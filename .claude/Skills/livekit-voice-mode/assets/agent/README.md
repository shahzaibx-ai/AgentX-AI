# AI Assistant — Voice agent

A [LiveKit Agents](https://docs.livekit.io/agents/) worker that powers the web
app's voice mode.

| Part | Default | Setting |
|---|---|---|
| Speech-to-text | `assemblyai/universal-3-5-pro` (English) | `VOICE_STT_MODEL`, `VOICE_STT_LANGUAGE` |
| Replies | The app's API: model dropdown, Ollama first, cloud fallback | `VOICE_LLM=app` |
| Text-to-speech | `fishaudio/s2.1-pro` | `VOICE_TTS_MODEL`, `VOICE_TTS_VOICE` |
| Turn detection | LiveKit Inference turn detector | — |
| Noise cancellation | ai-coustics `QUAIL_VF_S` | `VOICE_NOISE_CANCELLATION` |

Speech, turn detection and noise cancellation run on **LiveKit Cloud**
(LiveKit Inference), so use a LiveKit Cloud project's URL and keys.

## Run

```bash
uv sync
cp .env.example .env        # same LIVEKIT_* values as api/.env
uv run python voice_agent.py dev
```

Start the API first; the agent sends each spoken turn to
`POST {API_URL}/api/voice/chat`. When the API is public, set the same
`VOICE_AGENT_TOKEN` here and in api/.env so only this agent can call it.

## How a session works

1. The web app calls `POST /api/voice/session`. The API creates a fresh room,
   remembers the chosen model and the earlier chat, and returns a token whose
   room configuration dispatches this agent (`VOICE_AGENT_NAME`).
2. The agent joins, greets the user (`VOICE_GREETING`) and listens.
3. After each user turn, `AppLLM` streams the reply from the API. The API
   applies the model choice and fallback; the agent speaks it and publishes
   `assistant.model`, `assistant.provider`, `assistant.local`,
   `assistant.notice` and `assistant.error` attributes for the UI.
4. The web app's **Stop** button calls the `interrupt` RPC. Talking over the
   agent interrupts it too.

If the model fails, the agent says a short apology instead of going silent,
and the real reason appears in the web app.

Set `VOICE_LLM` to a LiveKit Inference model id (e.g. `google/gemma-4-31b-it`)
to skip the app's API and answer directly; model choice and chat history from
the web app then don't apply.

## Notes

- livekit-agents 1.8 logs that `agent_name` set in code will move to
  `livekit.toml` (`[agent] name`) in a future release. It works today; when
  you upgrade, move `VOICE_AGENT_NAME` there.
- Noise cancellation (ai-coustics) and LiveKit Inference need LiveKit Cloud.
  With a self-hosted LiveKit server, set `VOICE_NOISE_CANCELLATION=false` and
  switch STT/TTS/turn detection to provider plugins.

## Quality

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
