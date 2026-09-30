"""Builds providers from settings and decides which model serves a request.

Resolution order:
1. The provider/model the user picked in the UI.
2. Any locally installed Ollama model.
3. Configured cloud providers in `CLOUD_PRIORITY` order.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import Provider, ProviderError
from app.providers.ollama import OllamaProvider
from app.providers.openai_compat import OpenAICompatibleProvider, openai_model_filter
from app.schemas import ModelInfo, ModelsResponse, ProviderStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candidate:
    provider: Provider
    model: str


def _secret(value) -> str | None:
    return value.get_secret_value() if value else None


def build_providers(settings: Settings) -> list[Provider]:
    t = settings.request_timeout_seconds
    s = settings

    def compat(pid: str, label: str, key, url: str, model: str, **kw) -> Provider:
        return OpenAICompatibleProvider(
            pid, label, _secret(key), url, default_model=model, timeout=t, **kw
        )

    cloud: dict[str, Provider] = {
        "anthropic": AnthropicProvider(_secret(s.anthropic_api_key), s.anthropic_model, t),
        "openai": compat(
            "openai",
            "OpenAI",
            s.openai_api_key,
            s.openai_base_url,
            s.openai_model,
            model_filter=openai_model_filter(),
        ),
        "gemini": compat(
            "gemini", "Google Gemini", s.gemini_api_key, s.gemini_base_url, s.gemini_model
        ),
        "grok": compat("grok", "xAI Grok", s.grok_api_key, s.grok_base_url, s.grok_model),
        "meta": compat("meta", "Meta Llama", s.meta_api_key, s.meta_base_url, s.meta_model),
    }
    ordered = [cloud[p] for p in settings.cloud_priority if p in cloud]
    ordered += [p for key, p in cloud.items() if key not in settings.cloud_priority]
    local = OllamaProvider(settings.ollama_host, settings.ollama_enabled, t)
    return [local, *ordered]


class ProviderRegistry:
    def __init__(self, providers: list[Provider], cache_ttl: float = 30.0) -> None:
        self._providers = {p.id: p for p in providers}
        self._order = [p.id for p in providers]
        self._ttl = cache_ttl
        self._cache: tuple[float, list[ProviderStatus]] | None = None
        self._lock = asyncio.Lock()

    def get(self, provider_id: str) -> Provider | None:
        return self._providers.get(provider_id)

    @property
    def providers(self) -> list[Provider]:
        return [self._providers[i] for i in self._order]

    def invalidate(self) -> None:
        self._cache = None

    async def _probe(self, provider: Provider) -> ProviderStatus:
        status = ProviderStatus(
            id=provider.id,
            label=provider.label,
            local=provider.local,
            configured=provider.configured,
            available=False,
        )
        if not provider.configured:
            return status
        try:
            status.models = await asyncio.wait_for(provider.list_models(), timeout=10)
            status.available = True
        except (ProviderError, TimeoutError) as exc:
            status.error = str(exc) or "Timed out while listing models"
            logger.info("Provider %s unavailable: %s", provider.id, status.error)
        return status

    async def statuses(self, refresh: bool = False) -> list[ProviderStatus]:
        async with self._lock:
            now = time.monotonic()
            if not refresh and self._cache and now - self._cache[0] < self._ttl:
                return self._cache[1]
            result = list(await asyncio.gather(*(self._probe(p) for p in self.providers)))
            self._cache = (now, result)
            return result

    @staticmethod
    def _preferred(provider: Provider, status: ProviderStatus) -> ModelInfo | None:
        if not status.available or not status.models:
            return None
        if provider.default_model:
            for m in status.models:
                if m.id == provider.default_model:
                    return m
        return status.models[0]

    async def models_response(self, refresh: bool = False) -> ModelsResponse:
        statuses = await self.statuses(refresh)
        default = None
        for status in statuses:
            default = self._preferred(self._providers[status.id], status)
            if default:
                break
        return ModelsResponse(
            providers=statuses,
            default=default,
            has_local_models=any(s.local and s.models for s in statuses),
        )

    async def candidates(
        self, provider_id: str | None, model: str | None, allow_fallback: bool
    ) -> list[Candidate]:
        """Ordered list of (provider, model) pairs to try for a request."""
        result: list[Candidate] = []
        if provider_id:
            provider = self.get(provider_id)
            if provider is None:
                raise ProviderError(f"Unknown provider '{provider_id}'")
            if provider.configured:
                chosen = model or provider.default_model
                if not chosen:
                    status = next(s for s in await self.statuses() if s.id == provider_id)
                    preferred = self._preferred(provider, status)
                    chosen = preferred.id if preferred else ""
                if chosen:
                    result.append(Candidate(provider, chosen))
            if result and not allow_fallback:
                return result

        for status in await self.statuses():
            provider = self._providers[status.id]
            preferred = self._preferred(provider, status)
            if preferred and all(c.provider.id != provider.id for c in result):
                result.append(Candidate(provider, preferred.id))
        return result if allow_fallback else result[:1]

    async def aclose(self) -> None:
        await asyncio.gather(*(p.aclose() for p in self.providers), return_exceptions=True)
