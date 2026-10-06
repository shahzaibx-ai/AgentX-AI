"""Files in chat and the Library (RAG over your documents), as one package.

    from app.library import mount_library
    mount_library(app)                    # adds /api/files/* and /api/library/*
    service = app.state.library           # LibraryService, for the chat route

The search engine sits behind the `RagEngine` protocol (engine.py). Today it is
Gemini File Search (gemini.py); RAG_ENGINE=offline swaps in a local keyword
stand-in for development and tests. A LangChain/LangGraph engine plugs in the
same way.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from .engine import NOT_FOUND, Answer, Delta, RagEngine, RagError, Source, Turn
from .routes import LibraryRoutes
from .service import LibraryService, SourceOut
from .settings import LibrarySettings

__all__ = [
    "NOT_FOUND",
    "Answer",
    "Delta",
    "LibraryService",
    "LibrarySettings",
    "RagEngine",
    "RagError",
    "Source",
    "SourceOut",
    "Turn",
    "build_engine",
    "mount_library",
]

logger = logging.getLogger(__name__)


def build_engine(settings: LibrarySettings) -> RagEngine | None:
    name = settings.engine_name
    if not name:
        return None
    from .gemini import GeminiFileSearchEngine

    if name == "offline":
        from .offline import OfflineClient

        client: Any = OfflineClient()
        poll = 0.0
    else:
        from google import genai

        key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
        if not key:
            raise RagError("RAG_ENGINE=gemini needs GEMINI_API_KEY")
        # vertexai=False: File Search is a Gemini Developer API feature.
        client = genai.Client(api_key=key, vertexai=False)
        poll = settings.rag_poll_seconds
    return GeminiFileSearchEngine(
        client,
        # The offline stand-in has no model; don't show a Gemini name for it.
        model=settings.rag_model if name == "gemini" else "offline-keyword-search",
        embedding_model=settings.rag_embedding_model,
        chunk_tokens=settings.rag_chunk_tokens,
        chunk_overlap=settings.rag_chunk_overlap,
        top_k=settings.rag_top_k,
        poll_seconds=poll or 0.01,
        timeout_seconds=settings.rag_index_timeout_seconds,
        name=name,
    )


def mount_library(
    app: FastAPI,
    *,
    settings: LibrarySettings | None = None,
    engine: RagEngine | None = None,
    production: bool = False,
    prefix: str = "/api",
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Adds the routes and returns a lifespan helper that starts/stops the worker.

    Use it inside the app's lifespan: `async with lifespan_library(app): ...`.
    """
    settings = settings or LibrarySettings()
    problem: str | None = None
    if engine is None:
        # Never let the Library stop the API (chat, models and voice mode must keep
        # working): a missing package or bad setting turns the Library off with a reason.
        try:
            engine = build_engine(settings)
        except ModuleNotFoundError as exc:
            missing = exc.name or "google.genai"
            package = "google-genai" if missing.startswith("google") else missing
            problem = (
                f"The Library needs the {package} package. "
                "Run `uv sync` in the API folder and restart it."
            )
        except RagError as exc:
            problem = str(exc)
        except Exception as exc:  # e.g. an invalid key format rejected by the SDK
            logger.exception("Files and the Library could not start")
            problem = f"Files and the Library could not start: {exc}"
        if problem:
            logger.error("Files and the Library are off: %s", problem)
    service = LibraryService(settings, engine, problem=problem)
    app.state.library = service
    app.include_router(LibraryRoutes(service, settings, production).router(), prefix=prefix)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            await service.start()
        except Exception as exc:  # e.g. an unwritable LIBRARY_DATA_DIR
            logger.exception("Files and the Library could not start")
            service.disable(f"Files and the Library could not start: {exc}")
        try:
            yield
        finally:
            await service.stop()

    return lifespan
