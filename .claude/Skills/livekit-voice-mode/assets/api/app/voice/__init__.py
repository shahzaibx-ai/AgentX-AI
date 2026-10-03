"""Voice mode (LiveKit) for FastAPI — a self-contained, drop-in package.

The host app provides one thing, a *brain*: an async generator that streams a
chat reply as ("meta" | "delta" | "error" | "done", data) events. Then:

    from app.voice import mount_voice
    mount_voice(app, brain=my_brain)

adds GET /api/voice/config, POST /api/voice/session and POST /api/voice/chat.
Settings come from the environment (LIVEKIT_URL, LIVEKIT_API_KEY,
LIVEKIT_API_SECRET, VOICE_*). Imports are relative, so the folder can be copied
into any FastAPI project.
"""

from .brain import Brain, BrainEvent, BrainRequest
from .routes import mount_voice
from .settings import VoiceOption, VoiceSettings

__all__ = ["Brain", "BrainEvent", "BrainRequest", "VoiceOption", "VoiceSettings", "mount_voice"]
