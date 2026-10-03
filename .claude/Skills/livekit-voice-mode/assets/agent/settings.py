"""Voice agent settings, read from environment variables and `.env`.

LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET are read by the LiveKit
SDK itself (voice_agent.py loads `.env` into the environment first).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_INSTRUCTIONS = """You are a helpful voice AI assistant.
You eagerly assist users with their questions by providing information from your extensive knowledge.
You are curious, friendly, and have a sense of humor.
Your replies are spoken aloud, so keep them concise and conversational: usually one to three sentences unless the user asks for detail.
Never use markdown, lists, code blocks, emojis, asterisks or other symbols. Spell out anything that is hard to read aloud."""  # noqa: E501


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Must match VOICE_AGENT_NAME in the API, which dispatches this agent into rooms.
    voice_agent_name: str = "my-agent"

    # "app" = answer through the app's API (model dropdown, Ollama first, cloud fallback).
    # Any other value is a LiveKit Inference model id, e.g. "google/gemma-4-31b-it".
    voice_llm: str = "app"
    api_url: str = "http://localhost:8000"
    api_timeout_seconds: float = 120.0
    # Same value as VOICE_AGENT_TOKEN in the API's .env (sent as a Bearer token). Optional.
    voice_agent_token: str = ""

    voice_stt_model: str = "assemblyai/universal-3-5-pro"
    voice_stt_language: str = "en"
    voice_tts_model: str = "fishaudio/s2.1-pro"
    voice_tts_voice: str = "fa4c9eb3dccc4806b382b40d61c6b10a"
    voice_noise_cancellation: bool = True

    voice_instructions: str = DEFAULT_INSTRUCTIONS
    # Spoken when the session starts. Empty = wait for the user to speak first.
    voice_greeting: str = "Hi! What can I help you with?"


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
