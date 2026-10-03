"""Local models served by Ollama via the official Python SDK."""

from collections.abc import AsyncIterator

import httpx
from ollama import AsyncClient, ResponseError

from app.providers.base import Provider, ProviderError
from app.schemas import ChatMessage, ModelInfo


class OllamaProvider(Provider):
    id = "ollama"
    label = "Ollama (local)"
    local = True

    def __init__(self, host: str, enabled: bool = True, timeout: float = 120.0) -> None:
        self._host = host
        self._enabled = enabled
        self._client = AsyncClient(host=host, timeout=timeout)

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._host)

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.list()
        except (httpx.HTTPError, ConnectionError, ResponseError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc

        models: list[ModelInfo] = []
        for item in response.models:
            if not item.model:
                continue
            details = item.details
            # Embedding-only models cannot chat, so keep them out of the dropdown.
            families = (details.families or []) if details else []
            if any("bert" in f for f in families) or "embed" in item.model:
                continue
            models.append(
                ModelInfo(
                    id=item.model,
                    name=item.model.removesuffix(":latest"),
                    provider=self.id,
                    local=True,
                    size_bytes=item.size,
                    parameter_size=details.parameter_size if details else None,
                    family=details.family if details else None,
                )
            )
        return sorted(models, key=lambda m: m.name)

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
                messages=[m.model_dump() for m in messages],
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
