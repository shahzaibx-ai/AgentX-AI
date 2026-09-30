"""Anthropic Claude via the official SDK."""

from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from app.providers.base import Provider, ProviderError
from app.schemas import ChatMessage, ModelInfo

DEFAULT_MAX_TOKENS = 8192


class AnthropicProvider(Provider):
    id = "anthropic"
    label = "Anthropic Claude"
    local = False

    def __init__(self, api_key: str | None, default_model: str = "", timeout: float = 120.0):
        self._default_model = default_model
        self._client = (
            AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=1) if api_key else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    @property
    def default_model(self) -> str:
        return self._default_model

    def _require_client(self) -> AsyncAnthropic:
        if self._client is None:
            raise ProviderError(f"{self.label} is not configured (missing API key)")
        return self._client

    async def list_models(self) -> list[ModelInfo]:
        client = self._require_client()
        try:
            models = [m async for m in client.models.list(limit=100)]
        except anthropic.APIError as exc:
            raise ProviderError(f"{self.label}: could not list models ({exc})") from exc
        return [
            ModelInfo(id=m.id, name=m.display_name or m.id, provider=self.id, local=False)
            for m in models
        ]

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        client = self._require_client()
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        kwargs: dict = {"model": model, "max_tokens": DEFAULT_MAX_TOKENS, "messages": turns}
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = min(temperature, 1.0)
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.AuthenticationError as exc:
            raise ProviderError(f"{self.label}: invalid API key") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(f"{self.label}: rate limit or quota exceeded") from exc
        except anthropic.APIError as exc:
            raise ProviderError(f"{self.label}: {exc.message}") from exc

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
