# Configuration

Three places, and the rules that tie them together. `scripts/doctor_voice.py`
checks all of them.

## api/.env (read by `VoiceSettings`)

```dotenv
LIVEKIT_URL=wss://<project>.livekit.cloud      # the BROWSER connects here
LIVEKIT_API_KEY=API...
LIVEKIT_API_SECRET=...
VOICE_AGENT_NAME=my-agent                      # == agent/.env
VOICE_VOICES=[]                                # optional picker, see agent.md
# VOICE_TOKEN_TTL_SECONDS=900  VOICE_CONTEXT_TTL_SECONDS=3600  VOICE_HISTORY_MESSAGES=20
# VOICE_MAX_MESSAGES=100  VOICE_MAX_MESSAGE_CHARS=32000
```

Voice is **dormant until all three LIVEKIT_* are set**:
- `/api/voice/config` returns `enabled: false`;
- the composer shows no voice button;
- the browser never downloads LiveKit;
- `/api/voice/session` returns 503.

## agent/.env (read by `AgentSettings` and the LiveKit SDK)

```dotenv
LIVEKIT_URL=wss://<project>.livekit.cloud      # same project as the API
LIVEKIT_API_KEY=API...
LIVEKIT_API_SECRET=...
VOICE_AGENT_NAME=my-agent
VOICE_LLM=app
API_URL=http://localhost:8000                  # Docker Compose overrides: http://api:8000
```

The rest (models, voice, greeting, instructions, noise cancellation) is in
`agent.md`.

## web (build time)

| Variable | Default | Notes |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Target of the `/api/*` rewrite in `next.config.ts`. **Baked in at build**: rebuild after changing it (Docker passes it as a build arg) |
| `NEXT_PUBLIC_API_BASE` | `/api` | Only when the browser should call the API directly (another origin) |

## Rules

1. **Same LiveKit project everywhere.** URL, key and secret must be identical in
   api/.env and agent/.env. Otherwise the token is valid for a project the agent
   isn't registered in, and the UI shows "Voice mode couldn't start" after 20 s.
2. **Same agent name.** The API dispatches by `VOICE_AGENT_NAME`. A mismatch
   gives the same 20 s failure.
3. **Browser-reachable URL.** `LIVEKIT_URL` in api/.env is sent to the browser.
   `ws://127.0.0.1` works only for local testing on the same machine. HTTPS
   pages need `wss://`.
4. **Agent → API reachability.** `API_URL` is resolved from the agent's
   network (the container name in Compose, an internal URL in the cloud).
5. **Restart after edits.** Both processes read `.env` at startup.
6. **Secrets.** Never commit `.env`. The API secret stays server-side: the
   browser only ever sees a short-lived participant token for one room.

## Local LiveKit server (no Cloud account)

`livekit-server --dev --bind 127.0.0.1` uses `devkey` / `secret` at
`ws://127.0.0.1:7880`. Rooms, tokens, dispatch, transcripts and RPC all work.
LiveKit Inference (STT/TTS/turn detection) and ai-coustics don't, so use the
test harness (`testing.md`) or provider plugins (`agent.md`).
