"""Voice sessions: LiveKit tokens, per-room context, and message clean-up.

The browser asks for a session; we create a fresh room, remember which model
and earlier chat messages it should use, and return a token that also
dispatches the voice agent into that room. The agent later sends the spoken
turns to `/api/voice/chat`, and we add the remembered context.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import timedelta
from threading import Lock

from livekit import api

from .schemas import VoiceMessage
from .settings import VoiceOption, VoiceSettings

MAX_STORED_SESSIONS = 5000


@dataclass
class VoiceContext:
    provider: str | None
    model: str | None
    history: list[VoiceMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)


class VoiceContextStore:
    """In-memory, TTL-bound store. Fine for one API process; use Redis when scaling out."""

    def __init__(self, ttl_seconds: float, max_entries: int = MAX_STORED_SESSIONS) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._items: dict[str, VoiceContext] = {}
        self._lock = Lock()

    def put(self, room: str, context: VoiceContext) -> None:
        with self._lock:
            self._prune()
            while len(self._items) >= self._max:
                self._items.pop(next(iter(self._items)))
            self._items[room] = context

    def get(self, room: str) -> VoiceContext | None:
        with self._lock:
            context = self._items.get(room)
            if context and time.monotonic() - context.created_at > self._ttl:
                del self._items[room]
                return None
            return context

    def _prune(self) -> None:
        now = time.monotonic()
        for room in [r for r, c in self._items.items() if now - c.created_at > self._ttl]:
            del self._items[room]

    def __len__(self) -> int:
        return len(self._items)


def find_voice(settings: VoiceSettings, voice_id: str | None) -> VoiceOption | None:
    if not voice_id:
        return None
    return next((v for v in settings.voice_voices if v.id == voice_id), None)


def trim_history(history: list[VoiceMessage], limit: int, max_chars: int) -> list[VoiceMessage]:
    kept = [m for m in history if m.role in ("user", "assistant") and m.content.strip()]
    if limit <= 0:
        return []
    return [VoiceMessage(role=m.role, content=m.content[:max_chars]) for m in kept[-limit:]]


def normalise_messages(messages: list[VoiceMessage]) -> list[VoiceMessage]:
    """Make a conversation every provider accepts.

    System messages go first (merged into one); empty turns are dropped;
    consecutive turns from the same speaker are merged (voice often splits one
    thought into several transcripts); and the conversation starts with the
    user, since some APIs (e.g. Anthropic) reject a leading assistant turn such
    as a spoken greeting.
    """
    system = [m for m in messages if m.role == "system" and m.content.strip()]
    turns: list[VoiceMessage] = []
    for m in messages:
        if m.role == "system" or not m.content.strip():
            continue
        if turns and turns[-1].role == m.role:
            turns[-1] = VoiceMessage(role=m.role, content=f"{turns[-1].content}\n\n{m.content}")
        else:
            turns.append(VoiceMessage(role=m.role, content=m.content))
    while turns and turns[0].role == "assistant":
        turns.pop(0)
    merged_system = (
        [VoiceMessage(role="system", content="\n\n".join(m.content for m in system))]
        if system
        else []
    )
    return [*merged_system, *turns]


def build_voice_messages(
    context: VoiceContext | None, messages: list[VoiceMessage], max_messages: int
) -> list[VoiceMessage]:
    """Agent instructions + earlier text chat + spoken turns, ready for the brain."""
    system = [m for m in messages if m.role == "system"]
    spoken = [m for m in messages if m.role != "system"]
    history = context.history if context else []
    combined = normalise_messages([*system, *history, *spoken])
    if not combined or combined[-1].role != "user":
        raise ValueError("The conversation must end with a user turn")
    if len(combined) > max_messages:
        head = combined[:1] if combined[0].role == "system" else []
        combined = [*head, *combined[len(combined) - (max_messages - len(head)) :]]
        combined = normalise_messages(combined)
    return combined


def create_participant_token(
    settings: VoiceSettings,
    *,
    room: str,
    identity: str,
    name: str,
    agent_metadata: dict,
) -> str:
    """A token for one room whose room configuration dispatches the voice agent."""
    assert settings.livekit_api_key and settings.livekit_api_secret  # guarded by .enabled
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    dispatch = api.RoomAgentDispatch(
        agent_name=settings.voice_agent_name,
        metadata=json.dumps(agent_metadata, separators=(",", ":")),
    )
    return (
        api.AccessToken(
            settings.livekit_api_key.get_secret_value(),
            settings.livekit_api_secret.get_secret_value(),
        )
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_room_config(api.RoomConfiguration(agents=[dispatch]))
        .with_ttl(timedelta(seconds=settings.voice_token_ttl_seconds))
        .to_jwt()
    )
