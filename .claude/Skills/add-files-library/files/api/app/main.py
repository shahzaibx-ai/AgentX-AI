"""FastAPI application entry point.

Run locally:  uv run fastapi dev app/main.py
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.body_limit import BodySizeLimit
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.library import LibrarySettings, RagEngine, mount_library
from app.providers.registry import ProviderRegistry, build_providers
from app.routes import chat, health, models
from app.routes import stt

from app.voice import VoiceSettings, mount_voice
from app.voice_brain import chat_brain


def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
    voice_settings: VoiceSettings | None = None,
    library_settings: LibrarySettings | None = None,
    library_engine: RagEngine | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.registry = registry or ProviderRegistry(
            build_providers(settings), settings.model_cache_ttl_seconds, settings.vision_models
        )
        async with library_lifespan(app):
            yield
        await app.state.registry.aclose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    # Base64 adds a third; allow the photo budget plus room for the text.
    max_body = settings.max_images_per_request * settings.max_image_bytes * 4 // 3 + 8 * 1024 * 1024
    app.add_middleware(BodySizeLimit, max_bytes=max_body, paths=("/api/chat",))
    for router in (health.router, models.router, chat.router, stt.router):
        app.include_router(router, prefix="/api")
    # Files in chat + the Library (RAG with citations).
    library_settings = library_settings or LibrarySettings()
    app.add_middleware(
        BodySizeLimit,
        max_bytes=library_settings.chat_file_max_bytes + 1024 * 1024,
        paths=("/api/files",),
    )
    app.add_middleware(
        BodySizeLimit,
        max_bytes=library_settings.library_file_max_bytes * 10 + 1024 * 1024,
        paths=("/api/library/documents",),
    )
    library_lifespan = mount_library(
        app,
        settings=library_settings,
        engine=library_engine,
        production=settings.environment == "production",
    )
    mount_voice(app, brain=chat_brain, settings=voice_settings)  # voice mode (LiveKit)
    return app


app = create_app()
