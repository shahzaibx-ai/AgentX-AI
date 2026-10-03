"""Streams a chat reply, falling back to the next provider when one fails.

Fallback only happens before the first token is sent; once text has reached
the client, switching models mid-answer would produce a garbled reply, so a
later failure is reported as an error instead.
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import ProviderError
from app.providers.registry import ProviderRegistry
from app.schemas import ChatMessage, ChatRequest

logger = logging.getLogger(__name__)


@dataclass
class ChatEvent:
    type: str  # "meta" | "delta" | "error" | "done"
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        if self.type == "delta":
            return f"data: {payload}\n\n"
        return f"event: {self.type}\ndata: {payload}\n\n"


NO_MODELS_MESSAGE = (
    "No AI model is available. Install a local model with `ollama pull llama3.2`, "
    "or add a cloud API key (Anthropic, OpenAI, Gemini, Grok or Meta) to the API's .env file."
)


class ChatService:
    def __init__(self, registry: ProviderRegistry, system_prompt: str, allow_fallback: bool):
        self._registry = registry
        self._system_prompt = system_prompt
        self._allow_fallback = allow_fallback

    def _with_system(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        if not self._system_prompt or any(m.role == "system" for m in messages):
            return messages
        return [ChatMessage(role="system", content=self._system_prompt), *messages]

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        try:
            candidates = await self._registry.candidates(
                request.provider, request.model, self._allow_fallback
            )
        except ProviderError as exc:
            yield ChatEvent("error", {"message": str(exc)})
            return

        if not candidates:
            yield ChatEvent("error", {"message": NO_MODELS_MESSAGE})
            return

        messages = self._with_system(request.messages)
        failures: list[str] = []

        for candidate in candidates:
            provider, model = candidate.provider, candidate.model
            started = False
            try:
                async for delta in provider.stream_chat(model, messages, request.temperature):
                    if not started:
                        started = True
                        yield ChatEvent(
                            "meta",
                            {
                                "provider": provider.id,
                                "provider_label": provider.label,
                                "model": model,
                                "local": provider.local,
                                "fallback": bool(failures),
                                "notice": "; ".join(failures) or None,
                            },
                        )
                    yield ChatEvent("delta", {"delta": delta})
            except ProviderError as exc:
                logger.warning("Provider %s/%s failed: %s", provider.id, model, exc)
                if started:
                    yield ChatEvent("error", {"message": str(exc)})
                    return
                failures.append(str(exc))
                self._registry.invalidate()
                continue

            if not started:  # provider returned an empty reply; treat as success
                yield ChatEvent(
                    "meta",
                    {
                        "provider": provider.id,
                        "provider_label": provider.label,
                        "model": model,
                        "local": provider.local,
                        "fallback": bool(failures),
                        "notice": "; ".join(failures) or None,
                    },
                )
            yield ChatEvent("done", {})
            return

        yield ChatEvent("error", {"message": " · ".join(failures) or NO_MODELS_MESSAGE})
