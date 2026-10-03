# Architecture

## System

```
Browser ──► Next.js (web, :3000)
              │  app/page.tsx → <ChatApp/> (client component)
              │  /api/*  ──rewrite──►  FastAPI (api, :8000)
              ▼                          │
                                         ├─ GET  /api/models  → ProviderRegistry.models_response()
                                         └─ POST /api/chat    → ChatService.stream()  (SSE)
                                                                  │
                                           candidates: selected → local (Ollama) → cloud (CLOUD_PRIORITY)
                                                                  │
                          OllamaProvider ── ollama SDK ──► localhost:11434
                          AnthropicProvider ── anthropic SDK
                          OpenAICompatibleProvider ── openai SDK ──► OpenAI | Gemini | Grok | Meta Llama
```

## Backend layers (`api/app`)

| Layer | File | Responsibility |
|---|---|---|
| Entry | `main.py` | `create_app(settings, registry)` factory; lifespan stores `settings` + `registry` on `app.state`; CORS; routers under `/api` |
| Config | `core/config.py` | `Settings` (pydantic-settings) from env/`.env`; secrets are `SecretStr` |
| Schemas | `schemas.py` | `ChatRequest`, `ChatMessage`, `ModelInfo`, `ProviderStatus`, `ModelsResponse` |
| DI | `deps.py` | Reads settings/registry **from `request.app.state`** (not the global cache) so tests can inject |
| Routes | `routes/*.py` | Thin: validate, delegate, stream |
| Providers | `providers/*.py` | One class per backend, all implementing `Provider` |
| Registry | `providers/registry.py` | Builds providers from settings, probes them concurrently with a TTL cache, chooses candidates |
| Service | `services/chat.py` | Streams from the first candidate that works; emits typed events |

### The `Provider` contract

```python
class Provider(ABC):
    id: str; label: str; local: bool
    configured: bool            # has host / key
    default_model: str          # preferred fallback model ("" = first listed)
    async def list_models() -> list[ModelInfo]          # raise ProviderError when unreachable
    def stream_chat(model, messages, temperature) -> AsyncIterator[str]   # raise ProviderError
    async def aclose()
```

Every SDK exception is translated into `ProviderError` with a user-safe message.
Nothing above the provider layer knows about SDK types.

### Candidate selection (`ProviderRegistry.candidates`)

1. If the request names a provider (and it's configured): that provider + model
   (or its preferred model when `model` is omitted). Unknown provider → error event.
2. Then every provider in order (Ollama first, then `CLOUD_PRIORITY`) that is
   available and has models, using its preferred model, skipping duplicates.
3. With `ALLOW_CLOUD_FALLBACK=false` only the first candidate is kept.

### Fallback rule (`ChatService.stream`)

- A candidate that fails **before its first token** is skipped; its error is
  collected and the next candidate is tried. The model cache is invalidated so
  the dropdown refreshes to reality.
- A candidate that fails **after** sending text ends the stream with an `error`
  event. Switching models mid-answer would splice two models' text together.
- The first `meta` event carries `fallback: true` and `notice` (the collected
  errors) so the UI can explain the switch.
- No candidates at all → one `error` event with setup instructions.

## Frontend layers (`web/`)

| Layer | Files | Responsibility |
|---|---|---|
| Shell | `app/layout.tsx` | Geist fonts (self-hosted via `geist` pkg), `ThemeProvider` (class strategy), `TooltipProvider`, `Toaster` |
| Page | `app/page.tsx` | Renders `<ChatApp/>` |
| Container | `components/chat/chat-app.tsx` | Layout, desktop collapsible sidebar + mobile `Sheet`, header, global shortcuts, toasts |
| State | `hooks/use-models.ts` | Loads `/api/models`, persists selection, drops stale selections, exposes `effective` model |
| State | `hooks/use-chat.ts` | Conversations, streaming with rAF-batched token updates, stop/regenerate/feedback, localStorage persistence, undoable deletes |
| Transport | `lib/api.ts` | `fetchModels`, `streamChat` (fetch + SSE parser), `ApiError` with friendly messages |
| Presentation | `components/chat/*` | Sidebar, model picker, message list/item, markdown, composer, empty state |
| Primitives | `components/ui/*` | shadcn/ui (Radix base, new-york style) |
| Branding | `lib/config.ts` | `APP_CONFIG` app name, description, placeholder user |

### Why same-origin proxying

The browser only ever talks to `/api/*` on the Next.js origin; `next.config.ts`
rewrites to `API_URL`. Benefits: no CORS in production, the API can stay on a
private network, and one domain/TLS cert. `compress: false` is set because gzip
buffering would hold back streamed tokens.

### Streaming performance

Tokens arrive far faster than 60 fps. `use-chat.ts` appends deltas to a local
buffer and flushes once per `requestAnimationFrame`, so React renders at most
once per frame regardless of token rate. Persistence is skipped while streaming
and runs once when the reply ends.
