"""LiveKit voice agent for the AI Assistant.

    uv run python voice_agent.py dev      # local development (auto-reload)
    uv run python voice_agent.py start    # production

The API dispatches this agent (by VOICE_AGENT_NAME) into each voice room it
creates. Speech-to-text, text-to-speech and turn detection run on LiveKit
Inference; replies come from the app's API unless VOICE_LLM names another model.
"""

from dotenv import load_dotenv

load_dotenv(".env")  # LiveKit reads LIVEKIT_URL / _API_KEY / _API_SECRET from the environment

import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from typing import Any  # noqa: E402

from livekit import agents, rtc  # noqa: E402
from livekit.agents import (  # noqa: E402
    Agent,
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
    inference,
    llm,
    room_io,
)
from livekit.plugins import ai_coustics  # noqa: E402

from app_llm import AppLLM  # noqa: E402
from settings import AgentSettings, get_settings  # noqa: E402

logger = logging.getLogger("voice-agent")
settings = get_settings()
server = AgentServer()


class Assistant(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)


def parse_dispatch_metadata(raw: str | None) -> dict[str, Any]:
    """Metadata the API attached to the dispatch, e.g. {"voice": "<tts voice id>"}."""
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("ignoring malformed dispatch metadata")
        return {}
    return data if isinstance(data, dict) else {}


class RoomAttributes:
    """Publishes reply details as agent attributes so the web UI can show them.

    assistant.model / assistant.provider / assistant.local: who is answering.
    assistant.notice: why a fallback model was used.  assistant.error: last failure.
    """

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


def build_room_options(config: AgentSettings) -> room_io.RoomOptions:
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
    attributes = RoomAttributes(ctx.room)
    room_name = ctx.job.room.name

    session = AgentSession(
        stt=inference.STT(model=settings.voice_stt_model, language=settings.voice_stt_language),
        llm=build_llm(settings, room_name, attributes),
        tts=inference.TTS(
            model=settings.voice_tts_model,
            voice=metadata.get("voice") or settings.voice_tts_voice,
        ),
        turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(settings.voice_instructions),
        room_options=build_room_options(settings),
    )

    # The web app's Stop button: cut the current reply short.
    async def interrupt(_: rtc.RpcInvocationData) -> str:
        try:
            session.interrupt()
        except RuntimeError:
            logger.debug("nothing to interrupt")
        return "ok"

    ctx.room.local_participant.register_rpc_method("interrupt", interrupt)
    logger.info("voice session started in %s", room_name)

    if settings.voice_greeting:
        session.say(settings.voice_greeting)


if __name__ == "__main__":
    agents.cli.run_app(server)
