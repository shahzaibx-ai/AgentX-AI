"""Request and response models shared by the API routes."""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(max_length=200_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    provider: str | None = Field(
        default=None, description="Provider id, e.g. 'ollama' or 'openai'. Omit for automatic."
    )
    model: str | None = Field(default=None, description="Model id within the provider.")
    temperature: float | None = Field(default=None, ge=0, le=2)


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    local: bool
    size_bytes: int | None = None
    parameter_size: str | None = None
    family: str | None = None


class ProviderStatus(BaseModel):
    id: str
    label: str
    local: bool
    configured: bool
    available: bool
    error: str | None = None
    models: list[ModelInfo] = Field(default_factory=list)


class ModelsResponse(BaseModel):
    providers: list[ProviderStatus]
    default: ModelInfo | None = None
    has_local_models: bool


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
