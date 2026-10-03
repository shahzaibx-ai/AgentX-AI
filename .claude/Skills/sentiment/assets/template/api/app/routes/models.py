from fastapi import APIRouter, HTTPException, status

from app.deps import RegistryDep, SettingsDep
from app.ml.catalog import ModelSpec
from app.ml.registry import ModelLoadError, ModelRegistry, UnknownModelError
from app.schemas import Limits, LoadModelRequest, ModelInfo, ModelsResponse

router = APIRouter(tags=["models"])


def model_info(spec: ModelSpec, registry: ModelRegistry) -> ModelInfo:
    return ModelInfo(
        id=spec.id,
        name=spec.name,
        domain=spec.domain,
        description=spec.description,
        languages=spec.languages,
        parameters=spec.parameters,
        architecture=spec.architecture,
        labels=[spec.labels[i] for i in spec.display_order],
        revision=spec.revision,
        default=spec.id == registry.settings.default_model,
        status=registry.status(spec.id),
        error=registry.error(spec.id),
    )


# Status endpoints are async: they only read in-memory state, and must stay responsive
# while prediction requests occupy the worker threads.
@router.get("/models", response_model=ModelsResponse)
async def list_models(registry: RegistryDep, settings: SettingsDep) -> ModelsResponse:
    return ModelsResponse(
        default_model=settings.default_model,
        device=registry.device_name,
        limits=Limits(
            max_length=settings.max_length,
            max_text_chars=settings.max_text_chars,
            max_batch_items=settings.max_batch_items,
            batch_size=settings.batch_size,
            explain_steps=settings.explain_steps,
            low_confidence=settings.low_confidence,
        ),
        models=[model_info(spec, registry) for spec in registry.specs.values()],
    )


@router.post("/models/load", response_model=ModelInfo)
def load_model(body: LoadModelRequest, registry: RegistryDep) -> ModelInfo:
    """Load a model now (it is otherwise loaded on first use)."""
    try:
        spec = registry.spec(body.model)
        registry.get(spec.id)
    except UnknownModelError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ModelLoadError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return model_info(spec, registry)
