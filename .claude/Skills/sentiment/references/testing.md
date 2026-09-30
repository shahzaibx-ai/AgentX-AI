# Testing

## Unit and API tests (no network)

`cd api && uv run pytest`: 43 tests in about 2 s. `tests/conftest.py` builds
tiny real checkpoints once per session, saved as safetensors:
- a BERT WordPiece model in FinBERT's label order;
- a 5-star BERT;
- DistilBERT;
- a byte-level BPE RoBERTa.

Each has a classifier bias that forces a known label, which proves the label
mapping.

| Area | Tests |
|---|---|
| Catalog | label orders match the published configs, pinned revisions, display order, Twitter preprocessing keeps the layout |
| Classifier | labels per model, parity with a plain transformers forward pass, batch = single, tokens and truncation, RoBERTa's 512 limit, **refuses `.bin`**, rejects label-count mismatch |
| Explanations | **IG completeness** for all architectures, the explanation covers the original text, `[UNK]` is attributed, no token score is dropped in word mapping, explanations off by default and with 0 steps |
| API | health, models and limits, load endpoint, enabled-models filter, predict (default and chosen model), validation messages, limits, 404, batch order and validation, load failure → 503 plus retry, background preload status, concurrent first requests load once, settings validation, docs hidden in production, CORS, pinned torch version |

Add a test with every backend change. Never add a test that downloads a model.

`scripts/test_check_model.py` covers the model checker's decisions offline:
`cd api && uv run pytest <skill>/scripts/test_check_model.py`.

## Gates

```bash
bash <skill>/scripts/verify.sh <project>     # ruff, format, pytest, npm ci, typecheck, build
```

## End to end without Hugging Face

When the Hub is unreachable (CI, sandboxes), train tiny stand-ins and point the
API at them:

```bash
cd <project>/api
uv run python <skill>/assets/testing/train_tiny_models.py /tmp/tiny-models
# paste the printed MODEL_SOURCES=... line into api/.env
uv run fastapi dev
cd ../web && npm run build && npm start
BASE_URL=http://localhost:3000 node <skill>/assets/testing/studio_e2e.js
```

`studio_e2e.js` needs `playwright-core` plus a Chromium (`CHROME_PATH`, or
`npx playwright install chromium`). It reads `/api/models` and adapts to the
enabled models. It checks:
- default selection, and an example → a result with the right number of bars
  and word influence;
- Ctrl+Enter plus history;
- switching to every other model re-runs with that model (the result header
  names it);
- batch sample → 8 rows and the CSV export header;
- the Model tab lists every model;
- dark mode, and the phone width has no horizontal scroll.

Screenshots go to `./studio-e2e-out`; look at them.

Also try by hand:
- stop the API: the banner appears, and clears within 5 s of restarting;
- `Try again` recovers;
- upload a CSV with quotes and a `text` column.

## Live check with real models

```bash
python <skill>/scripts/doctor.py --api http://localhost:8000 --web http://localhost:3000 --load-all
```

This loads and predicts with every enabled model. The first run downloads them.
