# AI Assistant — API

FastAPI backend. Local Ollama models are used first; cloud providers
(Anthropic, OpenAI, Gemini, Grok, Meta Llama) are the fallback.

## Run

```bash
uv sync
cp .env.example .env          # add any cloud API keys you have
uv run fastapi dev app/main.py   # http://localhost:8000/docs
```

## Quality

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/models?refresh=true` | Installed Ollama models + cloud models, grouped by provider, with the default pick |
| POST | `/api/chat` | Streams a reply as server-sent events |

`POST /api/chat` body:

```json
{ "messages": [{"role": "user", "content": "Hi"}], "provider": "ollama", "model": "llama3.2:latest" }
```

`provider` and `model` are optional; without them the API picks the first
local model, then the first configured cloud provider.

Stream events:

```
event: meta
data: {"provider":"ollama","model":"llama3.2:latest","local":true,"fallback":false,"notice":null}

data: {"delta":"Hello"}

event: done        (or)   event: error
data: {}                  data: {"message":"..."}
```

## How fallback works

1. The model picked in the UI is tried first.
2. If it fails **before** sending any text, the API tries the first installed
   Ollama model, then each cloud provider in `CLOUD_PRIORITY` order.
3. The `meta` event says which model actually answered (`fallback: true`, with
   the reason in `notice`) so the UI can tell the user.
4. If a model fails mid-answer, the API reports an error rather than switching,
   so replies never mix two models.

Set `ALLOW_CLOUD_FALLBACK=false` to keep everything on the chosen model.

## Layout

```
app/
  main.py              app factory, CORS, lifespan
  core/config.py       settings from env / .env
  schemas.py           request/response models
  deps.py              FastAPI dependencies
  routes/              health, models, chat
  providers/
    base.py            Provider interface
    ollama.py          local models (ollama SDK)
    anthropic.py       Claude (anthropic SDK)
    openai_compat.py   OpenAI, Gemini, Grok, Meta (OpenAI-compatible APIs)
    registry.py        builds providers, lists models, picks candidates
  services/chat.py     streaming + fallback logic
tests/                 pytest suite with fake providers (no network needed)
```
