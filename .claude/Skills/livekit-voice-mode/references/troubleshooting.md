# Troubleshooting

Run `python <skill>/scripts/doctor_voice.py --project . --live` first. It
catches most of these with the fix spelled out.

| Symptom | Cause | Fix |
|---|---|---|
| No voice button in the composer | `/api/voice/config` says `enabled: false` (LIVEKIT_* missing in api/.env, or the API wasn't restarted); or no model is available; or the box isn't empty | Fill api/.env and restart the API; install a model; clear the input |
| No voice button, and `/api/voice/config` is 404 | `mount_voice(...)` isn't called in `create_app()` | See `integrate-fastapi.md` |
| API crashes with `No module named 'livekit'` | Dependency added but the venv wasn't synced | `cd api && uv sync` (the installer does this unless `--no-install`) |
| "Voice mode couldn't start … Make sure the agent is running" after ~20 s | Agent not running, registered in another LiveKit project, or with a different `VOICE_AGENT_NAME` | Start the agent; make LIVEKIT_* and `VOICE_AGENT_NAME` identical in both .env files |
| Agent log shows `registered worker` but never a job | Agent-name mismatch, or two workers (an old one takes the job) | Check the names; stop stray workers (`fuser -k 8081/tcp`) |
| Connects, but "Couldn't get a reply: API error …" and a spoken apology | The agent can't reach the API, or the API's model failed | Check `API_URL` from the agent's network (`http://api:8000` in Compose); check the API log |
| Spoken apology with `Connection refused` | `API_URL` points to localhost inside a container | Use the service name or an internal URL |
| Replies read out asterisks or code | A custom brain dropped the system prompt, or the TTS transforms were removed | Keep `req.messages[0]` (voice instructions); keep the default TTS text transforms |
| Replies ignore the model dropdown | `VOICE_LLM` isn't `app`; or the room context expired or lives on another API instance | Set `VOICE_LLM=app`; sticky routing or a Redis store (`integrate-fastapi.md`) |
| "Microphone access is blocked" | Permission denied, no device, or the mic is in use by another app | Site settings → allow the microphone; the message names the case |
| Mic works locally, fails when deployed | The page is served over plain HTTP (not localhost) | Serve the web app over HTTPS: browsers require a secure context for the mic |
| Browser can't connect: websocket error to `ws://…` | `LIVEKIT_URL` isn't reachable from the browser, or is `ws://` on an HTTPS page | Use the Cloud `wss://` URL; for self-hosted, put TLS in front |
| Two rooms or two agents per start in development | Strict Mode double mount without the 0 ms start timer | Keep the timer and `session.end()` cleanup in voice-session |
| Closing the settings menu with Esc stops the reply | The Esc guard for menus/dialogs was removed | Restore the `closest('[role=menu],[role=dialog],[role=listbox]')` check |
| Greeting saved cut short, or agent text missing words in the saved chat | Saving on the agent's final flag (never arrives) or appending instead of upserting | Save agent turns when the agent goes idle; upsert by `voice-<segment id>` |
| A chat created with only the greeting | Saving before the first user message | Buffer until a user message exists (`saveTranscripts` in chat-app) |
| Empty code block after Stop | Reply cut inside a code fence | Keep the trailing-fence strip in the live view |
| Level bars flat | Custom `loPass`/`hiPass` on `useMultibandTrackVolume` | Use the default bands with `{ bands: 5 }` |
| `InsecureKeyLengthWarning` in logs | Dev secret `secret` is 6 bytes | Harmless with `--dev`; Cloud secrets are long |
| Agent websocket gets HTTP 405 (local tests) | An HTTP proxy intercepts localhost | Unset `HTTP(S)_PROXY` for the agent process |
| `DeprecationWarning` about `agent_name` | livekit-agents 1.8 is moving it to `livekit.toml` | Works today; see `agent.md` |
| Agent unit tests fail only on one machine | That machine's `agent/.env` leaks into the tests | Keep the autouse env-clearing fixture in `agent/tests/conftest.py` |
| Installer says "customised, left unchanged" | Your file no longer matches the template around an edit | Make the numbered edit by hand from `manual-edits.md`, or rerun with `--partial` and finish the rest |
