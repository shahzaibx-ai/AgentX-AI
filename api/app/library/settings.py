"""Library (files and RAG) settings, read from environment variables and `.env`."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MB = 1024 * 1024


class LibrarySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "gemini" uses Gemini File Search (needs GEMINI_API_KEY). "offline" is a local
    # keyword-search stand-in for development and tests. Empty: gemini when a key is set.
    rag_engine: Literal["", "gemini", "offline"] = ""
    gemini_api_key: SecretStr | None = None  # shared with the Gemini chat provider

    # Model that answers questions about files. Must support File Search.
    rag_model: str = "gemini-3.8-flash"
    rag_embedding_model: str = ""  # empty = the service default, used when the store is created
    rag_chunk_tokens: int = Field(default=400, ge=50, le=2000)
    rag_chunk_overlap: int = Field(default=40, ge=0, le=500)
    rag_top_k: int = Field(default=6, ge=1, le=50)
    rag_store_name: str = "assistant-library"  # one File Search store for the whole app
    rag_index_timeout_seconds: float = Field(default=600, gt=0)
    rag_poll_seconds: float = Field(default=3, gt=0)
    rag_index_concurrency: int = Field(default=2, ge=1, le=8)

    # Where originals and the Library database live (relative to the API folder).
    library_data_dir: Path = Path("data/library")
    # Owner access to the Library pages and API. Required when ENVIRONMENT=production.
    # Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    library_token: SecretStr | None = None

    # Limits
    library_file_max_bytes: int = Field(default=100 * MB, ge=MB, le=100 * MB)  # File Search max
    chat_file_max_bytes: int = Field(default=25 * MB, ge=MB, le=100 * MB)
    chat_files_per_message: int = Field(default=10, ge=1, le=20)
    chat_file_retention_days: int = Field(default=30, ge=0)  # 0 = keep forever
    storage_quota_bytes: int = Field(default=50 * 1024 * MB, ge=MB)  # shown in Storage

    @property
    def engine_name(self) -> str:
        if self.rag_engine:
            return self.rag_engine
        key = self.gemini_api_key.get_secret_value() if self.gemini_api_key else ""
        return "gemini" if key else ""

    @property
    def enabled(self) -> bool:
        return bool(self.engine_name)
