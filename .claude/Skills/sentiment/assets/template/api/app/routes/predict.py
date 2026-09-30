"""Prediction endpoints.

Handlers are plain `def`: FastAPI runs them in a worker thread, so PyTorch work
never blocks the event loop.
"""

import time

from fastapi import APIRouter, HTTPException, status

from app.deps import RegistryDep, SettingsDep
from app.ml.classifier import SentimentClassifier
from app.ml.registry import ModelLoadError, ModelRegistry, UnknownModelError
from app.schemas import (
    BatchItem,
    BatchPredictRequest,
    BatchPredictResponse,
    Prediction,
    PredictRequest,
    PredictResponse,
)

router = APIRouter(tags=["predict"])


def _classifier(registry: ModelRegistry, model_id: str | None) -> SentimentClassifier:
    try:
        return registry.get(model_id)
    except UnknownModelError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ModelLoadError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


def _too_long(settings_limit: int, length: int, what: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"{what} has {length:,} characters; the limit is {settings_limit:,}",
    )


@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest, registry: RegistryDep, settings: SettingsDep) -> PredictResponse:
    if len(body.text) > settings.max_text_chars:
        raise _too_long(settings.max_text_chars, len(body.text), "The text")
    classifier = _classifier(registry, body.model)
    started = time.perf_counter()
    (result,) = classifier.predict(
        [body.text], explain=body.explain, explain_steps=settings.explain_steps
    )
    latency = (time.perf_counter() - started) * 1000
    return PredictResponse(
        **Prediction.model_validate(result).model_dump(),
        model=classifier.spec.id,
        device=registry.device_name,
        latency_ms=round(latency, 1),
    )


@router.post("/predict/batch", response_model=BatchPredictResponse)
def predict_batch(
    body: BatchPredictRequest, registry: RegistryDep, settings: SettingsDep
) -> BatchPredictResponse:
    if len(body.texts) > settings.max_batch_items:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{len(body.texts):,} texts sent; "
            f"the limit is {settings.max_batch_items:,} per request",
        )
    for i, text in enumerate(body.texts):
        if len(text) > settings.max_text_chars:
            raise _too_long(settings.max_text_chars, len(text), f"Row {i + 1}")
    classifier = _classifier(registry, body.model)
    started = time.perf_counter()
    results = classifier.predict(body.texts)
    latency = (time.perf_counter() - started) * 1000
    return BatchPredictResponse(
        model=classifier.spec.id,
        device=registry.device_name,
        latency_ms=round(latency, 1),
        results=[BatchItem.model_validate(r) for r in results],
    )
