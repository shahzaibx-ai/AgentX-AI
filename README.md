# AgentX AI — Full Stack

A production-ready AI chat application. It runs **local models through Ollama
first** and falls back to **cloud AI** (Anthropic, OpenAI, Google Gemini, xAI
Grok, Meta Llama) when no local model is installed or a local model fails.

```
ai-app/
├── api/   FastAPI · Python 3.13 · uv · ruff · pytest · Ollama SDK · Anthropic / OpenAI SDKs
└── web/   Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui
```

## Quick start

**Requirements:** Python 3.13 with [uv](https://docs.astral.sh/uv/), Node.js 20.9+,
and optionally [Ollama](https://ollama.com).

```bash
# 1. Local models (optional but recommended)
ollama pull llama3.2

# 2. API  → http://localhost:8000/docs
cd api
uv sync
cp .env.example .env            # add cloud API keys here if you have them
uv run fastapi dev app/main.py

# 3. Web  → http://localhost:3000   (new terminal)
cd web
npm install
cp .env.example .env.local
npm run dev
```

Or with Docker: `cp api/.env.example api/.env && docker compose up --build`.

## Photos

Add photos with the **+** button, by pasting, or by dropping them on the page
(up to 5 per message, JPEG, PNG, WebP or GIF, 10 MB each). The browser scales
them to 2048 px on the long edge and re-encodes them, which also removes
metadata such as GPS location. HEIC isn't supported yet; the app says how to
share a JPEG instead.

Photos need a model that can see images: `ollama pull gemma3` (or `llava`,
`qwen2.5vl`), or a cloud key. The model menu marks these "Sees images". Auto
picks one whenever a chat has photos; a chosen text-only model shows a notice
with a one-click switch. The line under the input says whether photos stay on
this computer or which provider receives them.

Photos are stored in the browser (IndexedDB) next to the chat history; photos
no chat uses are cleaned up after a day. Limits are set in `api/.env` (see
`api/README.md`).

## Voice mode (LiveKit)

Voice mode appears as a sound-wave button in the empty message box once the
API has LiveKit credentials. It needs a [LiveKit Cloud](https://cloud.livekit.io)
project, because speech-to-text, text-to-speech, turn detection and noise
cancellation run on LiveKit Inference.

```bash
# api/.env and agent/.env: the same three values from your LiveKit project
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

# Voice agent (new terminal; API must be running)
cd agent
uv sync
uv run python voice_agent.py dev
```

With Docker: fill in agent/.env, then `docker compose --profile voice up --build`.

How a session flows:

```
Browser ──POST /api/voice/session──► API: new room + token that dispatches the agent
   │                                     (remembers the chosen model and earlier chat)
   └──WebRTC (mic + speaker)──► LiveKit ◄── agent: STT → turn detection → reply → TTS
                                                │
                                   POST /api/voice/chat  (same model dropdown,
                                   Ollama first, cloud fallback as text chat)
```

- Replies use the model picked in the dropdown, with the same fallback as
  text chat. The agent shows which model answered.
- Talking over the assistant interrupts it; **Stop** and **Esc** do too.
- Transcripts are saved into the chat (tagged *Spoken*), so a voice
  conversation can continue by typing and vice versa.
- If a model fails the assistant says so out loud and the UI shows the
  reason; if the agent is not running the UI says so after 20 seconds.
- Anyone who can reach `/api/voice/session` can start a (billed) voice
  session, so put it behind your login before going public, and set the same
  `VOICE_AGENT_TOKEN` in api/.env and agent/.env so only the agent can call
  `/api/voice/chat`.

Voice settings (agent/.env): `VOICE_STT_MODEL`, `VOICE_STT_LANGUAGE`,
`VOICE_TTS_MODEL`, `VOICE_TTS_VOICE`, `VOICE_GREETING`, `VOICE_INSTRUCTIONS`,
`VOICE_NOISE_CANCELLATION`, and `VOICE_LLM` (`app`, or a LiveKit Inference model
id to bypass the app). Offer a voice picker with `VOICE_VOICES` in api/.env.

## How model selection works

The model dropdown shows three groups:

| Option | Behaviour |
|---|---|
| **Auto** (default) | First installed Ollama model; if none, the first cloud provider with a key |
| **Local · Ollama** | Every chat model you've pulled, with size and parameter count |
| **Cloud (fallback)** | One sub-menu per provider whose API key is set, listing its live models |

If the chosen model fails before replying (Ollama stopped, model deleted, key
out of quota), the API automatically tries the next option and the reply shows
a small note saying which model answered instead. Set
`ALLOW_CLOUD_FALLBACK=false` in `api/.env` to turn this off.

Cloud order is controlled by `CLOUD_PRIORITY`, and each provider's preferred
fallback model by `*_MODEL` (e.g. `OPENAI_MODEL`). Model lists are fetched live
from each provider, so new models appear without code changes.

## Quality checks

```bash
cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd web && npm run typecheck && npm run build
```

## Production checklist

- Put both services behind HTTPS (a reverse proxy or your platform's load balancer).
  Keep response buffering off for `/api/chat` so replies stream.
- Set `ENVIRONMENT=production` (hides `/docs`) and a real `CORS_ORIGINS` if the
  API is called from another domain.
- Add authentication and rate limiting before exposing the API publicly;
  cloud calls cost money.
- Chat history is stored in each user's browser today. Add a database when you
  add user accounts.
