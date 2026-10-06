"""Request and response models shared by the API routes."""

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from app.images import ImageError, ImageMediaType, decode_image

Role = Literal["system", "user", "assistant"]


class ImageInput(BaseModel):
    """A photo attached to a user message: base64 bytes (a data: URL also works)."""

    media_type: ImageMediaType
    data: str = Field(min_length=8, repr=False)
    _bytes: bytes = PrivateAttr(default=b"")

    @model_validator(mode="after")
    def _decode(self) -> Self:
        try:
            raw, real_type = decode_image(self.data)
        except ImageError as exc:
            raise ValueError(str(exc)) from exc
        # Trust the file signature, not the declared type.
        self.media_type = real_type
        self._bytes = raw
        self.data = ""  # keep one copy in memory, not two
        return self

    @property
    def raw(self) -> bytes:
        return self._bytes

    @property
    def size(self) -> int:
        return len(self._bytes)


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(default="", max_length=200_000)
    images: list[ImageInput] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.images and self.role != "user":
            raise ValueError("Only user messages can have images")
        return self


# Hard ceilings checked before any image is decoded (the route applies the configured limits).
MAX_REQUEST_MESSAGES = 500
MAX_REQUEST_IMAGES = 100


class RagScope(BaseModel):
    """Answer from documents: Library collections and/or files added to this chat."""

    collections: list[str] = Field(default_factory=list, max_length=20)
    files: list[str] = Field(default_factory=list, max_length=50)
    # The chat the files belong to; files from other chats are ignored.
    chat_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_REQUEST_MESSAGES)
    rag: RagScope | None = Field(
        default=None, description="Search these collections/files and answer with citations"
    )
    provider: str | None = Field(
        default=None, description="Provider id, e.g. 'ollama' or 'openai'. Omit for automatic."
    )
    model: str | None = Field(default=None, description="Model id within the provider.")
    temperature: float | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="before")
    @classmethod
    def _count_images_first(cls, data: Any) -> Any:
        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list):
            total = sum(
                len(m["images"])
                for m in messages
                if isinstance(m, dict) and isinstance(m.get("images"), list)
            )
            if total > MAX_REQUEST_IMAGES:
                raise ValueError(f"Too many photos ({total}); the limit is {MAX_REQUEST_IMAGES}")
        return data


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    local: bool
    size_bytes: int | None = None
    parameter_size: str | None = None
    family: str | None = None
    vision: bool = Field(default=False, description="Can read images")


class ProviderStatus(BaseModel):
    id: str
    label: str
    local: bool
    configured: bool
    available: bool
    error: str | None = None
    models: list[ModelInfo] = Field(default_factory=list)


class ImageLimits(BaseModel):
    per_message: int
    per_request: int
    max_bytes: int


class ModelsResponse(BaseModel):
    providers: list[ProviderStatus]
    default: ModelInfo | None = None
    default_vision: ModelInfo | None = Field(
        default=None, description="What Auto uses when a message has images"
    )
    has_local_models: bool
    image_limits: ImageLimits | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
