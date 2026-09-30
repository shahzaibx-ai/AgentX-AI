"""Provider interface shared by the local (Ollama) and cloud backends."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas import ChatMessage, ModelInfo


class ProviderError(Exception):
    """A provider could not serve the request. Safe to show to the user."""


class Provider(ABC):
    id: str
    label: str
    local: bool = False

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True when the provider has what it needs to run (host or API key)."""

    @property
    def default_model(self) -> str:
        """Preferred model id, if one is configured. Empty means 'first listed'."""
        return ""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return the models this provider can serve right now."""

    @abstractmethod
    def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas for a chat completion."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        """Release network resources."""
