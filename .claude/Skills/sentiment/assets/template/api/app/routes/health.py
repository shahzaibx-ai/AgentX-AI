from fastapi import APIRouter

from app import __version__
from app.deps import RegistryDep
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(registry: RegistryDep) -> HealthResponse:
    return HealthResponse(
        version=__version__,
        device=registry.device_name,
        models={model_id: registry.status(model_id) for model_id in registry.specs},
    )
