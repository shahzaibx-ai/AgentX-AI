"""Unit tests for the real provider adapters, with the SDK clients mocked."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.providers.base import ProviderError
from app.providers.ollama import OllamaProvider
from app.providers.openai_compat import OpenAICompatibleProvider, openai_model_filter
from app.providers.registry import build_providers
from app.schemas import ChatMessage


def test_build_providers_orders_local_then_cloud_priority():
    settings = Settings(_env_file=None, cloud_priority=["grok", "openai"], grok_api_key="k")
    ids = [p.id for p in build_providers(settings)]
    assert ids[:3] == ["ollama", "grok", "openai"]
    assert set(ids) == {"ollama", "anthropic", "openai", "gemini", "grok", "meta"}
    configured = {p.id for p in build_providers(settings) if p.configured}
    assert configured == {"ollama", "grok"}


def test_openai_filter_hides_non_chat_models():
    f = openai_model_filter()
    assert f("gpt-5.5")
    assert not f("text-embedding-3-large")
    assert not f("whisper-1")
    assert not f("gpt-image-2")


async def test_ollama_lists_chat_models_and_skips_embeddings():
    provider = OllamaProvider("http://localhost:11434")

    def model(name, family="llama", families=None, size=1):
        details = SimpleNamespace(family=family, families=families or [family], parameter_size="3B")
        return SimpleNamespace(model=name, size=size, details=details)

    async def fake_list():
        return SimpleNamespace(
            models=[
                model("qwen3:8b"),
                model("llama3.2:latest"),
                model("nomic-embed-text:latest", "nomic-bert", ["nomic-bert"]),
            ]
        )

    provider._client.list = fake_list
    models = await provider.list_models()
    assert [m.name for m in models] == ["llama3.2", "qwen3:8b"]
    assert models[0].id == "llama3.2:latest"
    assert models[0].local is True


async def test_ollama_unreachable_raises_provider_error():
    provider = OllamaProvider("http://localhost:1")

    async def boom():
        raise ConnectionError("refused")

    provider._client.list = boom
    with pytest.raises(ProviderError, match="not reachable"):
        await provider.list_models()


async def test_ollama_streams_deltas():
    provider = OllamaProvider("http://localhost:11434")

    async def fake_chat(**kwargs):
        async def gen():
            for text in ["Hel", "lo", ""]:
                yield SimpleNamespace(message=SimpleNamespace(content=text))

        return gen()

    provider._client.chat = fake_chat
    out = [t async for t in provider.stream_chat("m", [ChatMessage(role="user", content="hi")])]
    assert out == ["Hel", "lo"]


async def test_unconfigured_cloud_provider_raises():
    provider = OpenAICompatibleProvider("openai", "OpenAI", None, "https://x")
    assert provider.configured is False
    with pytest.raises(ProviderError, match="missing API key"):
        await provider.list_models()
