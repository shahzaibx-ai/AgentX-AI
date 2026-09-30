from livekit.agents import inference

import voice_agent
from app_llm import AppLLM
from settings import AgentSettings


def test_dispatch_metadata_is_parsed_defensively():
    assert voice_agent.parse_dispatch_metadata('{"voice": "abc"}') == {"voice": "abc"}
    assert voice_agent.parse_dispatch_metadata("") == {}
    assert voice_agent.parse_dispatch_metadata(None) == {}
    assert voice_agent.parse_dispatch_metadata("not json") == {}
    assert voice_agent.parse_dispatch_metadata("[1, 2]") == {}


def test_agent_is_registered_under_configured_name():
    assert voice_agent.server is not None
    # The module-level settings are what the worker registers with (read at import).
    assert voice_agent.settings.voice_agent_name


async def test_llm_choice_follows_settings(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-that-is-at-least-32-bytes")
    attrs = voice_agent.RoomAttributes(room=None)  # callbacks are not invoked here
    app = voice_agent.build_llm(AgentSettings(_env_file=None), "voice-x", attrs)
    assert isinstance(app, AppLLM)
    assert app.url == "http://localhost:8000/api/voice/chat"
    await app.aclose()

    direct = voice_agent.build_llm(
        AgentSettings(_env_file=None, voice_llm="google/gemma-4-31b-it"), "voice-x", attrs
    )
    assert isinstance(direct, inference.LLM)


def test_noise_cancellation_can_be_disabled():
    on = voice_agent.build_room_options(AgentSettings(_env_file=None))
    off = voice_agent.build_room_options(
        AgentSettings(_env_file=None, voice_noise_cancellation=False)
    )
    assert on.audio_input is not None
    assert off.audio_input != on.audio_input


def test_defaults_match_the_original_agent():
    s = AgentSettings(_env_file=None)
    assert s.voice_stt_model == "assemblyai/universal-3-5-pro"
    assert s.voice_stt_language == "en"
    assert s.voice_tts_model == "fishaudio/s2.1-pro"
    assert s.voice_tts_voice == "fa4c9eb3dccc4806b382b40d61c6b10a"
    assert s.voice_agent_name == "my-agent"
