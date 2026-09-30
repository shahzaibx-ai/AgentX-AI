# AI Assistant — Full Stack

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
