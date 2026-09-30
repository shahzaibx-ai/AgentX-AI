# Testing voice mode

## Unit tests (no network, run in CI)

| Suite | Count | Covers |
|---|---|---|
| `api/tests/test_voice.py` | 18 (the template's API suite totals 38) | config on/off, custom prefix, token claims (identity, room, TTL, agent dispatch, voice metadata), unknown voice → 422, unique rooms, history trimming, brain receives model + history, unknown room → automatic model, brain crash → safe `error`, validation, normalising, caps, store expiry, template adapter end to end with a fake provider |
| `agent/tests/` | 12 | settings, dispatch metadata parsing, LLM choice, noise cancellation toggle, AppLLM streaming, meta/error callbacks, spoken fallback on HTTP error / SSE error / timeout / refused connection, partial text kept |

`agent/tests/conftest.py` clears `VOICE_*` and `API_*` for every test, because
`voice_agent.py` loads `agent/.env` into the environment on import. Keep this
fixture, or a developer's `.env` will break the suite.

Gates: `bash <skill>/scripts/verify_voice.sh <project>` (ruff + format + pytest
for api and agent, typecheck + build for web).

## End to end without LiveKit Cloud

Everything is real except the cloud speech services. That covers: browser
WebRTC, a real LiveKit server, token dispatch, the production `voice_session`,
AppLLM → API → model, attributes, the interrupt RPC, transcripts and saving.

1. **LiveKit server.** Download `livekit_<ver>_linux_amd64.tar.gz` (or your
   OS's build) from the livekit/livekit GitHub releases, then:
   `livekit-server --dev --bind 127.0.0.1` → `ws://127.0.0.1:7880`, `devkey` / `secret`.
2. **A model.** A real Ollama with a small model, or the stand-in (it
   streams a fixed answer):
   `cd api && uv run uvicorn --app-dir <skill>/assets/testing fake_ollama:app --port 11434`
3. **API** with `LIVEKIT_URL=ws://127.0.0.1:7880 LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret`
   in api/.env: `cd api && uv run uvicorn app.main:app --port 8000`
4. **Agent harness** (from `agent/`, with the same LIVEKIT_* plus
   `VOICE_NOISE_CANCELLATION=false`):
   `uv run python <skill>/assets/testing/voice_e2e_agent.py start`
   It imports the project's real `voice_agent` and swaps in `FakeSTT` (it
   "hears" "What is AI?" after about 1.5 s of mic audio), `FakeTTS` (tones with
   3–5 kHz content, so level bars move), and STT-based turn detection.
5. **Web:** `cd web && npm run build && npm start`.
6. **Browser test:**
   ```bash
   npm i -D playwright-core && npx playwright install chromium   # or CHROME_PATH=/path/to/chrome
   BASE_URL=http://localhost:3000 node <skill>/assets/testing/voice_e2e.js all
   ```
   Desktop runs the full flow: Start → "Spoken" → **Stop the reply** visible →
   settings menu opens, and Esc closes it without stopping → Stop →
   "Listening…" → Mute → End → the chat is saved with voice messages. Mobile
   (390 px) and dark mode check the speaking layout. Screenshots are written
   to `./voice-e2e-out`. Exit 1 on any failure or browser error.
7. **Check it** with `python <skill>/scripts/doctor_voice.py --project . --live`.

Expected output (desktop):

```
desktop clicked Start voice mode
desktop user transcript is final
desktop agent is speaking
desktop Stop interrupted the reply; agent listening again
desktop muted
desktop saved: [{"title": "What is AI?", "messages": ["assistant(voice): Hi! …",
                 "user(voice): What is AI?", "assistant(voice): … | llama3.2:latest"]}]
desktop PASS
```

## Failure paths to check by hand

- **Model down.** Stop the model server after the page loads, then speak. You
  should hear the spoken apology and see the banner "Couldn't get a reply: …".
- **Agent down.** Stop the agent, then start voice. After about 20 s: "Voice
  mode couldn't start … Make sure the agent is running…", with Type instead /
  Try again.
- **Mic blocked.** Deny the permission. You should see "Microphone access is
  blocked" with a specific reason.
- **Cloud fallback.** Pick a local model that fails. The banner says "Using
  <provider> because the selected model was unavailable (…)".

## Gotchas when scripting this

- Behind an HTTP proxy, unset `HTTP(S)_PROXY` for the agent, or its websocket
  to localhost gets a 405 from the proxy.
- Stop processes with PID files or `fuser -k <port>/tcp`. `pkill -f <pattern>`
  can match and kill your own shell.
- One agent per LiveKit server in tests: a stray old worker also registers as
  `my-agent` and may take the job. Check `:8081` before starting another.
- `inference.LLM` reads `LIVEKIT_API_KEY` at construction, so unit tests that
  build it must `monkeypatch.setenv` a key and a 32+ byte secret.
