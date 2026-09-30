from fastapi import APIRouter, Query

from app.deps import RegistryDep, SettingsDep
from app.schemas import ImageLimits, ModelsResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def list_models(
    registry: RegistryDep,
    settings: SettingsDep,
    refresh: bool = Query(default=False, description="Bypass the short-lived model cache"),
) -> ModelsResponse:
    """Local Ollama models plus models from every configured cloud provider."""
    response = await registry.models_response(refresh=refresh)
    response.image_limits = ImageLimits(
        per_message=settings.max_images_per_message,
        per_request=settings.max_images_per_request,
        max_bytes=settings.max_image_bytes,
    )
    return response
