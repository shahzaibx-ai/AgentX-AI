"""Photos in chat: validation, limits, routing to vision models, provider formats."""

import base64
from types import SimpleNamespace

import pytest
from ollama import ResponseError
from ollama._client import _copy_messages
from pydantic import ValidationError

from app.images import sniff
from app.providers.anthropic import AnthropicProvider, to_anthropic_turn
from app.providers.base import ProviderError
from app.providers.ollama import OllamaProvider, to_ollama_messages
from app.providers.openai_compat import to_openai_message
from app.schemas import ChatMessage, ImageInput
from app.services.chat import NO_VISION_MESSAGE, text_only_message
from app.vision import cloud_vision, matches_extra, ollama_vision
from tests.conftest import FakeProvider, parse_sse

# A real 1x1 PNG and a JPEG-signature stub.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def image(data: bytes = PNG, media_type: str = "image/png") -> dict:
    return {"media_type": media_type, "data": b64(data)}


def user(text: str = "What is this?", *images: dict) -> dict:
    return {"role": "user", "content": text, "images": list(images)}


# ---------------------------------------------------------------- validation
def test_image_is_decoded_and_its_real_type_wins():
    img = ImageInput(**image(PNG, "image/jpeg"))
    assert img.media_type == "image/png"
    assert img.raw == PNG
    assert ImageInput(media_type="image/png", data="data:image/png;base64," + b64(PNG)).raw == PNG


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("/etc/passwd", "not valid base64"),  # would be read as a file by the Ollama SDK
        (b64(b"/etc/passwd"), "Only JPEG, PNG, WebP and GIF"),
        (b64(b"GIF8 not quite"), "Only JPEG, PNG, WebP and GIF"),
        ("!!!not base64!!!", "not valid base64"),
    ],
)
def test_bad_images_are_rejected(data, message):
    with pytest.raises(ValidationError, match=message):
        ImageInput(media_type="image/png", data=data)


def test_sniff_formats():
    assert sniff(PNG) == "image/png"
    assert sniff(JPEG) == "image/jpeg"
    assert sniff(b"GIF89a....") == "image/gif"
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff(b"<svg>") is None


def test_message_rules():
    assert ChatMessage(role="user", content="", images=[image()]).images  # photo-only message
    with pytest.raises(ValidationError, match="Only user messages can have images"):
        ChatMessage(role="assistant", content="hi", images=[image()])
    assert ChatMessage(role="assistant", content="").content == ""  # errored replies in history


def test_decoded_images_are_not_kept_twice():
    img = ImageInput(**image())
    assert img.data == ""
    assert img.raw == PNG


def test_image_count_is_checked_before_decoding(make_client):
    client = make_client(FakeProvider("ollama", local=True, models=["gemma3"]))
    # 101 images that are not even valid: rejected by count, never decoded.
    body = {
        "messages": [
            {
                "role": "user",
                "content": "x",
                "images": [{"media_type": "image/png", "data": "!"}] * 10,
            }
        ]
        * 11
    }
    res = client.post("/api/chat", json=body)
    assert res.status_code == 422
    assert "Too many photos (110)" in str(res.json()["detail"])


def test_oversized_body_is_refused_while_streaming(make_client):
    client = make_client(
        FakeProvider("ollama", local=True, models=["gemma3"]),
        max_images_per_request=1,
        max_image_bytes=1024,
    )
    big = b'{"messages":[{"role":"user","content":"' + b"x" * (9 * 1024 * 1024) + b'"}]}'
    res = client.post("/api/chat", content=big, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert "too large" in res.json()["detail"]

    def chunks():
        yield big[: 1024 * 1024]
        yield big[1024 * 1024 :]

    res = client.post("/api/chat", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


# ---------------------------------------------------------------- limits
def test_photo_limits(make_client):
    vision = FakeProvider("ollama", local=True, models=["gemma3"], vision_models={"gemma3"})
    client = make_client(vision, max_images_per_message=2, max_images_per_request=3,
                         max_image_bytes=1024)  # fmt: skip

    too_many = client.post("/api/chat", json={"messages": [user("x", *[image()] * 3)]})
    assert too_many.status_code == 422
    assert too_many.json()["detail"] == "Up to 2 photos per message"

    history = [user("a", image(), image()), {"role": "assistant", "content": "ok"},
               user("b", image(), image())]  # fmt: skip
    over_request = client.post("/api/chat", json={"messages": history})
    assert over_request.json()["detail"] == "Up to 3 photos per conversation request"

    big = client.post("/api/chat", json={"messages": [user("x", image(PNG + b"\x00" * 2048))]})
    assert big.status_code == 422
    assert big.json()["detail"].startswith("A photo is 0.0 MB; the limit is")

    bad = client.post("/api/chat", json={"messages": [user("x", image(b"hello world!"))]})
    assert bad.status_code == 422
    assert "Only JPEG, PNG, WebP and GIF" in str(bad.json()["detail"])


# ---------------------------------------------------------------- routing
def events(client, body):
    return parse_sse(client.post("/api/chat", json=body).text)


def test_auto_picks_a_vision_model_and_passes_the_images(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llama3.2"],
                         vision_models={"gemma3"}, default_model="llama3.2")  # fmt: skip
    client = make_client(local)
    result = events(client, {"messages": [user("Describe", image())]})
    assert result[0] == ("meta", result[0][1])
    assert result[0][1]["model"] == "gemma3"
    ((model, messages),) = local.calls
    assert model == "gemma3"
    assert messages[-1].images[0].raw == PNG


def test_text_requests_are_unchanged(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llama3.2"],
                         vision_models={"gemma3"}, default_model="llama3.2")  # fmt: skip
    client = make_client(local)
    assert events(client, {"messages": [user("Hi")]})[0][1]["model"] == "llama3.2"


def test_auto_goes_to_cloud_vision_when_no_local_model_can_see(make_client):
    local = FakeProvider("ollama", local=True, models=["llama3.2"])
    cloud = FakeProvider("openai", models=["gpt-4o-mini"], vision_models={"gpt-4o-mini"})
    client = make_client(local, cloud)
    meta = events(client, {"messages": [user("Describe", image())]})[0][1]
    assert (meta["provider"], meta["model"]) == ("openai", "gpt-4o-mini")
    assert local.calls == []


def test_chosen_text_only_model_is_refused_with_a_clear_message(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llama3.2"],
                         vision_models={"gemma3"})  # fmt: skip
    client = make_client(local)
    body = {"messages": [user("Describe", image())], "provider": "ollama", "model": "llama3.2"}
    result = events(client, body)
    assert result == [("error", {"message": text_only_message("llama3.2")})]
    assert "llama3.2 can't see images" in result[0][1]["message"]
    assert local.calls == []


def test_provider_default_model_is_checked_too(make_client):
    cloud = FakeProvider("openai", models=["gpt-3.5-turbo"], default_model="gpt-3.5-turbo")
    client = make_client(cloud)
    result = events(client, {"messages": [user("Describe", image())], "provider": "openai"})
    assert result == [("error", {"message": text_only_message("gpt-3.5-turbo")})]


def test_unlisted_model_is_judged_by_name(make_client):
    cloud = FakeProvider("openai", models=["gpt-4o"], vision_models={"gpt-4o"})
    client = make_client(cloud)
    body = {"messages": [user("Describe", image())], "provider": "openai", "model": "gpt-3.5-turbo"}
    assert events(client, body)[0][0] == "error"
    body["model"] = "gpt-4o-2024-11-20"  # not listed, but a vision family
    assert events(client, body)[0][0] == "meta"


def test_chosen_vision_model_is_used(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llava"],
                         vision_models={"gemma3", "llava"})  # fmt: skip
    client = make_client(local)
    body = {"messages": [user("Describe", image())], "provider": "ollama", "model": "llava"}
    assert events(client, body)[0][1]["model"] == "llava"


def test_no_vision_model_anywhere(make_client):
    client = make_client(FakeProvider("ollama", local=True, models=["llama3.2"]))
    assert events(client, {"messages": [user("Describe", image())]}) == [
        ("error", {"message": NO_VISION_MESSAGE})
    ]


def test_fallback_only_moves_to_models_that_can_see(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3"], vision_models={"gemma3"},
                         chat_error="Ollama error: model crashed")  # fmt: skip
    text_cloud = FakeProvider("grok", models=["grok-3"])
    vision_cloud = FakeProvider("gemini", models=["gemini-2.5-flash"],
                                vision_models={"gemini-2.5-flash"})  # fmt: skip
    client = make_client(local, text_cloud, vision_cloud)
    meta = events(client, {"messages": [user("Describe", image())]})[0][1]
    assert meta["provider"] == "gemini"
    assert meta["fallback"] is True
    assert text_cloud.calls == []


def test_a_photo_earlier_in_the_chat_still_needs_vision(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llama3.2"],
                         vision_models={"gemma3"}, default_model="llama3.2")  # fmt: skip
    client = make_client(local)
    history = [user("What is this?", image()), {"role": "assistant", "content": "A dot."},
               user("And the colour?")]  # fmt: skip
    assert events(client, {"messages": history})[0][1]["model"] == "gemma3"


def test_models_endpoint_reports_vision(make_client):
    local = FakeProvider("ollama", local=True, models=["gemma3", "llama3.2"],
                         vision_models={"gemma3"}, default_model="llama3.2")  # fmt: skip
    body = make_client(local).get("/api/models").json()
    assert body["default"]["id"] == "llama3.2"
    assert body["default_vision"]["id"] == "gemma3"
    by_id = {m["id"]: m["vision"] for m in body["providers"][0]["models"]}
    assert by_id == {"gemma3": True, "llama3.2": False}
    assert body["image_limits"] == {
        "per_message": 5,
        "per_request": 20,
        "max_bytes": 10 * 1024 * 1024,
    }


def test_vision_models_setting_marks_extra_models(make_client):
    cloud = FakeProvider("meta", models=["my-org/custom-vl"])
    body = make_client(cloud, vision_models=["*-vl"]).get("/api/models").json()
    assert body["providers"][0]["models"][0]["vision"] is True


# ---------------------------------------------------------------- provider formats
def test_ollama_gets_raw_bytes_never_strings():
    msgs = to_ollama_messages([ChatMessage(role="user", content="hi", images=[image()]),
                               ChatMessage(role="assistant", content="ok")])  # fmt: skip
    assert msgs[0]["images"] == [PNG]
    assert "images" not in msgs[1]
    # What the SDK sends: bytes are base64-encoded by the SDK, no file lookups.
    sent = [m.model_dump(exclude_none=True) for m in _copy_messages(msgs)]
    assert sent[0]["images"] == [b64(PNG)]


async def test_anthropic_refuses_photos_over_5_mb_before_any_text():
    big = PNG + b"\x00" * (5 * 1024 * 1024)
    provider = AnthropicProvider(api_key="test-key")
    msg = ChatMessage(role="user", content="hi", images=[image(big)])
    with pytest.raises(ProviderError, match="under 5 MB"):
        async for _ in provider.stream_chat("claude-sonnet-4-5", [msg]):
            pass


def test_anthropic_content_blocks():
    turn = to_anthropic_turn(ChatMessage(role="user", content="What?", images=[image()]))
    assert turn["content"][0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": b64(PNG)},
    }
    assert turn["content"][1] == {"type": "text", "text": "What?"}
    photo_only = to_anthropic_turn(ChatMessage(role="user", content="", images=[image()]))
    assert [b["type"] for b in photo_only["content"]] == ["image"]  # no empty text block
    assert to_anthropic_turn(ChatMessage(role="user", content="plain")) == {
        "role": "user", "content": "plain"}  # fmt: skip


def test_openai_content_parts():
    msg = to_openai_message(ChatMessage(role="user", content="What?", images=[image(JPEG)]))
    assert msg["content"] == [
        {"type": "text", "text": "What?"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(JPEG)}"}},
    ]
    assert to_openai_message(ChatMessage(role="system", content="Be nice.")) == {
        "role": "system", "content": "Be nice."}  # fmt: skip


async def test_ollama_reads_vision_from_capabilities_and_falls_back_to_names():
    provider = OllamaProvider("http://localhost:11434")

    def item(name, families=("llama",)):
        details = SimpleNamespace(family=families[0], families=list(families), parameter_size="4B")
        return SimpleNamespace(model=name, size=1, details=details, digest=f"sha-{name}")

    async def fake_list():
        return SimpleNamespace(models=[item("gemma3:4b", ("gemma3",)), item("llama3.2:latest"),
                                       item("llava:7b", ("llama", "clip"))])  # fmt: skip

    async def fake_show(name):
        if name == "llava:7b":
            raise ResponseError("show failed")  # older server: fall back to families/names
        caps = {"gemma3:4b": ["completion", "vision"], "llama3.2:latest": ["completion", "tools"]}
        return SimpleNamespace(capabilities=caps[name])

    calls: list[str] = []

    async def counting_show(name):
        calls.append(name)
        return await fake_show(name)

    provider._client.list = fake_list
    provider._client.show = counting_show
    vision = {m.id: m.vision for m in await provider.list_models()}
    assert vision == {"gemma3:4b": True, "llama3.2:latest": False, "llava:7b": True}
    # Known digests are cached; the failed one is asked again.
    calls.clear()
    await provider.list_models()
    assert calls == ["llava:7b"]


def test_vision_rules():
    assert ollama_vision("gemma3:1b", None, ["gemma3"]) is False
    assert ollama_vision("qwen2.5vl:7b", None, ["qwen25vl"]) is True
    assert ollama_vision("anything", ["completion", "vision"], None) is True
    assert ollama_vision("llava:7b", ["completion"], ["clip"]) is False  # server's word wins
    assert cloud_vision("anthropic", "claude-sonnet-4-5") is True
    assert cloud_vision("openai", "gpt-4o-mini") is True
    assert cloud_vision("openai", "gpt-3.5-turbo") is False
    assert cloud_vision("openai", "o3-mini") is False
    assert cloud_vision("openai", "gpt-4-turbo-preview") is False
    assert cloud_vision("openai", "o1-preview") is False
    assert ollama_vision("gemma3n:e4b", None, ["gemma3n"]) is False
    assert cloud_vision("gemini", "gemini-2.5-flash") is True
    assert cloud_vision("grok", "grok-3") is False
    assert cloud_vision("grok", "grok-2-vision-1212") is True
    assert cloud_vision("meta", "Llama-4-Maverick-17B-128E-Instruct-FP8") is True
    assert cloud_vision("unknown", "x") is False
    assert matches_extra("My-Org/Custom-VL", ["*-vl"]) is True
