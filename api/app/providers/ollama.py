"""Local models served by Ollama via the official Python SDK."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
from ollama import AsyncClient, ResponseError

from app.providers.base import Provider, ProviderError
from app.schemas import ChatMessage, ModelInfo
from app.vision import ollama_vision

SHOW_TIMEOUT_SECONDS = 5.0


def to_ollama_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Ollama chat messages. Images go as raw bytes (never strings; see app/images.py)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        item: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.images:
            item["images"] = [image.raw for image in m.images]
        out.append(item)
    return out


def _is_chat_model(item: Any) -> bool:
    """Embedding-only models can't chat, so they stay out of the dropdown."""
    if not item.model:
        return False
    families = (item.details.families or []) if item.details else []
    return not any("bert" in f for f in families) and "embed" not in item.model


class OllamaProvider(Provider):
    id = "ollama"
    label = "Ollama (local)"
    local = True

    def __init__(self, host: str, enabled: bool = True, timeout: float = 120.0) -> None:
        self._host = host
        self._enabled = enabled
        self._client = AsyncClient(host=host, timeout=timeout)
        self._caps_cache: dict[tuple[str, str], list[str] | None] = {}

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._host)

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.list()
        except (httpx.HTTPError, ConnectionError, ResponseError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc

        items = [item for item in response.models if _is_chat_model(item)]
        capabilities = await self._capabilities(
            [(item.model, getattr(item, "digest", None) or "") for item in items]
        )

        models: list[ModelInfo] = []
        for item in items:
            details = item.details
            families = (details.families or []) if details else []
            models.append(
                ModelInfo(
                    id=item.model,
                    name=item.model.removesuffix(":latest"),
                    provider=self.id,
                    local=True,
                    size_bytes=item.size,
                    parameter_size=details.parameter_size if details else None,
                    family=details.family if details else None,
                    vision=ollama_vision(item.model, capabilities.get(item.model), families),
                )
            )
        return sorted(models, key=lambda m: m.name)

    async def _capabilities(self, models: list[tuple[str, str]]) -> dict[str, list[str] | None]:
        """Each model's capabilities from `ollama show` (None when the server doesn't say).

        Answers are cached by digest, so only new or re-pulled models are asked.
        """
        limit = asyncio.Semaphore(4)

        async def one(name: str, digest: str) -> list[str] | None:
            key = (name, digest)
            if digest and key in self._caps_cache:
                return self._caps_cache[key]
            async with limit:
                try:
                    info = await asyncio.wait_for(self._client.show(name), SHOW_TIMEOUT_SECONDS)
                except (httpx.HTTPError, ConnectionError, ResponseError, TimeoutError):
                    return None  # not cached: ask again next time
                caps = getattr(info, "capabilities", None)
                result = list(caps) if caps is not None else None
                if digest:
                    self._caps_cache[key] = result
                return result

        results = await asyncio.gather(*(one(n, d) for n, d in models))
        return {name: caps for (name, _), caps in zip(models, results, strict=True)}

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        options = {"temperature": temperature} if temperature is not None else None
        try:
            stream = await self._client.chat(
                model=model,
                messages=to_ollama_messages(messages),
                stream=True,
                options=options,
            )
            async for chunk in stream:
                if chunk.message and chunk.message.content:
                    yield chunk.message.content
        except ResponseError as exc:
            raise ProviderError(f"Ollama error: {exc.error}") from exc
        except (httpx.HTTPError, ConnectionError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc
