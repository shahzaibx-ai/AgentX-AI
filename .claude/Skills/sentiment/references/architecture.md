# Architecture

```
Browser ── /api/* ──► Next.js (web/, :3000) ── rewrite ──► FastAPI (api/, :8000)
                                                        │
                                  ModelRegistry ── lazy, thread-safe loading
                                        │
                     SentimentClassifier (per model) = fast tokenizer + PyTorch model on one device
                                        │
                     predict(): batched softmax · explain(): integrated gradients → words
```

## Backend (`api/app/`)

| Module | Role |
|---|---|
| `main.py` | Entrypoint `app = create_app()`. `[tool.fastapi] entrypoint = "app.main:app"` in pyproject makes `uv run fastapi dev` work with no path |
| `factory.py` | `create_app(settings=None, registry=None)`: CORS, docs off in production, lifespan (torch threads, background preload). Tests import this, never `main.py`, so a developer's `.env` can't affect them |
| `core/config.py` | `Settings` (pydantic-settings, `.env`); validates model lists against the catalog |
| `ml/catalog.py` | `ModelSpec` per model: id, labels in checkpoint order, polarity, pinned revision, preprocessing |
| `ml/classifier.py` | `SentimentClassifier.load()` (safetensors only) and `predict(texts, explain=...)` |
| `ml/explain.py` | `integrated_gradients()` and token→word mapping (`word_weights`, `word_attributions`) |
| `ml/registry.py` | `ModelRegistry.get(id)` loads once (per-model lock), `status()`, `preload()` (daemon thread), error capture |
| `ml/device.py` | `auto` → CUDA, then MPS, then CPU |
| `routes/` | `health`, `models` (list + load), `predict` (single + batch) |
| `schemas.py` | Pydantic request/response models, mirrored in `web/lib/types.ts` |
| `download.py` | `python -m app.download`: fetch config, tokenizer and `model.safetensors` only |

**Threading:**
- Prediction routes are plain `def`, so FastAPI runs them in its worker thread pool and PyTorch never blocks the event loop.
- Each classifier holds a lock, so one forward pass runs per model at a time. This avoids CPU oversubscription and keeps the tokenizer thread-safe.
- Status routes (`/health`, `/models`) are `async def`: they only read memory and must answer even while every worker thread waits on a model.

**Model lifecycle:**
- `not_loaded` → `loading` → `ready`, or `error` (the message is kept; the next request retries).
- `PRELOAD_MODELS` (default: the default model) load in a background thread at startup, so the API answers immediately and `/api/health` shows `loading`.
- The registry publishes the model before clearing `loading`, so status never flickers back to `not_loaded`.

**Prediction output:**
- `probs` holds every class, sorted by `ModelSpec.polarity` (most negative first), so the UI can use a fixed order for any model.
- `num_tokens` is the full tokenised length; `truncated` is true past `min(MAX_LENGTH, position limit)` (RoBERTa: 514 − 2 = 512).
- Batch results omit tokens and explanations to keep payloads small.

## Frontend (`web/`)

| Path | Role |
|---|---|
| `components/studio/studio-app.tsx` | Shell and state: views (tabs synced to `#batch` / `#model`), the analysis state machine, model-switch re-run, history actions |
| `analyze-view.tsx`, `result-view.tsx`, `probability-bars.tsx`, `word-influence.tsx` | Analyze tab |
| `batch-view.tsx` | Batch tab: paste/upload, 64-row chunks with progress and cancel, stats, filters, CSV copy/download |
| `model-view.tsx` | Model card, runtime limits, all models with load/use, endpoint list |
| `sidebar.tsx`, `topbar.tsx`, `status.tsx`, `label-pill.tsx` | History, model picker, API status chip, theme toggle, shared bits |
| `hooks/use-models.ts` | `/api/models`, selection (saved per browser), polling while offline (5 s) or loading (2 s) |
| `hooks/use-history.ts` | Recent analyses in localStorage (validated on read, max 50) |
| `lib/api.ts` | Typed client, `ApiError` (status 0 = unreachable), long timeouts for predictions |
| `lib/csv.ts` | RFC 4180 parse, text-column detection, formula-safe export |
| `lib/labels.ts` | Label → colour token, name, tone, expected stars |
| `lib/config.ts` | App name, placeholder user (Rizwan), per-domain example texts, batch sample |
| `next.config.ts` | `/api/*` rewrite to `API_URL`, `experimental.proxyTimeout` of 10 min (first model load), security headers, standalone output |

**Analysis flow:**
1. `analyze(text)` records `lastRun = {text, model}` before sending, and aborts any request still in flight.
2. On success, the result goes to history (unless it was a re-run).
3. When the selected model changes, the effect re-runs `lastRun.text` with the new model. The result header names the model that produced the result.

**Tabs:** all three stay mounted (`forceMount` plus `data-[state=inactive]:hidden`), so the batch input and results survive tab switches.
