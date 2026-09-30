"""Voice package tests.

Most run on a bare FastAPI app with a fake brain (the package works in any
app); the last ones check this app's adapter (app/voice_brain.py).
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from livekit import api
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from app.providers.registry import ProviderRegistry
from app.voice import BrainRequest, VoiceOption, VoiceSettings, mount_voice
from app.voice.schemas import VoiceMessage
from app.voice.service import (
    VoiceContext,
    VoiceContextStore,
    build_voice_messages,
    normalise_messages,
)
from tests.conftest import FakeProvider, parse_sse

KEY, SECRET = "devkey", "a-long-enough-test-secret-value-000"
ENABLED = {
    "livekit_url": "wss://example.livekit.cloud",
    "livekit_api_key": SecretStr(KEY),
    "livekit_api_secret": SecretStr(SECRET),
    "voice_agent_name": "my-agent",
    "voice_voices": [
        VoiceOption(id="calm", name="Calm", description="Even", tts_voice="tts-calm-123")
    ],
}


def msg(role, content):
    return VoiceMessage(role=role, content=content)


class RecordingBrain:
    """A fake host chat pipeline that records what it was asked."""

    def __init__(self, reply="Spoken answer", fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    async def __call__(self, request, req: BrainRequest):
        self.calls.append(req)
        if self.fail:
            raise RuntimeError("boom")
        yield "meta", {"provider": "fake", "provider_label": "Fake", "model": "m1", "local": True}
        for word in self.reply.split(" "):
            yield "delta", {"delta": word + " "}
        yield "done", {}


def bare_client(brain=None, **settings) -> tuple[TestClient, RecordingBrain]:
    brain = brain or RecordingBrain()
    app = FastAPI()
    mount_voice(app, brain=brain, settings=VoiceSettings(_env_file=None, **settings))
    return TestClient(app), brain


# ---------- config ----------


def test_config_disabled_without_livekit_keys():
    body = bare_client()[0].get("/api/voice/config").json()
    assert body["enabled"] is False
    assert "LIVEKIT_URL" in body["reason"]


def test_config_enabled_lists_voices_without_internal_ids():
    body = bare_client(**ENABLED)[0].get("/api/voice/config").json()
    assert body == {
        "enabled": True,
        "reason": None,
        "voices": [{"id": "calm", "name": "Calm", "description": "Even"}],
    }


def test_custom_prefix():
    app = FastAPI()
    mount_voice(app, RecordingBrain(), VoiceSettings(_env_file=None), prefix="/voice")
    assert TestClient(app).get("/voice/config").status_code == 200


# ---------- session ----------


def test_session_unavailable_when_not_configured():
    assert bare_client()[0].post("/api/voice/session", json={}).status_code == 503


def test_session_returns_token_that_dispatches_the_agent():
    client, _ = bare_client(**ENABLED)
    res = client.post(
        "/api/voice/session",
        json={
            "provider": "ollama",
            "model": "llama3.2",
            "voice": "calm",
            "participant_name": "Rizwan",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["server_url"] == "wss://example.livekit.cloud"
    assert body["room_name"].startswith("voice-") and len(body["room_name"]) == 38

    claims = api.TokenVerifier(KEY, SECRET).verify(body["participant_token"])
    assert claims.identity == body["participant_identity"]
    assert claims.name == "Rizwan"
    assert claims.video.room_join is True
    assert claims.video.room == body["room_name"]
    (dispatch,) = claims.room_config.agents
    assert dispatch.agent_name == "my-agent"
    assert json.loads(dispatch.metadata) == {"voice": "tts-calm-123"}


def test_session_rejects_unknown_voice():
    assert (
        bare_client(**ENABLED)[0].post("/api/voice/session", json={"voice": "x"}).status_code == 422
    )


def test_each_session_gets_its_own_room():
    client, _ = bare_client(**ENABLED)
    rooms = {client.post("/api/voice/session", json={}).json()["room_name"] for _ in range(3)}
    assert len(rooms) == 3


@pytest.mark.parametrize(("limit", "expected"), [(0, []), (2, ["q3", "q4"])])
def test_history_is_trimmed(limit, expected):
    client, _ = bare_client(**ENABLED, voice_history_messages=limit)
    history = [{"role": "user", "content": f"q{i}"} for i in range(5)]
    room = client.post("/api/voice/session", json={"history": history}).json()["room_name"]
    stored = client.app.state.voice_store.get(room).history
    assert [m.content for m in stored] == expected


# ---------- voice chat (called by the agent) ----------


def start(client, **body):
    return client.post("/api/voice/session", json=body).json()["room_name"]


def test_voice_chat_passes_model_and_history_to_the_brain():
    client, brain = bare_client(**ENABLED)
    room = start(
        client,
        provider="ollama",
        model="b",
        history=[
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
        ],
    )
    res = client.post(
        "/api/voice/chat",
        json={
            "room": room,
            "messages": [
                {"role": "system", "content": "You are a voice assistant."},
                {"role": "assistant", "content": "Hi! How can I help?"},
                {"role": "user", "content": "What is AI?"},
            ],
        },
    )
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    assert events[0] == (
        "meta",
        {"provider": "fake", "provider_label": "Fake", "model": "m1", "local": True},
    )
    assert "".join(d["delta"] for n, d in events if n == "message").strip() == "Spoken answer"
    assert events[-1] == ("done", {})

    (req,) = brain.calls
    assert (req.provider, req.model) == ("ollama", "b")
    assert req.messages == [
        {"role": "system", "content": "You are a voice assistant."},
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer\n\nHi! How can I help?"},
        {"role": "user", "content": "What is AI?"},
    ]


def test_voice_chat_with_unknown_room_uses_auto():
    client, brain = bare_client(**ENABLED)
    client.post(
        "/api/voice/chat",
        json={"room": "voice-" + "0" * 32, "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert (brain.calls[0].provider, brain.calls[0].model) == (None, None)


def test_brain_crash_becomes_an_error_event():
    client, _ = bare_client(RecordingBrain(fail=True), **ENABLED)
    res = client.post(
        "/api/voice/chat",
        json={"room": "voice-" + "0" * 32, "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert parse_sse(res.text) == [("error", {"message": "The assistant failed to answer."})]


def test_agent_token_guards_voice_chat():
    client, brain = bare_client(**ENABLED, voice_agent_token=SecretStr("agent-shared-secret"))
    body = {"room": "voice-" + "0" * 32, "messages": [{"role": "user", "content": "Hi"}]}

    assert client.post("/api/voice/chat", json=body).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.post("/api/voice/chat", json=body, headers=wrong).status_code == 401
    assert brain.calls == []

    ok = {"Authorization": "Bearer agent-shared-secret"}
    res = client.post("/api/voice/chat", json=body, headers=ok)
    assert res.status_code == 200
    assert parse_sse(res.text)[-1] == ("done", {})
    # The browser-facing endpoints don't need the agent token.
    assert client.get("/api/voice/config").status_code == 200
    assert client.post("/api/voice/session", json={}).status_code == 201


def test_voice_chat_validation():
    client, _ = bare_client(**ENABLED)
    bad_room = client.post(
        "/api/voice/chat", json={"room": "../etc", "messages": [{"role": "user", "content": "x"}]}
    )
    assert bad_room.status_code == 422
    no_user_turn = client.post(
        "/api/voice/chat",
        json={"room": "voice-" + "1" * 32, "messages": [{"role": "assistant", "content": "Hi"}]},
    )
    assert no_user_turn.status_code == 422


# ---------- helpers ----------


def test_normalise_merges_turns_and_drops_leading_assistant():
    out = normalise_messages(
        [
            msg("assistant", "Hello there"),
            msg("system", "A"),
            msg("user", "one"),
            msg("user", "two"),
            msg("assistant", "   "),
            msg("system", "B"),
        ]
    )
    assert [(m.role, m.content) for m in out] == [("system", "A\n\nB"), ("user", "one\n\ntwo")]


def test_build_voice_messages_caps_length_but_keeps_system():
    turns = [msg("user" if i % 2 == 0 else "assistant", f"t{i}") for i in range(11)]
    out = build_voice_messages(None, [msg("system", "S"), *turns], max_messages=5)
    assert len(out) <= 5
    assert [m.role for m in out[:2]] == ["system", "user"]  # never starts with assistant
    assert out[-1].content == "t10"


def test_store_expires_entries():
    store = VoiceContextStore(ttl_seconds=0)
    store.put("voice-x", VoiceContext(provider=None, model=None))
    assert store.get("voice-x") is None


# ---------- this app's adapter: voice uses the text-chat pipeline ----------


@pytest.fixture
def app_client():
    clients = []

    def factory(*providers):
        app = create_app(
            Settings(_env_file=None, system_prompt="Be helpful.", cors_origins=["*"]),
            ProviderRegistry(list(providers), cache_ttl=0),
            VoiceSettings(_env_file=None, **ENABLED),
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


def test_app_voice_uses_selected_model_with_fallback(app_client):
    ollama = FakeProvider("ollama", local=True, models=["a", "b"], chat_error="model not found")
    cloud = FakeProvider("openai", models=["gpt-x"], reply="Cloud answer")
    client = app_client(ollama, cloud)
    room = start(client, provider="ollama", model="b")
    events = parse_sse(
        client.post(
            "/api/voice/chat", json={"room": room, "messages": [{"role": "user", "content": "Hi"}]}
        ).text
    )
    assert events[0][1]["provider"] == "openai"
    assert events[0][1]["fallback"] is True
    assert "".join(d["delta"] for n, d in events if n == "message") == "Cloud answer"
    assert ollama.calls[0][0] == "b"


def test_app_voice_keeps_agent_instructions_as_system_prompt(app_client):
    ollama = FakeProvider("ollama", local=True, models=["m"])
    client = app_client(ollama)
    client.post(
        "/api/voice/chat",
        json={
            "room": "voice-" + "2" * 32,
            "messages": [
                {"role": "system", "content": "Speak briefly."},
                {"role": "user", "content": "Hi"},
            ],
        },
    )
    _, messages = ollama.calls[0]
    assert [(m.role, m.content) for m in messages] == [("system", "Speak briefly."), ("user", "Hi")]
