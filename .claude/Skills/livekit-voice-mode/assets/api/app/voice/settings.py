"""Voice settings, read from environment variables and `.env`."""

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceOption(BaseModel):
    """A text-to-speech voice users can pick in the voice settings menu."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")
    name: str
    description: str = ""
    tts_voice: str = Field(description="Voice id passed to the agent's TTS model")


class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Enabled when URL, key and secret are all set (same LiveKit project as the agent).
    livekit_url: str = ""
    livekit_api_key: SecretStr | None = None
    livekit_api_secret: SecretStr | None = None

    voice_agent_name: str = "my-agent"  # must match the agent's VOICE_AGENT_NAME
    # Optional shared secret. When set, POST /chat (called by the agent) requires
    # "Authorization: Bearer <token>"; set the same VOICE_AGENT_TOKEN in agent/.env.
    # Use it whenever the API is reachable from the internet.
    voice_agent_token: SecretStr | None = None
    voice_token_ttl_seconds: int = 900
    voice_context_ttl_seconds: int = 3600
    voice_history_messages: int = 20
    voice_max_messages: int = 100
    voice_max_message_chars: int = 32_000
    # Optional picker, e.g. [{"id":"calm","name":"Calm","tts_voice":"<voice id>"}].
    voice_voices: list[VoiceOption] = Field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return bool(
            self.livekit_url
            and self.livekit_api_key
            and self.livekit_api_key.get_secret_value()
            and self.livekit_api_secret
            and self.livekit_api_secret.get_secret_value()
        )
