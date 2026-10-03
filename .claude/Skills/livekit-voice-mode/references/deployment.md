# Deployment

## Docker Compose (the template)

The installer adds an `agent` service under the `voice` profile:

```bash
cp agent/.env.example agent/.env          # fill in LIVEKIT_* (same project as api/.env)
docker compose --profile voice up --build
```

- Compose sets `API_URL=http://api:8000` for the agent. Don't use `localhost`
  inside containers.
- The agent needs **no inbound port**. It dials out to LiveKit. Port 8081 is
  only its health check, used by the Compose healthcheck.
- The agent image runs `python -m livekit.agents download-files` at build
  time, so plugin model files are baked in and not fetched per session.
- `LIVEKIT_URL` in api/.env goes to the browser, so it must be the public
  `wss://` URL even when everything else runs in Compose.

## Where the agent can run

| Option | Notes |
|---|---|
| Next to the API (same Compose / VM / cluster) | Simplest. `API_URL` stays internal, so `/api/voice/chat` never needs to be public |
| LiveKit Cloud agent hosting | `lk agent create` then `lk agent deploy` (LiveKit CLI) build from `agent/Dockerfile`. The agent then reaches the API over the internet, so set `VOICE_AGENT_TOKEN`, use an https `API_URL`, and provide secrets as the LiveKit docs describe. Check the current docs for `livekit.toml` and secrets flags |
| Any container platform | One long-running process per replica (`python voice_agent.py start`). Scale replicas with concurrent sessions: each session runs STT/TTS streams and some CPU for noise cancellation |

Graceful shutdown: LiveKit Agents drains active sessions on SIGTERM. Give
containers a generous stop timeout (e.g. `stop_grace_period: 60s`) so deploys
don't cut calls.

## Security checklist

1. **Auth on `/api/voice/session`.** Anyone who can call it starts a billed
   voice session. Put it behind your login: add `dependencies=[Depends(require_user)]`
   to the `/session` route in `app/voice/routes.py`, or put a middleware in
   front. Pass the user's name as `participant_name`. If brains need the
   user, store the user id in `VoiceContext` there.
2. **Agent-only `/api/voice/chat`.** Set the same `VOICE_AGENT_TOKEN` in
   api/.env and agent/.env (generate one with
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`). The API
   then answers 401 to anything without `Authorization: Bearer <token>`.
   Required when the agent reaches the API over the internet.
3. **Secrets stay server-side.** The browser gets only a participant token
   for one room (default 15 min, just to join).
4. **Rate limits.** Limit `/session` per user or IP at your proxy. Voice
   minutes cost STT + TTS + LLM.
5. **HTTPS.** Browsers allow the microphone only in secure contexts
   (https or localhost).
6. **Logs.** Transcripts pass through the API. Don't log message bodies in
   production.

## Scaling

- **API:** the room context (model choice + history) is in-process memory. With
  more than one API replica, use sticky sessions or move `VoiceContextStore` to
  Redis (`integrate-fastapi.md`). Without that, replies still work, but on
  automatic model choice and without history.
- **Agent:** stateless between sessions; add replicas freely. All replicas
  register under the same `VOICE_AGENT_NAME`, and LiveKit load-balances
  dispatch.
- **Web:** unchanged. The voice chunk loads on demand.

## Costs to explain to clients

LiveKit Cloud bills connection minutes plus Inference usage (STT, TTS, and the
LLM when `VOICE_LLM` isn't `app`). With `VOICE_LLM=app`, the LLM cost is
whatever the app's model costs: zero for local Ollama, the provider's price for
cloud fallback. Check LiveKit's current pricing page before quoting numbers.

## Go-live check

```bash
python <skill>/scripts/doctor_voice.py --project . --live \
  --api https://api.example.com --agent-health http://<agent-host>:8081
```

Then make one real call from a phone on mobile data (different network, real
mic, real speaker). That catches TURN/firewall and echo issues that local tests
can't.
