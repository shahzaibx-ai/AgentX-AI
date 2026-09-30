import json

import httpx
from livekit.agents import llm

from app_llm import FALLBACK_REPLY, AppLLM, chat_context_to_messages


def sse(*events: tuple[str | None, dict]) -> str:
    parts = []
    for name, data in events:
        head = f"event: {name}\n" if name else ""
        parts.append(f"{head}data: {json.dumps(data)}\n\n")
    return "".join(parts)


META = {
    "provider": "ollama",
    "provider_label": "Ollama (local)",
    "model": "llama3.2",
    "local": True,
}


def make_llm(handler, **kw):
    seen: dict = {"meta": [], "errors": [], "requests": []}

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen["requests"].append(json.loads(request.content))
        seen.setdefault("auth", []).append(request.headers.get("authorization"))
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    model = AppLLM(
        api_url="http://api:8000/",
        room="voice-" + "a" * 32,
        client=client,
        on_meta=seen["meta"].append,
        on_error=seen["errors"].append,
        **kw,
    )
    return model, seen


def context() -> llm.ChatContext:
    ctx = llm.ChatContext.empty()
    ctx.add_message(role="system", content="Be brief.")
    ctx.add_message(role="assistant", content="Hi! What can I help you with?")
    ctx.add_message(role="user", content="What is AI?")
    return ctx


async def reply_text(model: AppLLM) -> str:
    chunks = []
    async with model.chat(chat_ctx=context()) as stream:
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                chunks.append(chunk.delta.content)
    return "".join(chunks)


def test_chat_context_to_messages_maps_roles_and_skips_empty():
    ctx = llm.ChatContext.empty()
    ctx.add_message(role="developer", content="Rules")
    ctx.add_message(role="user", content="   ")
    ctx.add_message(role="user", content="Hello")
    ctx.add_message(role="assistant", content="Hi")
    assert chat_context_to_messages(ctx) == [
        {"role": "system", "content": "Rules"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]


async def test_streams_reply_and_reports_model():
    body = sse(
        ("meta", META), (None, {"delta": "AI is "}), (None, {"delta": "software."}), ("done", {})
    )
    model, seen = make_llm(lambda r: httpx.Response(200, text=body))
    assert await reply_text(model) == "AI is software."
    assert seen["meta"] == [META]
    assert seen["errors"] == []
    (request,) = seen["requests"]
    assert request["room"] == "voice-" + "a" * 32
    assert request["messages"][-1] == {"role": "user", "content": "What is AI?"}
    assert request["messages"][0] == {"role": "system", "content": "Be brief."}


async def test_posts_to_voice_chat_endpoint():
    model, _ = make_llm(lambda r: httpx.Response(200, text=sse(("done", {}))))
    assert model.url == "http://api:8000/api/voice/chat"


async def test_sends_agent_token_only_when_configured():
    done = sse(("done", {}))
    plain, seen = make_llm(lambda r: httpx.Response(200, text=done))
    await reply_text(plain)
    assert seen["auth"] == [None]

    signed, seen = make_llm(lambda r: httpx.Response(200, text=done), token="agent-shared-secret")
    await reply_text(signed)
    assert seen["auth"] == ["Bearer agent-shared-secret"]


async def test_model_error_before_text_speaks_apology():
    body = sse(("error", {"message": "No AI model is available."}))
    model, seen = make_llm(lambda r: httpx.Response(200, text=body))
    assert await reply_text(model) == FALLBACK_REPLY
    assert seen["errors"] == ["No AI model is available."]


async def test_model_error_after_text_keeps_partial_reply():
    body = sse((None, {"delta": "Partial"}), ("error", {"message": "connection dropped"}))
    model, seen = make_llm(lambda r: httpx.Response(200, text=body))
    assert await reply_text(model) == "Partial"
    assert seen["errors"] == ["connection dropped"]


async def test_http_error_speaks_apology_with_detail():
    model, seen = make_llm(
        lambda r: httpx.Response(422, json={"detail": "Last message must be user"})
    )
    assert await reply_text(model) == FALLBACK_REPLY
    assert seen["errors"] == ["API error 422: Last message must be user"]


async def test_unreachable_api_speaks_apology():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    model, seen = make_llm(refuse)
    assert await reply_text(model) == FALLBACK_REPLY
    assert "Can't reach the API" in seen["errors"][0]
