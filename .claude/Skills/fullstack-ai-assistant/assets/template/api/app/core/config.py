"""Application settings, loaded from environment variables and `.env`."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AI Assistant API"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    system_prompt: str = (
        "You are a helpful, accurate and concise AI assistant. "
        "Use Markdown for structure when it helps readability."
    )

    # Behaviour
    allow_cloud_fallback: bool = True
    request_timeout_seconds: float = 120.0
    model_cache_ttl_seconds: float = 30.0
    max_messages: int = 100
    max_message_chars: int = 32_000

    # Local: Ollama (always tried first)
    ollama_host: str = "http://localhost:11434"
    ollama_enabled: bool = True

    # Cloud fallbacks, tried in this order. A provider is enabled when its key is set.
    cloud_priority: list[str] = Field(
        default_factory=lambda: ["anthropic", "openai", "gemini", "grok", "meta"]
    )

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = ""

    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = ""

    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = ""

    grok_api_key: SecretStr | None = None
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = ""

    meta_api_key: SecretStr | None = None
    meta_base_url: str = "https://api.llama.com/compat/v1/"
    meta_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
