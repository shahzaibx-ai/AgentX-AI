# AgentX AI

**A production-ready, local-first AI chat app with vision, voice mode, and voice dictation.**

AgentX AI runs models on your own machine through **Ollama first**, and automatically falls back to **cloud AI** (Anthropic Claude, OpenAI, Google Gemini, xAI Grok, Meta Llama) when no local model is installed or a local model fails. It supports photo understanding, real-time voice conversations over LiveKit, and push-to-talk dictation.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-7-3178C6?logo=typescript&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)
![LiveKit](https://img.shields.io/badge/LiveKit-Agents-FF6B6B)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Setup & Installation](#setup--installation)
7. [Configuration](#configuration)
8. [How It Works](#how-it-works)
9. [API Reference](#api-reference)
10. [Testing & Quality](#testing--quality)
11. [Production Checklist](#production-checklist)
12. [Roadmap](#roadmap)
13. [Author & Contact](#author--contact)

---

## Project Overview

AgentX AI is a full-stack AI assistant made of three independently deployable services:

| Service | Folder | Role |
|---|---|---|
| **Web** | `web/` | Next.js chat UI: history, model picker, photos, voice mode, dictation |
| **API** | `api/` | FastAPI backend: provider registry, streaming chat, fallback logic, voice sessions, speech-to-text |
| **Agent** | `agent/` | LiveKit voice agent: speech-to-text, turn detection, text-to-speech; answers through the API |

The design goals are **privacy** (local models and local photos by default), **resilience** (automatic fallback so a reply is almost never lost), and **a clean, extensible codebase** (provider interface, drop-in voice package, typed end to end, tested with fake providers so no network is needed).

---

## Features

### Chat
- **Streaming replies** over server-sent events, with stop and regenerate.
- **Markdown rendering** (GitHub-flavored) with copyable code blocks and tables.
- **Conversation history** with search, date grouping, delete with undo, stored in the browser.
- **Quote message**, copy, thumbs up/down feedback on replies.
- **Keyboard shortcuts**: `Ctrl/Cmd + Shift + O` new chat, `Ctrl/Cmd + K` search, `Esc` stop.
- Light, dark, and system themes; responsive layout with a mobile sidebar sheet.

### Local-first model routing
- **Auto mode** (default): first installed Ollama model, otherwise the first cloud provider with a key.
- **Model picker** grouped as **Local · Ollama** and **Cloud (fallback)**, with live model lists fetched from each provider (new models appear without code changes).
- **Automatic fallback** if the chosen model fails *before* replying. The UI shows which model actually answered and why.
- Mid-answer failures are reported instead of switching models, so replies never mix two models.
- Switch fallback off with `ALLOW_CLOUD_FALLBACK=false`.

### Photos (vision)
- Add up to **5 photos per message** (JPEG, PNG, WebP, GIF, 10 MB each) via the **+** button, camera, paste, or drag and drop.
- The browser **resizes to 2048 px** and re-encodes, which also **strips metadata such as GPS location**.
- **Vision-aware routing**: Auto picks a model that can see images; a text-only model shows a notice with a one-click switch.
- Models are tagged **"Sees images"**. Ollama reports vision capability directly; cloud models are matched by family with `VISION_MODELS` for custom patterns.
- A privacy line shows whether photos stay on your computer or which provider receives them.
- Photos live in the browser (IndexedDB), with automatic cleanup of unused ones after a day.
- Server-side hardening: real format detected from file signature, per-image/per-message/per-request limits, streaming request-size cap (HTTP 413), and raw-bytes handling for Ollama so a string like `/etc/passwd` can never be read as a file path.

### Voice mode (LiveKit)
- Real-time spoken conversation with **interruptions** (talk over the assistant, or press **Stop** / **Esc**).
- Replies use **the same model dropdown and fallback** as text chat.
- **Live captions**, microphone selection and mute, optional TTS voice picker.
- Voice context carries the earlier text chat, so you can switch between speaking and typing.
- Spoken failure messages and clear UI reasons if a model fails or the agent is offline (20-second agent-join timeout).
- Noise cancellation via ai-coustics; STT, TTS, and turn detection via LiveKit Inference.

### Voice dictation
- Mic button in the composer records audio with a live level meter and timer, transcribes it with **Groq Whisper (`whisper-large-v3-turbo`)**, and inserts the text into the message box.

---

## Architecture

```
┌────────────────────────── Browser (Next.js) ──────────────────────────┐
│ Chat UI · Model picker · Photos (IndexedDB) · Voice UI · Dictation    │
└───────┬───────────────────────────────┬───────────────────────────────┘
        │ /api/* (proxied by Next.js)   │ WebRTC (mic + speaker)
        ▼                               ▼
┌──────────────────┐             ┌──────────────────┐
│   FastAPI (api)  │◄────────────│  LiveKit Cloud   │
│                  │ POST        └────────┬─────────┘
│  /api/chat       │ /api/voice/chat      │
│  /api/models     │                      ▼
│  /api/stt        │             ┌──────────────────┐
│  /api/voice/*    │◄────────────│ Voice agent      │
└───┬──────────┬───┘             │ STT → turns →TTS │
    │          │                 └──────────────────┘
    ▼          ▼
 Ollama     Cloud providers
 (local)    Anthropic · OpenAI · Gemini · Grok · Meta
```

**Voice session flow**

1. The browser calls `POST /api/voice/session`. The API creates a fresh room, remembers the chosen model and earlier chat, and returns a token that dispatches the agent.
2. The browser joins via WebRTC; the agent joins, greets the user, and listens.
3. After each user turn, the agent posts the spoken conversation to `POST /api/voice/chat`. The API applies model selection and fallback, streams the reply, and the agent speaks it while publishing `assistant.model`, `assistant.provider`, `assistant.notice` and `assistant.error` attributes for the UI.
4. Transcripts are saved into the chat tagged **Spoken**.

---

## Tech Stack

### Frontend (`web/`)
| Area | Technology |
|---|---|
| Framework | Next.js 16, React 19, TypeScript 7 |
| Styling & UI | Tailwind CSS 4, shadcn/ui (new-york), Radix UI, lucide-react, Sonner toasts, next-themes |
| Content | react-markdown, remark-gfm |
| Voice | `livekit-client`, `@livekit/components-react` |
| Storage | localStorage (chats), IndexedDB (photos) |
| Fonts | Geist Sans / Geist Mono |

### Backend (`api/`)
| Area | Technology |
|---|---|
| Framework | FastAPI, Pydantic v2, pydantic-settings |
| Runtime & tooling | Python 3.13, uv, Uvicorn, ruff, pytest, pytest-asyncio |
| Local AI | Ollama Python SDK |
| Cloud AI | Anthropic SDK; OpenAI SDK for OpenAI, Gemini, Grok, Meta (OpenAI-compatible endpoints) |
| Speech-to-text | Groq Whisper via the OpenAI SDK |
| Voice | `livekit-api` (token minting, agent dispatch) |
| Streaming | Server-sent events |

### Voice agent (`agent/`)
| Area | Technology |
|---|---|
| Framework | LiveKit Agents (`livekit-agents`) |
| Speech-to-text | `assemblyai/universal-3-5-pro` (LiveKit Inference) |
| Text-to-speech | `fishaudio/s2.1-pro` (LiveKit Inference) |
| Turn detection | LiveKit Inference turn detector |
| Noise cancellation | ai-coustics `QUAIL_VF_S` |
| LLM | The app's own API (`VOICE_LLM=app`), or any LiveKit Inference model id |

### AI models and providers
| Provider | Type | Enabled by |
|---|---|---|
| Ollama (Llama, Gemma, Qwen, LLaVA, …) | Local | `OLLAMA_ENABLED=true` (default) |
| Anthropic Claude | Cloud | `ANTHROPIC_API_KEY` |
| OpenAI | Cloud | `OPENAI_API_KEY` |
| Google Gemini | Cloud | `GEMINI_API_KEY` |
| xAI Grok | Cloud | `GROK_API_KEY` |
| Meta Llama API | Cloud | `META_API_KEY` |
| Groq Whisper | Speech-to-text | `GROQ_API_KEY` |
| LiveKit Inference | STT / TTS / turn detection | LiveKit Cloud project |

### DevOps
Docker and Docker Compose (multi-stage builds, non-root users, health checks), standalone Next.js output.

---

## Project Structure

```
agentx-ai/
├── docker-compose.yml
├── api/                     FastAPI backend
│   ├── app/
│   │   ├── main.py          App factory, CORS, body-size limit, router mounting
│   │   ├── schemas.py       Request/response models (images validated and decoded once)
│   │   ├── images.py        Image sniffing and base64 handling
│   │   ├── vision.py        Which models can see images
│   │   ├── voice_brain.py   Connects voice mode to the text-chat pipeline
│   │   ├── core/            config, logging, request body-size limit
│   │   ├── providers/       base, ollama, anthropic, openai_compat, registry
│   │   ├── routes/          chat, models, health, stt
│   │   ├── services/chat.py Streaming + fallback logic
│   │   └── voice/           Drop-in LiveKit voice package (routes, service, settings)
│   └── tests/               pytest suite using fake providers (no network)
├── agent/                   LiveKit voice agent
│   ├── voice_agent.py       Entrypoint: chat mode and dictation mode
│   ├── app_llm.py           LLM adapter that streams from the app's API
│   ├── settings.py          Agent settings
│   └── tests/
└── web/                     Next.js frontend
    ├── app/                 layout, page, global styles
    ├── components/
    │   ├── chat/            sidebar, composer, messages, model picker, markdown
    │   ├── photos/          attachment tray, viewer, drop zone, vision notice
    │   ├── voice/           voice session, bar, level meters
    │   └── ui/              shadcn/ui primitives
    ├── hooks/               use-chat, use-models, use-attachments, use-recorder, …
    └── lib/                 api client, types, image helpers, voice client
```

---

## Setup & Installation

### Prerequisites

- **Python 3.13** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20.9+** and npm
- [**Ollama**](https://ollama.com) (optional but recommended for local models)
- A [**LiveKit Cloud**](https://cloud.livekit.io) project (only for voice mode)
- A [**Groq**](https://console.groq.com) API key (only for dictation; free tier available)
- Cloud API keys (optional fallback)

### 1. Clone the repository

```bash
git clone https://github.com/shahzaibx-ai/agentx-ai.git
cd agentx-ai
```

### 2. Pull local models (optional but recommended)

```bash
ollama pull llama3.2      # text chat
ollama pull gemma3        # photos (or llava, qwen2.5vl)
```

### 3. Run the API  →  http://localhost:8000/docs

```bash
cd api
uv sync
cp .env.example .env      # add cloud / Groq / LiveKit keys if you have them
uv run fastapi dev app/main.py
```

### 4. Run the web app  →  http://localhost:3000

Open a new terminal:

```bash
cd web
npm install
cp .env.example .env.local    # API_URL=http://localhost:8000
npm run dev
```

The browser calls `/api/*` on the Next.js app, which forwards requests to the FastAPI server at `API_URL`, so no CORS setup is needed.

### 5. Enable voice mode (optional)

1. Create a LiveKit Cloud project and put the same three values in **both** `api/.env` and `agent/.env`:

   ```bash
   LIVEKIT_URL=wss://<your-project>.livekit.cloud
   LIVEKIT_API_KEY=...
   LIVEKIT_API_SECRET=...
   ```

2. Start the agent (API must already be running):

   ```bash
   cd agent
   uv sync
   cp .env.example .env
   uv run python voice_agent.py dev
   ```

3. Voice mode appears in the sidebar once the API has LiveKit credentials.

### 6. Enable dictation (optional)

Add your Groq key to `api/.env`:

```bash
GROQ_API_KEY=your-groq-key
```

### Run everything with Docker

```bash
cp api/.env.example api/.env          # add your keys
docker compose up --build             # api + web

# with the voice agent (fill agent/.env first)
docker compose --profile voice up --build

# run Ollama in Docker instead of on the host
docker compose --profile ollama up    # then set OLLAMA_HOST=http://ollama:11434
```

Services: web on `:3000`, API on `:8000`, agent health check on `:8081`.

---

## Configuration

### API (`api/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | Set `production` to hide `/docs` |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed browser origins (JSON list) |
| `SYSTEM_PROMPT` | helpful assistant | System prompt for every chat |
| `ALLOW_CLOUD_FALLBACK` | `true` | Try other models when one fails |
| `MODEL_CACHE_TTL_SECONDS` | `30` | Model list cache |
| `REQUEST_TIMEOUT_SECONDS` | `120` | Provider timeout |
| `OLLAMA_ENABLED` / `OLLAMA_HOST` | `true` / `http://localhost:11434` | Local models |
| `CLOUD_PRIORITY` | `["anthropic","openai","gemini","grok","meta"]` | Cloud fallback order |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROK_API_KEY`, `META_API_KEY` | empty | A provider is enabled when its key is set |
| `*_MODEL` | empty | Preferred fallback model per provider (empty = first listed) |
| `GROQ_API_KEY` | empty | Speech-to-text for dictation |
| `MAX_IMAGES_PER_MESSAGE` | `5` | Photo limit per message |
| `MAX_IMAGES_PER_REQUEST` | `20` | Photo limit across the whole history |
| `MAX_IMAGE_BYTES` | `10485760` | Max size of one photo |
| `VISION_MODELS` | `[]` | Extra fnmatch patterns for vision-capable models |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | empty | Enable voice mode |
| `VOICE_AGENT_NAME` | `my-agent` | Must match the agent |
| `VOICE_AGENT_TOKEN` | empty | Shared secret protecting `/api/voice/chat` |
| `VOICE_VOICES` | `[]` | Optional TTS voice picker |

### Agent (`agent/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `LIVEKIT_*` | n/a | Same project as the API |
| `VOICE_AGENT_NAME` | `my-agent` | Must match the API |
| `VOICE_LLM` | `app` | `app` = answer through the API; or a LiveKit Inference model id |
| `API_URL`, `API_TIMEOUT_SECONDS` | `http://localhost:8000`, `120` | Where the agent reaches the API |
| `VOICE_AGENT_TOKEN` | empty | Same as in the API |
| `VOICE_STT_MODEL`, `VOICE_STT_LANGUAGE` | `assemblyai/universal-3-5-pro`, `en` | Speech-to-text |
| `VOICE_TTS_MODEL`, `VOICE_TTS_VOICE` | `fishaudio/s2.1-pro`, default voice id | Text-to-speech |
| `VOICE_NOISE_CANCELLATION` | `true` | Set `false` on self-hosted LiveKit |
| `VOICE_GREETING`, `VOICE_INSTRUCTIONS` | friendly defaults | Personality |

### Web (`web/.env.local`)

| Variable | Default | Purpose |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Server-side target of the `/api/*` rewrite |

The app name and placeholder user live in `web/lib/config.ts`.

---

## How It Works

### Model selection and fallback

1. The model chosen in the UI is tried first.
2. If it fails **before** sending text, the API tries the first installed Ollama model, then each cloud provider in `CLOUD_PRIORITY` order.
3. The `meta` event reports which model answered (`fallback: true` plus the reason in `notice`).
4. If a model fails mid-answer, an `error` event is sent and no other model takes over.

### Photos and vision

When any message in the conversation has photos, Auto and fallback consider only vision-capable models. An explicitly chosen text-only model is rejected up front with a clear message instead of silently ignoring the image. Photos are sent to Ollama as raw bytes, to Anthropic as image blocks (5 MB limit per image; larger ones fall back to another model), and to OpenAI-compatible APIs as `image_url` parts. Nothing is written to disk on the server.

### Dictation

The composer records audio with `MediaRecorder`, uploads it to `POST /api/stt`, and the API forwards it to Groq Whisper. The returned text is appended to the current message.

---

## API Reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/models?refresh=true` | Models grouped by provider, defaults, vision flags, image limits |
| `POST` | `/api/chat` | Stream a reply as server-sent events |
| `POST` | `/api/stt` | Transcribe an audio file (max 25 MB) |
| `GET` | `/api/voice/config` | Whether voice is enabled, and available voices |
| `POST` | `/api/voice/session` | Create a room and token that dispatches the agent |
| `POST` | `/api/voice/chat` | Called by the agent to get a spoken-turn reply (optional Bearer token) |

**Chat request**

```json
{
  "messages": [
    { "role": "user", "content": "What's on this receipt?",
      "images": [{ "media_type": "image/jpeg", "data": "/9j/4AAQ..." }] }
  ],
  "provider": "ollama",
  "model": "gemma3:latest"
}
```

`provider` and `model` are optional; omit them for Auto.

**Stream events**

```
event: meta
data: {"provider":"ollama","model":"gemma3:latest","local":true,"fallback":false,"notice":null}

data: {"delta":"Hello"}

event: done        (or)   event: error
data: {}                  data: {"message":"..."}
```

Interactive docs are available at `http://localhost:8000/docs` outside production.

---

## Testing & Quality

```bash
# API
cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest

# Agent
cd agent && uv run ruff check . && uv run ruff format --check . && uv run pytest

# Web
cd web && npm run typecheck && npm run build
```

The API and agent test suites use fake providers and mocked transports, so they run without Ollama, API keys, or network access.

---

## Production Checklist

- Serve both services over **HTTPS** behind a reverse proxy or load balancer. Keep response buffering **off** for `/api/chat` so replies stream.
- Set `ENVIRONMENT=production` and a real `CORS_ORIGINS` if the API is called from another domain.
- Add **authentication and rate limiting** before going public. Cloud calls, voice sessions, and transcription all cost money. Anyone who can reach `/api/voice/session` can start a billed voice session.
- Set the same `VOICE_AGENT_TOKEN` in `api/.env` and `agent/.env` so only the agent can call `/api/voice/chat`.
- Chat history lives in each user's browser today. Add a database when you add user accounts.
- The voice context store is in-memory; use Redis if you scale the API across multiple processes.

---

## Roadmap

- User accounts and server-side chat storage
- HEIC photo support
- Persisted voice preferences (voice, captions) and saved transcripts into chat history
- Rate limiting and usage tracking
- Document and file upload (RAG)

---

## Author & Contact

**Muhammad Shahzaib Arshed**

| | |
|---|---|
| GitHub | [github.com/shahzaibx-ai](https://github.com/shahzaibx-ai) |
| LinkedIn | [linkedin.com/in/muhammad-shahzaib-arshed](https://www.linkedin.com/in/muhammad-shahzaib-arshed/) |
| Email | [mszaibi007@gmail.com](mailto:mszaibi007@gmail.com) |

Questions, bug reports, and pull requests are welcome. Open an issue or reach out directly.

---

<p align="center">Built with FastAPI, Next.js, Ollama, and LiveKit.</p>