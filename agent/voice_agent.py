"""LiveKit voice agent for the AI Assistant.

    uv run python voice_agent.py dev      # local development (auto-reload)
    uv run python voice_agent.py start    # production

The API dispatches this agent (by VOICE_AGENT_NAME) into each voice room it
creates. Speech-to-text, text-to-speech and turn detection run on LiveKit
Inference; replies come from the app's API unless VOICE_LLM names another model.
"""

from dotenv import load_dotenv

load_dotenv(".env")  # LiveKit reads LIVEKIT_URL / _API_KEY / _API_SECRET from the environment

import asyncio
import json
import logging
from typing import Any

from livekit import agents, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
    inference,
    llm,
    room_io,
)
from livekit.plugins import ai_coustics

from app_llm import AppLLM
from settings import AgentSettings, get_settings

logger = logging.getLogger("voice-agent")
settings = get_settings()
server = AgentServer()

class Assistant(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)

class DictationAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a dictation agent. Only transcribe user speech.")
    
    async def on_user_turn_completed(self, _ctx: Any, _turn: Any) -> None:
        # Prevent any agent replies in dictation mode
        raise agents.StopResponse()

def parse_dispatch_metadata(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("ignoring malformed dispatch metadata")
        return {}
    return data if isinstance(data, dict) else {}

class RoomAttributes:
    def __init__(self, room: rtc.Room) -> None:
        self._room = room
        self._tasks: set[asyncio.Task[None]] = set()

    def set(self, values: dict[str, str]) -> None:
        task = asyncio.create_task(self._publish(values))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _publish(self, values: dict[str, str]) -> None:
        try:
            await self._room.local_participant.set_attributes(values)
        except Exception:
            logger.warning("could not publish agent attributes", exc_info=True)

    def on_meta(self, meta: dict[str, Any]) -> None:
        self.set(
            {
                "assistant.model": str(meta.get("model") or ""),
                "assistant.provider": str(meta.get("provider_label") or meta.get("provider") or ""),
                "assistant.local": "true" if meta.get("local") else "false",
                "assistant.notice": str(meta.get("notice") or ""),
                "assistant.error": "",
            }
        )

    def on_error(self, message: str) -> None:
        self.set({"assistant.error": message[:300]})

def build_llm(config: AgentSettings, room_name: str, attributes: RoomAttributes) -> llm.LLM:
    if config.voice_llm == "app":
        return AppLLM(
            api_url=config.api_url,
            room=room_name,
            timeout=config.api_timeout_seconds,
            token=config.voice_agent_token,
            on_meta=attributes.on_meta,
            on_error=attributes.on_error,
        )
    return inference.LLM(model=config.voice_llm)

def build_room_options(config: AgentSettings, mode: str = "chat") -> room_io.RoomOptions:
    if mode == "dictation":
        return room_io.RoomOptions() # Disable noise cancellation/ai_coustics for dictation
    if not config.voice_noise_cancellation:
        return room_io.RoomOptions()
    return room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=ai_coustics.audio_enhancement(
                model=ai_coustics.EnhancerModel.QUAIL_VF_S
            ),
        ),
    )

@server.rtc_session(agent_name=settings.voice_agent_name)
async def voice_session(ctx: agents.JobContext) -> None:
    metadata = parse_dispatch_metadata(ctx.job.metadata)
    mode = metadata.get("mode", "chat")
    attributes = RoomAttributes(ctx.room)
    room_name = ctx.job.room.name

    if mode == "dictation":
        # STT only
        session = AgentSession(
            stt=inference.STT(model=settings.voice_stt_model, language=settings.voice_stt_language),
            llm=None,
            tts=None,
            turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
        )
        agent = DictationAgent()
        room_options = build_room_options(settings, mode="dictation")
    else:
        # Chat mode
        session = AgentSession(
            stt=inference.STT(model=settings.voice_stt_model, language=settings.voice_stt_language),
            llm=build_llm(settings, room_name, attributes),
            tts=inference.TTS(
                model=settings.voice_tts_model,
                voice=metadata.get("voice") or settings.voice_tts_voice,
            ),
            turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
        )
        agent = Assistant(settings.voice_instructions)
        room_options = build_room_options(settings)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_options,
    )

    if mode != "dictation":
        # Only register interrupt for chat mode
        async def interrupt(_: rtc.RpcInvocationData) -> str:
            try:
                session.interrupt()
            except RuntimeError:
                logger.debug("nothing to interrupt")
            return "ok"
        ctx.room.local_participant.register_rpc_method("interrupt", interrupt)
        
        if settings.voice_greeting:
            session.say(settings.voice_greeting)

    logger.info("voice session started in %s mode=%s", room_name, mode)

if __name__ == "__main__":
    agents.cli.run_app(server)
