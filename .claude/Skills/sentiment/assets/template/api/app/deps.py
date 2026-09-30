from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.ml.registry import ModelRegistry


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RegistryDep = Annotated[ModelRegistry, Depends(get_registry)]
