# Sentiment Studio

## Stack

* **Frontend:** Node.js 24, Next.js 16, React 19, TypeScript 7, shadcn/ui — `web/` — port `3000`
* **Backend:** Python 3.12, FastAPI, uv, Ruff, pytest — `api/` — port `8000`
* **Torch & NumPy:** Torch 2.2.2, Torchvision 0.17.2, NumPy 1.26.4
* **Transformers:** transformers 4.57.6
* **Sentiment models:**
  * Financial — `ProsusAI/finbert` (positive / negative / neutral)
  * Topic — `distilbert/distilbert-base-uncased-finetuned-sst-2-english` (DistilBERT SST-2: positive / negative)
  * Social media — `cardiffnlp/twitter-roberta-base-sentiment-latest` (Twitter RoBERTa: negative / neutral / positive)
  * Product reviews — `nlptown/bert-base-multilingual-uncased-sentiment` (Multilingual BERT: 1–5 stars)

## Commands

### Frontend

```bash
cd web
npm install
npm run dev
npm install <package-name>
npm run typecheck
npm run build
```

### Backend

```bash
cd api
uv sync
uv run fastapi dev
uv add <package-name>
uv run pytest
uv run ruff check .
uv run ruff format .
uv run python -m app.download   # pre-download models (optional)
```

## Rules

* Keep frontend code in `web/` and backend code in `api/`.
* Use `uv` for Python dependencies and `npm` for frontend dependencies.
* Use Ruff for Python linting and formatting.
* Run relevant tests after every change.
* Keep changes minimal and follow existing patterns.
* Never commit `.env`, API keys, secrets, or credentials.
* Use environment variables for secrets.
* Do not introduce dependencies unless necessary.

## Project rules

* **Weights are loaded from safetensors only.** torch is pinned to 2.2.2, and
  transformers refuses pickled `pytorch_model.bin` files on torch < 2.6
  (CVE-2025-32434). `ProsusAI/finbert` and `cardiffnlp/twitter-roberta-base-sentiment-latest`
  publish safetensors only on the Hub conversion bot's PR revisions, so the catalog
  pins `refs/pr/29` and `refs/pr/43`. Keep `use_safetensors=True`; never load `.bin`.
* **Models live in `api/app/ml/catalog.py`.** Label order must match the checkpoint's
  `id2label`; `polarity` (-1…+1 per label) drives the UI order and the sign of the
  word-influence explanation.
* **Keep `web/lib/types.ts` in sync with `api/app/schemas.py`.**
* Route handlers that run PyTorch are plain `def` (FastAPI runs them in a thread pool).
* Backend tests build tiny real checkpoints in `tests/conftest.py`; they need no
  network. Don't add tests that download models.
* UI: shadcn/ui primitives, the tokens in `web/app/globals.css`, no gradients. Sentiment
  colour is always paired with a text label (blue = positive, red = negative, gray = neutral).
* The placeholder user is **Rizwan** (`web/lib/config.ts`).
