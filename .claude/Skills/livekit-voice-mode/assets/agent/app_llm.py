"""An LLM for LiveKit Agents that answers through the app's own API.

Instead of calling a model directly, the agent posts the spoken conversation
to `POST /api/voice/chat`. The API adds the model the user picked in the
dropdown and the earlier text chat, then streams the reply with the same
Ollama-first, cloud-fallback logic as text chat.

Failures never leave the user in silence: the agent speaks a short apology
and reports the real reason through `on_error` (shown in the web UI).
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
    llm,
)

logger = logging.getLogger("voice-agent.app-llm")

FALLBACK_REPLY = "Sorry, I can't reach the AI model right now. Please try again in a moment."

MetaCallback = Callable[[dict[str, Any]], None]
ErrorCallback = Callable[[str], None]


def chat_context_to_messages(chat_ctx: llm.ChatContext) -> list[dict[str, str]]:
    """Plain {role, content} messages the API accepts (tool calls are skipped)."""
    messages: list[dict[str, str]] = []
    for item in chat_ctx.items:
        if getattr(item, "type", None) != "message":
            continue
        text = (item.text_content or "").strip()
        if not text:
            continue
        role = "system" if item.role in ("system", "developer") else item.role
        messages.append({"role": role, "content": text})
    return messages


async def iter_sse(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Parse a text/event-stream into (event name, JSON payload) pairs."""
    event, data = "message", []
    async for line in lines:
        if not line:
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, json.loads("\n".join(data))


class AppLLM(llm.LLM):
    def __init__(
        self,
        *,
        api_url: str,
        room: str,
        timeout: float = 120.0,
        on_meta: MetaCallback | None = None,
        on_error: ErrorCallback | None = None,
        client: httpx.AsyncClient | None = None,
        token: str = "",
    ) -> None:
        super().__init__()
        self.url = api_url.rstrip("/") + "/api/voice/chat"
        self.room = room
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._on_meta = on_meta
        self._on_error = on_error
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))

    @property
    def model(self) -> str:
        return "app"

    @property
    def provider(self) -> str:
        return "ai-assistant-api"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> "AppLLMStream":
        return AppLLMStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)

    def notify_meta(self, meta: dict[str, Any]) -> None:
        if self._on_meta:
            self._on_meta(meta)

    def notify_error(self, message: str) -> None:
        logger.warning("voice reply failed: %s", message)
        if self._on_error:
            self._on_error(message)

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()


class AppLLMStream(llm.LLMStream):
    def __init__(
        self,
        app_llm: AppLLM,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(app_llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._app = app_llm
        # The API already falls back between models; never replay a half-spoken reply.
        self._retry_on_chunk_sent = False

    async def _run(self) -> None:
        request_id = f"app-{uuid.uuid4().hex[:12]}"
        sent_text = False

        def emit(text: str) -> None:
            self._event_ch.send_nowait(
                llm.ChatChunk(id=request_id, delta=llm.ChoiceDelta(role="assistant", content=text))
            )

        def fail(message: str) -> None:
            self._app.notify_error(message)
            if not sent_text:
                emit(FALLBACK_REPLY)

        payload = {"room": self._app.room, "messages": chat_context_to_messages(self._chat_ctx)}
        try:
            async with self._app.client.stream(
                "POST", self._app.url, json=payload, headers=self._app.headers
            ) as res:
                if res.status_code >= 400:
                    detail = await _error_detail(res)
                    fail(f"API error {res.status_code}: {detail}")
                    return
                async for name, data in iter_sse(res.aiter_lines()):
                    if name == "meta":
                        self._app.notify_meta(data)
                    elif name == "error":
                        fail(str(data.get("message") or "The model failed to answer."))
                        return
                    elif name == "done":
                        return
                    elif isinstance(data.get("delta"), str) and data["delta"]:
                        sent_text = True
                        emit(data["delta"])
            if not sent_text:
                fail("The reply ended before any text arrived.")
        except httpx.TimeoutException:
            fail("The AI model took too long to answer.")
        except httpx.HTTPError as exc:
            fail(f"Can't reach the API at {self._app.url} ({exc.__class__.__name__}).")
        except (json.JSONDecodeError, ValueError) as exc:
            fail(f"Unexpected response from the API ({exc}).")


async def _error_detail(res: httpx.Response) -> str:
    body = await res.aread()
    try:
        detail = json.loads(body).get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail and isinstance(detail[0], dict):
            return str(detail[0].get("msg", ""))
    except (json.JSONDecodeError, AttributeError):
        pass
    return body.decode(errors="replace")[:200]
