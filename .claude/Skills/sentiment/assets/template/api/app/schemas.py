"""Request and response models (mirrored in web/lib/types.ts)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ModelStatus = Literal["not_loaded", "loading", "ready", "error"]


# ---------------------------------------------------------------- requests
class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000, examples=["The battery life is fantastic."])
    model: str | None = Field(default=None, description="Model id; omit for the default model")
    explain: bool = Field(default=True, description="Include word-level attributions")

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text is empty")
        return value


class BatchPredictRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=10_000)
    model: str | None = None

    @field_validator("texts")
    @classmethod
    def _no_blank_rows(cls, values: list[str]) -> list[str]:
        for i, value in enumerate(values):
            if not value.strip():
                raise ValueError(f"Row {i + 1} is empty")
        return values


class LoadModelRequest(BaseModel):
    model: str


# ---------------------------------------------------------------- responses
class LabelScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    score: float
    logit: float


class Attribution(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    weight: float = Field(description="-1 pushes toward negative, +1 toward positive")


class Prediction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    score: float
    probs: list[LabelScore] = Field(description="Every class, from most negative to most positive")
    tokens: list[str]
    num_tokens: int
    truncated: bool
    attributions: list[Attribution] | None = None


class PredictResponse(Prediction):
    model: str
    device: str
    latency_ms: float


class BatchItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    score: float
    probs: list[LabelScore]
    num_tokens: int
    truncated: bool


class BatchPredictResponse(BaseModel):
    model: str
    device: str
    latency_ms: float
    results: list[BatchItem]


class ModelInfo(BaseModel):
    id: str
    name: str
    domain: str
    description: str
    languages: str
    parameters: str
    architecture: str
    labels: list[str] = Field(description="From most negative to most positive")
    revision: str
    default: bool
    status: ModelStatus
    error: str | None = None


class Limits(BaseModel):
    max_length: int
    max_text_chars: int
    max_batch_items: int
    batch_size: int
    explain_steps: int
    low_confidence: float


class ModelsResponse(BaseModel):
    default_model: str
    device: str
    limits: Limits
    models: list[ModelInfo]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    device: str
    models: dict[str, ModelStatus]
