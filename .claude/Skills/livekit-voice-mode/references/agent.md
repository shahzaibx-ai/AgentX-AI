# The voice agent (`agent/`)

A standalone uv project (Python 3.13) built on `livekit-agents~=1.8` and
`livekit-plugins-ai-coustics`.

```
agent/
  voice_agent.py   AgentServer + @server.rtc_session(agent_name=VOICE_AGENT_NAME)
  app_llm.py       AppLLM: an llm.LLM that streams from the API's /api/voice/chat
  settings.py      AgentSettings (env / .env)
  tests/           no network: settings, dispatch metadata, AppLLM against httpx.MockTransport
  Dockerfile       uv image; downloads plugin model files at build; health on :8081
```

Commands (from `agent/`):

```bash
uv sync
uv run python voice_agent.py download-files   # once: model files for plugins
uv run python voice_agent.py dev              # development, auto-reload
uv run python voice_agent.py start            # production
uv run python voice_agent.py console          # talk to it in the terminal (no web app)
```

`voice_agent.py` calls `load_dotenv(".env")` **before** any other import,
because LiveKit's `inference.*` classes read `LIVEKIT_API_KEY/SECRET` from the
environment when they're constructed. Run it from `agent/`, or export the
variables yourself.

## Settings (`agent/.env`)

| Variable | Default | Notes |
|---|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | — | Same project as the API |
| `VOICE_AGENT_NAME` | `my-agent` | Must equal the API's; the API dispatches by this name |
| `VOICE_LLM` | `app` | `app` = reply through the API (model dropdown + fallback). Anything else is a LiveKit Inference model id (e.g. `google/gemma-4-31b-it`) and bypasses the app |
| `API_URL` | `http://localhost:8000` | Where the agent reaches the API (Compose: `http://api:8000`) |
| `API_TIMEOUT_SECONDS` | 120 | Per reply |
| `VOICE_STT_MODEL` / `VOICE_STT_LANGUAGE` | `assemblyai/universal-3-5-pro` / `en` | LiveKit Inference STT |
| `VOICE_TTS_MODEL` / `VOICE_TTS_VOICE` | `fishaudio/s2.1-pro` / `fa4c9eb3dccc4806b382b40d61c6b10a` | LiveKit Inference TTS; the web voice picker can override the voice per session |
| `VOICE_NOISE_CANCELLATION` | `true` | ai-coustics on the user's mic (LiveKit Cloud only) |
| `VOICE_GREETING` | `Hi! What can I help you with?` | Empty = wait for the user to speak first |
| `VOICE_INSTRUCTIONS` | concise, spoken, no markdown | The system prompt for voice (sent to the API as the first message) |

## Common customisations

**Another language.** Set `VOICE_STT_LANGUAGE` (e.g. `es`), pick an STT model
and a TTS voice that support it, and translate `VOICE_GREETING` and
`VOICE_INSTRUCTIONS`. Check that the turn detector supports the language too
(LiveKit publishes its supported-language list).

**A voice picker.** In `api/.env`:

```
VOICE_VOICES=[{"id":"calm","name":"Calm","description":"Even and relaxed","tts_voice":"<tts voice id>"},
              {"id":"bright","name":"Bright","description":"Upbeat","tts_voice":"<tts voice id>"}]
```

The web shows them in the settings menu. The choice travels as dispatch
metadata `{"voice": tts_voice}`, and the agent uses it for `inference.TTS(voice=…)`.

**Personality or domain.** Edit `VOICE_INSTRUCTIONS`, and keep the spoken-style
rules: short answers, no markdown, lists, emoji or symbols. For long texts,
set it in `settings.py`'s `DEFAULT_INSTRUCTIONS` instead of `.env`.

**Tools / function calling.** With `VOICE_LLM=app`, the API's brain decides
what the model can do, so add tools there (they then work for typed chat too).
`AppLLM` ignores LiveKit `function_tool`s. With an Inference model
(`VOICE_LLM=<model id>`), define `@function_tool` methods on the `Assistant`
class as usual.

**Different speech providers.** Replace `inference.STT/TTS` in
`voice_session` with provider plugins (`livekit-plugins-<provider>`). Keep the
`llm=build_llm(...)` line, so replies still come from the app.

**Self-hosted LiveKit (no Cloud).** LiveKit Inference and ai-coustics need
LiveKit Cloud. On your own server: set `VOICE_NOISE_CANCELLATION=false`; use
provider plugins for STT and TTS with your own API keys; and for turn
detection, use a VAD-based setup or the turn-detector plugin. Check the current
LiveKit Agents docs for the exact plugin names and options, since they change
between releases.

**Push-to-talk.** Not included. `session.commit_user_turn()` exists, but with
automatic turn detection on it can double-reply. Build it as a separate mode:
`turn_detection="manual"` plus `start_turn`/`end_turn` RPCs, and a hold-to-talk
button in the bar.

## Never silent

The one hard rule: a voice user must always hear something. `AppLLMStream`
turns every failure (HTTP status, an SSE `error` before text, a timeout, a
refused connection) into `FALLBACK_REPLY` spoken aloud, plus
`assistant.error` for the UI. If you add code paths (tools, retrieval), keep
that guarantee and add a test for each new failure mode (see
`tests/test_app_llm.py`).

## Deprecations to watch

- livekit-agents 1.8 logs that `agent_name` in code will move to
  `livekit.toml` (`[agent] name = "…"`). It still works; move it when the
  warning becomes an error.
- The Dockerfile uses `python -m livekit.agents download-files` (the generic
  form); `python voice_agent.py download-files` also works locally.
