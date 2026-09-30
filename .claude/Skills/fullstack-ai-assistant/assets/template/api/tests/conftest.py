import json
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.base import Provider, ProviderError
from app.providers.registry import ProviderRegistry
from app.schemas import ChatMessage, ModelInfo


class FakeProvider(Provider):
    def __init__(
        self,
        provider_id: str,
        *,
        local: bool = False,
        models: list[str] | None = None,
        reply: str = "Hello there",
        configured: bool = True,
        list_error: str | None = None,
        chat_error: str | None = None,
        fail_after_tokens: int | None = None,
        default_model: str = "",
    ) -> None:
        self.id = provider_id
        self.label = provider_id.title()
        self.local = local
        self._models = models or []
        self._reply = reply
        self._configured = configured
        self._list_error = list_error
        self._chat_error = chat_error
        self._fail_after = fail_after_tokens
        self._default = default_model
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def default_model(self) -> str:
        return self._default

    async def list_models(self) -> list[ModelInfo]:
        if self._list_error:
            raise ProviderError(self._list_error)
        return [ModelInfo(id=m, name=m, provider=self.id, local=self.local) for m in self._models]

    async def stream_chat(
        self, model: str, messages: list[ChatMessage], temperature: float | None = None
    ) -> AsyncIterator[str]:
        self.calls.append((model, messages))
        if self._chat_error:
            raise ProviderError(self._chat_error)
        for i, word in enumerate(self._reply.split(" ")):
            if self._fail_after is not None and i >= self._fail_after:
                raise ProviderError("connection dropped")
            yield word if i == 0 else f" {word}"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = "message", None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        events.append((name, data))
    return events


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, system_prompt="Be helpful.", cors_origins=["*"])


@pytest.fixture
def make_client(settings: Settings) -> Iterator:
    clients: list[TestClient] = []

    def factory(*providers: Provider, **overrides) -> TestClient:
        cfg = settings.model_copy(update=overrides)
        registry = ProviderRegistry(list(providers), cache_ttl=0)
        client = TestClient(create_app(cfg, registry))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)
