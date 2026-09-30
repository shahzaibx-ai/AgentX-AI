# Sentiment Studio API

FastAPI service for transformer sentiment models (PyTorch 2.2.2, transformers 4.57.6).

```bash
uv sync
uv run fastapi dev                  # http://localhost:8000, docs at /docs
uv run pytest                       # tests (no downloads)
uv run ruff check . && uv run ruff format .
uv run python -m app.download       # pre-download models for offline use
```

```
app/
  main.py            entrypoint (`app`), see [tool.fastapi] in pyproject.toml
  factory.py         create_app(settings, registry)
  core/config.py     settings from env / .env (see .env.example)
  ml/catalog.py      the four models: labels, polarity, pinned safetensors revisions
  ml/classifier.py   tokenizer + model on one device; batched prediction
  ml/explain.py      integrated gradients → word-level influence
  ml/registry.py     lazy, thread-safe loading; background preload; status
  ml/device.py       auto / cpu / cuda / mps
  routes/            /api/health, /api/models, /api/models/load, /api/predict, /api/predict/batch
  schemas.py         request/response models (mirrored in web/lib/types.ts)
  download.py        `python -m app.download`
tests/               tiny real checkpoints built in conftest.py
```

See the root README for the API reference and configuration.
