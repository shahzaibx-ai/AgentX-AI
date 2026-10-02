from typing import Literal
from pydantic import BaseModel, Field

class VoiceMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(max_length=200_000)

class VoiceOptionInfo(BaseModel):
    id: str
    name: str
    description: str = ""

class VoiceConfigResponse(BaseModel):
    enabled: bool
    reason: str | None = None
    voices: list[VoiceOptionInfo] = Field(default_factory=list)

class VoiceSessionRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    voice: str | None = Field(default=None, description="Id from /api/voice/config voices")
    participant_name: str | None = Field(default=None, max_length=64)
    mode: Literal["chat", "dictation"] = "chat"
    history: list[VoiceMessage] = Field(
        default_factory=list,
        max_length=200,
        description="Earlier messages of the chat the voice session continues",
    )

class VoiceSessionResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    participant_identity: str

class VoiceChatRequest(BaseModel):
    """Sent by the voice agent: the spoken conversation so far."""
    room: str = Field(pattern=r"^voice-[0-9a-f]{32}$")
    messages: list[VoiceMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
