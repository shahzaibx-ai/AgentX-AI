# Sentiment Studio

Sentiment analysis with PyTorch and Hugging Face Transformers: a FastAPI service
that serves four fine-tuned transformer models, and a Next.js workspace to
analyze a text, run batches and inspect the models.

```
sentiment-studio/
├── api/   FastAPI · Python 3.12 · uv · Ruff · pytest · torch 2.2.2 · transformers 4.57.6   → :8000
└── web/   Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui · Node 24      → :3000
```

## Models

| Model | Hugging Face id | Domain | Labels |
|---|---|---|---|
| DistilBERT SST-2 (default) | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` | Topic: reviews, comments, headlines | negative, positive |
| FinBERT | `ProsusAI/finbert` | Financial news and reports | negative, neutral, positive |
| Twitter RoBERTa | `cardiffnlp/twitter-roberta-base-sentiment-latest` | Tweets and social posts | negative, neutral, positive |
| Multilingual BERT | `nlptown/bert-base-multilingual-uncased-sentiment` | Product reviews (EN, NL, DE, FR, ES, IT) | 1–5 stars |

Models download from the Hugging Face Hub on first use (268–670 MB each) and
stay in memory. The default model loads in the background at startup.

## Quick start

```bash
# 1. API (terminal 1)
cd api
uv sync
cp .env.example .env            # optional; defaults work
uv run fastapi dev              # http://localhost:8000 · docs at /docs

# 2. Web (terminal 2)
cd web
npm install
npm run dev                     # http://localhost:3000
```

The web app calls `/api/*` on its own origin and Next.js forwards it to the API
(`API_URL`, default `http://localhost:8000`), so there is no CORS setup.

## What you can do

- **Analyze:** label and confidence, the probability of every class, word
  influence (integrated gradients: blue words pushed toward positive, red toward
  negative), token list and a truncation warning past 512 tokens. Examples match
  the selected model's domain. Ctrl/⌘ + Enter runs it.
- **Batch:** paste one text per line or upload a CSV (`text`, `review`,
  `sentence`, `comment`… column) or TXT file, up to 1,000 rows. See the label
  split, average confidence and low-confidence rows, then filter and export as
  CSV with every class probability.
- **Model:** model card, runtime (device, limits), load models ahead of time,
  switch models, API reference.
- History of recent analyses (kept in the browser), light and dark themes, and
  a phone layout.

## API

| Method | Path | Body → response |
|---|---|---|
| GET | `/api/health` | → `{status, version, device, models: {id: status}}` |
| GET | `/api/models` | → `{default_model, device, limits, models: [...]}` |
| POST | `/api/models/load` | `{model}` → model info once loaded |
| POST | `/api/predict` | `{text, model?, explain?}` → `{label, score, probs, tokens, num_tokens, truncated, attributions, model, device, latency_ms}` |
| POST | `/api/predict/batch` | `{texts, model?}` → `{model, device, latency_ms, results: [{label, score, probs, num_tokens, truncated}]}` |

```bash
curl -s localhost:8000/api/predict -H 'content-type: application/json' \
  -d '{"text": "Shares rose after strong earnings.", "model": "ProsusAI/finbert"}'
```

`probs` always lists every class from most negative to most positive. Errors are
JSON `{"detail": "..."}`: 404 unknown model, 422 invalid input or over a limit,
503 model failed to load (the message says why).

## Configuration

All backend settings are environment variables (or `api/.env`); see
`api/.env.example`. The most useful ones:

| Variable | Default | |
|---|---|---|
| `DEVICE` | `auto` | `auto` picks CUDA, then Apple MPS, then CPU |
| `DEFAULT_MODEL` / `ENABLED_MODELS` | DistilBERT / all four | JSON list for `ENABLED_MODELS` |
| `PRELOAD_MODELS` | the default model | loaded in the background at startup |
| `MODEL_SOURCES` | `{}` | `{"<model id>": "/local/folder"}` to serve a local copy |
| `MAX_TEXT_CHARS` / `MAX_BATCH_ITEMS` | 5000 / 1000 | request limits |
| `EXPLAIN_STEPS` | 16 | integrated-gradients steps; `0` turns word influence off |
| `ENVIRONMENT` | `development` | `production` hides `/docs` |

Web: `API_URL` (build time and server side) sets where `/api` is forwarded.

### Offline servers

```bash
cd api
uv run python -m app.download       # config, tokenizer and model.safetensors only
HF_HUB_OFFLINE=1 uv run fastapi run
```

### GPU and CPU

`torch==2.2.2` from PyPI includes CUDA 12.1 on Linux, so NVIDIA GPUs work out of
the box (`DEVICE=auto`). Apple Silicon uses MPS. On a CPU-only Linux server you
can install the much smaller CPU build by adding this to `api/pyproject.toml`,
then running `uv lock && uv sync`:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu", marker = "sys_platform == 'linux'" }
torchvision = { index = "pytorch-cpu", marker = "sys_platform == 'linux'" }
```

## Docker

```bash
cp api/.env.example api/.env      # optional
docker compose up --build         # web → http://localhost:3000, API → http://localhost:8000
```

Models are cached in the `models` volume, so they download once. To fill it in
advance: `docker compose run --rm api python -m app.download`. For an NVIDIA
GPU, uncomment the `deploy` block in `docker-compose.yml`.

## Why safetensors only

torch is pinned to 2.2.2, and transformers refuses to unpickle `pytorch_model.bin`
files on torch < 2.6 because of CVE-2025-32434. The API therefore always loads
`model.safetensors`. FinBERT and Twitter RoBERTa publish safetensors only on the
Hugging Face conversion bot's pull-request revisions, so the catalog pins those
revisions (`refs/pr/29`, `refs/pr/43`). The Model view shows each model's revision.

## Quality checks

```bash
cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd web && npm run typecheck && npm run build
```

The backend tests build tiny real BERT, DistilBERT and RoBERTa checkpoints on the
fly, so they exercise the actual PyTorch/Transformers code with no downloads:
label mapping per model, batching, truncation, the safetensors-only rule, the
integrated-gradients completeness property, and every endpoint and error path.

## Production checklist

- Set `ENVIRONMENT=production` and put the web app behind HTTPS.
- Add authentication before exposing the API publicly; inference costs CPU/GPU time.
- One API process holds each model in memory (0.3–0.7 GB per model). Scale with
  more processes or replicas, and use `ENABLED_MODELS` to load only what you need.
- History lives in each user's browser. Add a database if you need shared history.
