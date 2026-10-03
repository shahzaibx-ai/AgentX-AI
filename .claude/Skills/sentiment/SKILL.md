---
name: sentiment
description: Build, scaffold, extend, deploy or debug "Sentiment Studio", a production-ready sentiment analysis app. The backend is FastAPI (Python 3.12, uv, Ruff, pytest) serving Hugging Face transformer classifiers with PyTorch 2.2.2 and transformers 4.57.6. The models are FinBERT (financial), DistilBERT SST-2 (topic/general), Twitter RoBERTa (social) and Multilingual BERT (1-5 stars), loaded from safetensors only, with integrated-gradients word explanations. The frontend is Next.js 16 / React 19 / TypeScript 7 / Tailwind 4 / shadcn/ui with Analyze, Batch (CSV) and Model views. Use whenever the user wants a sentiment or text-classification web app or API with PyTorch and Transformers, wants to add or swap a Hugging Face sentiment model, add word-level explanations, batch or CSV sentiment scoring, rebrand this app, deploy it with Docker/GPU/offline models, or fix errors like torch.load / safetensors / model loading failures.
---

# Sentiment Studio

A tested template plus the knowledge to adapt it. Straight from the scaffolder:
43 backend tests pass (tiny real checkpoints, no downloads), Ruff is clean, and
the TypeScript 7 type check and Next.js production build pass. A browser test
covered analyze, model switching, batch/CSV, history, dark mode, phone layout,
and API offline/recovery.

```
<project>/
├── api/   FastAPI · Python 3.12 · uv · Ruff · pytest · torch 2.2.2 · torchvision 0.17.2 · numpy 1.26.4 · transformers 4.57.6   :8000
├── web/   Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui · Node.js 24                                     :3000
├── docker-compose.yml   api + web, model cache volume, optional GPU
├── CLAUDE.md            stack, commands, rules (for coding agents)
└── README.md
```

| Model | Id | Labels |
|---|---|---|
| DistilBERT SST-2 (default, "Topic") | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` | negative, positive |
| FinBERT ("Financial") | `ProsusAI/finbert` @ `refs/pr/29` | negative, neutral, positive |
| Twitter RoBERTa ("Social media") | `cardiffnlp/twitter-roberta-base-sentiment-latest` @ `refs/pr/43` | negative, neutral, positive |
| Multilingual BERT ("Product reviews") | `nlptown/bert-base-multilingual-uncased-sentiment` | 1–5 stars |

**The one rule that isn't obvious.** With torch 2.2.2, transformers refuses
pickled `pytorch_model.bin` weights (CVE-2025-32434, it requires torch ≥ 2.6).
The app loads **safetensors only** (`use_safetensors=True`). FinBERT and Twitter
RoBERTa have safetensors only on Hugging Face conversion-bot PR revisions, so
those revisions are pinned. Never remove this; see `references/models.md`.

## Workflow

### 1. Settle the brief (ask only what changes the build)

| Input | Default |
|---|---|
| App name | `Sentiment Studio` |
| Placeholder user | `Rizwan`. Never invent other person names in UI or docs |
| Models | all four, DistilBERT SST-2 default (`--models finbert,sst2,twitter,stars`) |
| Extra scope (auth, DB history, fine-tuning, new models, emotions, long docs) | none; see `references/extending.md` / `models.md` |

The user's stack spec is authoritative (Node 24, Python 3.12, exact torch,
torchvision, numpy and transformers pins). Keep those pins unless they ask to
change them.

### 2. Scaffold

```bash
python <skill>/scripts/scaffold.py --dest ./<folder> \
  --app-name "Acme Pulse" --user-name "Rizwan" \
  --description "Customer feedback sentiment for Acme" \
  --models finbert,sst2 --default-model finbert
```

This copies `assets/template/`, renames the packages (`<slug>-api`, `<slug>-web`,
lockfiles included), the UI name and user (`web/lib/config.ts`), the browser
storage keys, the API title and the READMEs/CLAUDE.md headings. It writes
`api/.env` (with `ENABLED_MODELS` / `DEFAULT_MODEL` / `PRELOAD_MODELS` when a
subset is chosen) and `web/.env.local`. It refuses a non-empty folder unless
`--force`.

Don't rebuild the project by hand or from memory. The template encodes fixes
for many non-obvious problems: the proxy timeout for first model loads,
`[UNK]` attribution, whitespace-token mapping, CSV formula injection, offline
polling, safetensors-only loading, and more.

### 3. Customise

Read only what the task needs:

| Task | Read |
|---|---|
| How the pieces fit; threading; model lifecycle; UI state flow | `references/architecture.md` |
| Endpoints, JSON shapes, errors, curl | `references/api-contract.md` |
| Add, swap, limit or self-host models; safetensors and revisions; fine-tuned models | `references/models.md` + `scripts/check_model.py` |
| Word influence (integrated gradients): math, cost, settings | `references/explainability.md` |
| UI changes, design tokens, sentiment colours, new views, a11y | `references/frontend.md` |
| Docker, GPU/CPU torch, timeouts, capacity, offline, security | `references/deployment.md` |
| Tests, tiny models, e2e, live checks | `references/testing.md` |
| Auth, shared history, fine-tuning, multi-label, long docs | `references/extending.md` |
| Anything failing | `references/troubleshooting.md` |

Rules that keep the codebase coherent:

- Models are defined only in `api/app/ml/catalog.py`. `labels` follow the
  checkpoint's `id2label` order, and `polarity` (−1…+1) drives display order and
  the explanation sign.
- PyTorch work goes in plain `def` routes (thread pool). Status routes stay
  `async def`. One lock per classifier.
- `web/lib/types.ts` mirrors `api/app/schemas.py` exactly. Change both together.
- Tests build tiny checkpoints (`api/tests/conftest.py`), with no downloads. Add
  a test with every backend change. New architecture → new tiny builder.
- UI:
  - use shadcn/ui primitives and the tokens in `web/app/globals.css`, with no
    gradients;
  - blue = positive, red = negative, gray = neutral, always with a text label;
  - check light, dark and a 390 px width.
- Every hop allows long first requests (Next `proxyTimeout`, nginx, client
  timeouts).
- Never log texts; never commit `.env`; secrets come from environment variables.

### 4. Verify (always, before delivering)

```bash
bash <skill>/scripts/verify.sh ./<folder>          # api: uv sync, ruff, format, pytest · web: npm ci, typecheck, build
```

With the servers running:

```bash
python <skill>/scripts/doctor.py --api http://localhost:8000 --web http://localhost:3000 --load-all
```

Hugging Face unreachable (CI, sandbox)? Train tiny stand-ins with
`assets/testing/train_tiny_models.py`, point `MODEL_SOURCES` at them, and run
`assets/testing/studio_e2e.js` (`references/testing.md`). Look at the
screenshots it saves. Say clearly that scores from stand-ins are meaningless.

### 5. Deliver

Zip the project without `node_modules`, `.next`, `.venv`, caches or real `.env`
files. Summarise what was built or changed, what was verified (with numbers),
and what couldn't be tested here (for example real model downloads, a GPU, a
Docker build). Give the run commands:

```bash
cd api && uv sync && uv run fastapi dev      # :8000, docs at /docs
cd web && npm install && npm run dev         # :3000
```

## Scripts and assets

| Path | Purpose |
|---|---|
| `scripts/scaffold.py` | New project from the template: rename, user, model subset (stdlib) |
| `scripts/verify.sh` | All quality gates; non-zero exit on failure |
| `scripts/doctor.py` | Tools, running API (device, per-model status, test predictions), web proxy |
| `scripts/check_model.py` | Can a Hub model be added? Safetensors revision, labels, tokenizer, architecture → prints a `ModelSpec` |
| `scripts/test_check_model.py` | Offline tests for the checker (run from a project's `api/`) |
| `assets/template/` | The project |
| `assets/testing/train_tiny_models.py` | Tiny trained stand-ins for all four models (no downloads) |
| `assets/testing/studio_e2e.js` | Browser test that adapts to the enabled models; saves screenshots |
