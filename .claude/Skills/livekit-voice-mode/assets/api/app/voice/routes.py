import json
import logging
import secrets
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from .brain import Brain, BrainRequest
from .schemas import (
    VoiceChatRequest,
    VoiceConfigResponse,
    VoiceOptionInfo,
    VoiceSessionRequest,
    VoiceSessionResponse,
)
from .service import (
    VoiceContext,
    VoiceContextStore,
    build_voice_messages,
    create_participant_token,
    find_voice,
    trim_history,
)
from .settings import VoiceSettings

logger = logging.getLogger(__name__)

NOT_CONFIGURED = (
    "Voice mode isn't set up. Add LIVEKIT_URL, LIVEKIT_API_KEY and "
    "LIVEKIT_API_SECRET to the API's .env and start the voice agent."
)
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def mount_voice(
    app: FastAPI,
    brain: Brain,
    settings: VoiceSettings | None = None,
    prefix: str = "/api/voice",
) -> None:
    """Add the voice endpoints to `app`. Call once, when creating the app."""
    settings = settings or VoiceSettings()
    app.state.voice_settings = settings
    app.state.voice_store = VoiceContextStore(settings.voice_context_ttl_seconds)
    app.state.voice_brain = brain
    app.include_router(router, prefix=prefix)


def _settings(request: Request) -> VoiceSettings:
    return request.app.state.voice_settings


def _store(request: Request) -> VoiceContextStore:
    return request.app.state.voice_store


SettingsDep = Annotated[VoiceSettings, Depends(_settings)]
StoreDep = Annotated[VoiceContextStore, Depends(_store)]


def _require_agent(request: Request, settings: SettingsDep) -> None:
    """Only the voice agent may call /chat when VOICE_AGENT_TOKEN is set."""
    token = settings.voice_agent_token.get_secret_value() if settings.voice_agent_token else ""
    if not token:
        return
    sent = request.headers.get("authorization", "")
    if not secrets.compare_digest(sent.encode(), f"Bearer {token}".encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid voice agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(tags=["voice"])


def _sse(name: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n" if name == "delta" else f"event: {name}\ndata: {payload}\n\n"


@router.get("/config", response_model=VoiceConfigResponse)
async def voice_config(settings: SettingsDep) -> VoiceConfigResponse:
    """Whether voice mode is available, and the voices users can pick from."""
    return VoiceConfigResponse(
        enabled=settings.enabled,
        reason=None if settings.enabled else NOT_CONFIGURED,
        voices=[
            VoiceOptionInfo(id=v.id, name=v.name, description=v.description)
            for v in settings.voice_voices
        ],
    )


@router.post("/session", response_model=VoiceSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_session(
    body: VoiceSessionRequest, settings: SettingsDep, store: StoreDep
) -> VoiceSessionResponse:
    """Create a room for one voice conversation and a token that brings the agent in."""
    if not settings.enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED)

    voice = find_voice(settings, body.voice)
    if body.voice and voice is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown voice '{body.voice}'")

    room = f"voice-{uuid4().hex}"
    identity = f"user-{uuid4().hex[:12]}"
    store.put(
        room,
        VoiceContext(
            provider=body.provider,
            model=body.model,
            history=trim_history(
                body.history, settings.voice_history_messages, settings.voice_max_message_chars
            ),
        ),
    )
    token = create_participant_token(
        settings,
        room=room,
        identity=identity,
        name=(body.participant_name or "Guest").strip() or "Guest",
        agent_metadata={"voice": voice.tts_voice if voice else None},
    )
    logger.info("Voice session created: room=%s provider=%s", room, body.provider or "auto")
    return VoiceSessionResponse(
        server_url=settings.livekit_url,
        participant_token=token,
        room_name=room,
        participant_identity=identity,
    )


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
    dependencies=[Depends(_require_agent)],
)
async def voice_chat(
    body: VoiceChatRequest, request: Request, settings: SettingsDep, store: StoreDep
) -> StreamingResponse:
    """Used by the voice agent. Streams the reply as server-sent events.

    Adds the model the user picked and the earlier chat messages remembered for
    this room. An unknown or expired room falls back to automatic model choice.
    """
    context = store.get(body.room)
    try:
        messages = build_voice_messages(context, body.messages, settings.voice_max_messages)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if any(len(m.content) > settings.voice_max_message_chars for m in messages):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Message is too long")

    brain: Brain = request.app.state.voice_brain
    brain_request = BrainRequest(
        messages=[m.model_dump() for m in messages],
        provider=context.provider if context else None,
        model=context.model if context else None,
        temperature=body.temperature,
    )

    async def events() -> AsyncIterator[str]:
        try:
            async for name, data in brain(request, brain_request):
                if await request.is_disconnected():
                    break
                yield _sse(name, data)
        except Exception:
            logger.exception("voice brain failed")
            yield _sse("error", {"message": "The assistant failed to answer."})

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
