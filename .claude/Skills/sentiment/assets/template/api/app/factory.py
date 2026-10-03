"""Application factory (tests build apps with their own settings)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import Settings, get_settings
from app.ml.registry import ModelRegistry
from app.routes import health, models, predict

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")


def create_app(settings: Settings | None = None, registry: ModelRegistry | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.torch_threads:
            torch.set_num_threads(settings.torch_threads)
        if settings.preload_models:
            app.state.registry.preload(settings.preload_models)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Sentiment analysis with PyTorch and Hugging Face Transformers.",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.registry = registry or ModelRegistry(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    for router in (health.router, models.router, predict.router):
        app.include_router(router, prefix="/api")
    return app
