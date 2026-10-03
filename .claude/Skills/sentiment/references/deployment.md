# Deployment

## Docker Compose

```bash
cp api/.env.example api/.env       # optional
docker compose up --build          # web :3000, API :8000
docker compose run --rm api python -m app.download   # optional: pre-fill the model cache
```

**API image:**
- Built from `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, running on
  `python:3.12-slim-bookworm`, as the non-root user `app`.
- Sets `ENVIRONMENT=production`, so `/docs` is hidden. `api/.env.example` leaves
  `ENVIRONMENT` commented out so it doesn't override this.
- Sets `HF_HOME=/models`; the `models` volume keeps downloads across rebuilds.

**Web image:**
- `node:24-alpine`, standalone output, runs as the `node` user.
- `API_URL` is a **build arg** (rewrites are baked in at build time).

**Image size:** `torch==2.2.2` from PyPI on Linux includes CUDA 12.1 libraries,
so the API image is several GB. For CPU-only servers, switch torch to the CPU
wheel index (snippet in the project README; it's `[[tool.uv.index]]` plus
`[tool.uv.sources]`, then `uv lock`).

**GPU:** uncomment the `deploy.resources.reservations.devices` block in
`docker-compose.yml`; it needs the NVIDIA Container Toolkit. `DEVICE=auto`
picks CUDA.

## Reverse proxy and timeouts

The first request for a model downloads and loads it. That can take minutes,
and so can long batches on CPU. Every hop must allow it:

- Next.js rewrite: `experimental.proxyTimeout: 600000` is set in `next.config.ts`
  (the default of 30 s breaks first loads).
- nginx in front: `proxy_read_timeout 600s; proxy_send_timeout 600s;`
- The web client times predictions out at 10 minutes (`lib/api.ts`).

To avoid slow first requests altogether:
- run `python -m app.download` at build or deploy time;
- keep `PRELOAD_MODELS` for the models users hit first;
- set `HF_HUB_OFFLINE=1` so production never reaches the Hub.

## Capacity

- Memory is about the safetensors size per loaded model (0.27–0.67 GB fp32),
  plus PyTorch overhead. Use `ENABLED_MODELS` to load only what is used.
- One forward pass runs per model at a time (a per-model lock). Throughput
  scales with processes or replicas, each holding its own copy of the models.
  On CPU, set `TORCH_THREADS` to cores ÷ processes.
- `BATCH_SIZE=32` suits CPU. A GPU can take 64–128 for short texts.
- Explanations cost `EXPLAIN_STEPS` extra forward and backward passes. Lower it,
  or set 0, on busy CPU servers.

## Security checklist

- Put authentication in front of the API before exposing it. Inference burns
  CPU/GPU and there are no rate limits built in (add them at the proxy).
- `ENVIRONMENT=production` hides the OpenAPI docs.
- `CORS_ORIGINS` only matters for clients calling the API directly; the web app
  goes through its own origin.
- Weights: safetensors only (no pickle execution), from pinned revisions.
- CSV export neutralises formula cells (`=`, `+`, `-`, `@`); keep that when you
  change the export.
- Texts are never logged by the app. Keep it that way; they may be customer data.

## Offline or air-gapped

```bash
cd api && uv run python -m app.download         # on a machine with internet
# copy ~/.cache/huggingface (or MODEL_CACHE_DIR) to the server, then:
HF_HUB_OFFLINE=1 uv run fastapi run
```

Or export each model to a folder and use `MODEL_SOURCES`.
