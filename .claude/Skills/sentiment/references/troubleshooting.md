# Troubleshooting

Start with `python <skill>/scripts/doctor.py --api http://localhost:8000 --web http://localhost:3000`.

| Symptom | Cause | Fix |
|---|---|---|
| 503 "…require users to upgrade torch to at least v2.6…" | A `.bin` checkpoint reached transformers | Keep `use_safetensors=True`; pin a safetensors revision (`check_model.py`) |
| 503 "…does not appear to have a file named model.safetensors" | The model or revision has no safetensors | Use the bot PR revision, or convert to a local folder plus `MODEL_SOURCES` |
| 503 "Couldn't connect to huggingface.co" | No internet, or blocked | Pre-download with `python -m app.download`, then `HF_HUB_OFFLINE=1` |
| First Analyze with a new model fails after ~30 s with HTTP 500 | A proxy timeout in front of the API | `experimental.proxyTimeout` in `next.config.ts` (already set); raise nginx `proxy_read_timeout` |
| UI: "The API didn't answer (HTTP 500)…" | API down (the proxy returns 500), or an unhandled server error | Start the API; read its log |
| UI banner "Can't reach the API" | API not running, or `API_URL` wrong at web build time | `cd api && uv run fastapi dev`; rebuild the web app after changing `API_URL` |
| `RuntimeError: DEVICE=cuda but no CUDA GPU…` | Forced device not available | `DEVICE=auto`, or install GPU drivers / the NVIDIA container toolkit |
| Very slow on CPU | Large texts with explanations, many threads | `EXPLAIN_STEPS=8` or `0`, `TORCH_THREADS`, shorter `MAX_LENGTH`, a GPU |
| Labels look swapped | Catalog `labels` not in `id2label` order | Fix the order from the model's `config.json` (see the warning in the logs) |
| An emoji or rare word never gets influence | Old code marked `[UNK]` special | Use `return_special_tokens_mask=True` (current code) |
| History shows the wrong model name | The model was removed from `ENABLED_MODELS` | Harmless; the id's last part is shown |
| `npm warn EBADENGINE` | Node < 24 | Install Node 24 (`.nvmrc`); builds still run on 20.9+ |
| Tests fail only on one machine | Env vars leaking into `Settings` | Tests use `_env_file=None`, an autouse fixture that clears setting env vars, and import `app.factory`, never `app.main` |
| CSV upload merges rows | Old parser treated a mid-field `"` as quoting | Quotes only open at a field's start (current code) |
