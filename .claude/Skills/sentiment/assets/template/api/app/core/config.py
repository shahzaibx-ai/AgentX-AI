"""Settings, read from environment variables and `api/.env`.

Lists and dicts are JSON in env vars, e.g.
    ENABLED_MODELS='["ProsusAI/finbert"]'
    MODEL_SOURCES='{"ProsusAI/finbert": "/models/finbert"}'
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ml.catalog import CATALOG, DEFAULT_MODEL_ID


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=()
    )

    app_name: str = "Sentiment Studio API"
    environment: Literal["development", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Models
    default_model: str = DEFAULT_MODEL_ID
    enabled_models: list[str] = Field(default_factory=lambda: list(CATALOG))
    preload_models: list[str] = Field(default_factory=lambda: [DEFAULT_MODEL_ID])
    model_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Load a model from a local folder instead of the Hugging Face Hub.",
    )
    model_cache_dir: str | None = None

    # Runtime
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    torch_threads: int | None = Field(default=None, ge=1)
    max_length: int = Field(default=512, ge=16, le=512)
    batch_size: int = Field(default=32, ge=1, le=256)

    # Request limits
    max_text_chars: int = Field(default=5000, ge=1, le=100_000)
    max_batch_items: int = Field(default=1000, ge=1, le=10_000)

    # Explanations (integrated gradients). 0 turns them off.
    explain_steps: int = Field(default=16, ge=0, le=200)
    low_confidence: float = Field(default=0.6, gt=0, lt=1)

    @model_validator(mode="after")
    def _check_models(self) -> Self:
        unknown = [m for m in self.enabled_models if m not in CATALOG]
        if unknown:
            raise ValueError(f"Unknown models in ENABLED_MODELS: {unknown}. Known: {list(CATALOG)}")
        if not self.enabled_models:
            raise ValueError("ENABLED_MODELS must list at least one model")
        if self.default_model not in self.enabled_models:
            raise ValueError(f"DEFAULT_MODEL {self.default_model!r} is not in ENABLED_MODELS")
        missing = [m for m in self.preload_models if m not in self.enabled_models]
        if missing:
            raise ValueError(f"PRELOAD_MODELS must be enabled models: {missing}")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
