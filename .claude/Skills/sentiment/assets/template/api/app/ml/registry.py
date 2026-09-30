"""Loads models on first use (or at startup) and keeps them in memory."""

import contextlib
import logging
import threading
from collections.abc import Callable, Iterable
from typing import Literal

import torch

from app.core.config import Settings
from app.ml.catalog import CATALOG, ModelSpec
from app.ml.classifier import SentimentClassifier
from app.ml.device import describe_device, resolve_device

logger = logging.getLogger(__name__)

ModelStatus = Literal["not_loaded", "loading", "ready", "error"]
Loader = Callable[[ModelSpec, torch.device], SentimentClassifier]


class UnknownModelError(LookupError):
    pass


class ModelLoadError(RuntimeError):
    pass


class ModelRegistry:
    def __init__(self, settings: Settings, loader: Loader | None = None) -> None:
        self.settings = settings
        self.specs: dict[str, ModelSpec] = {m: CATALOG[m] for m in settings.enabled_models}
        self.device = resolve_device(settings.device)
        self.device_name = describe_device(self.device)
        self._loader = loader or self._load
        self._models: dict[str, SentimentClassifier] = {}
        self._errors: dict[str, str] = {}
        self._loading: set[str] = set()
        self._locks = {m: threading.Lock() for m in self.specs}

    # ------------------------------------------------------------------ lookup
    def spec(self, model_id: str | None) -> ModelSpec:
        key = model_id or self.settings.default_model
        try:
            return self.specs[key]
        except KeyError:
            raise UnknownModelError(
                f"Unknown model {key!r}. Available: {', '.join(self.specs)}"
            ) from None

    def status(self, model_id: str) -> ModelStatus:
        if model_id in self._models:
            return "ready"
        if model_id in self._loading:
            return "loading"
        if model_id in self._errors:
            return "error"
        return "not_loaded"

    def error(self, model_id: str) -> str | None:
        return self._errors.get(model_id)

    # ------------------------------------------------------------------ loading
    def get(self, model_id: str | None = None) -> SentimentClassifier:
        spec = self.spec(model_id)
        if (model := self._models.get(spec.id)) is not None:
            return model
        with self._locks[spec.id]:
            if (model := self._models.get(spec.id)) is not None:
                return model
            self._loading.add(spec.id)
            self._errors.pop(spec.id, None)
            try:
                model = self._loader(spec, self.device)
            except Exception as exc:
                message = _describe_load_error(spec, exc)
                logger.exception("could not load %s", spec.id)
                self._errors[spec.id] = message
                raise ModelLoadError(message) from exc
            else:
                # Publish before clearing "loading" so status never reads "not_loaded" in between.
                self._models[spec.id] = model
            finally:
                self._loading.discard(spec.id)
            logger.info("%s ready on %s", spec.id, self.device_name)
            return model

    def preload(self, model_ids: Iterable[str]) -> threading.Thread:
        """Load models in the background so the API can start serving immediately."""
        ids = list(model_ids)

        def run() -> None:
            for model_id in ids:
                # Failures are recorded in status(); the next request retries.
                with contextlib.suppress(ModelLoadError):
                    self.get(model_id)

        # Mark as loading right away so /api/health reflects it before the thread starts.
        self._loading.update(m for m in ids if m not in self._models)
        thread = threading.Thread(target=run, name="model-preload", daemon=True)
        thread.start()
        return thread

    def _load(self, spec: ModelSpec, device: torch.device) -> SentimentClassifier:
        return SentimentClassifier.load(
            spec,
            source=self.settings.model_sources.get(spec.id),
            device=device,
            max_length=self.settings.max_length,
            batch_size=self.settings.batch_size,
            cache_dir=self.settings.model_cache_dir,
        )


def _describe_load_error(spec: ModelSpec, exc: Exception) -> str:
    detail = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    hint = ""
    if isinstance(exc, OSError):
        hint = (
            " Check the internet connection to huggingface.co, or download the models first "
            "with `uv run python -m app.download` and set HF_HUB_OFFLINE=1."
        )
    return f"Couldn't load {spec.name}: {detail[:300]}{hint}"
