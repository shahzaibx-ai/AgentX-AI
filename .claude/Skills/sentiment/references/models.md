# Models

## The catalog (`api/app/ml/catalog.py`)

| Constant | Id | Revision | Labels (checkpoint order) | Polarity |
|---|---|---|---|---|
| `DISTILBERT_SST2` (default) | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` | `main` | negative, positive | -1, +1 |
| `FINBERT` | `ProsusAI/finbert` | `refs/pr/29` | positive, negative, neutral | +1, -1, 0 |
| `TWITTER_ROBERTA` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | `refs/pr/43` | negative, neutral, positive | -1, 0, +1 |
| `MULTILINGUAL_STARS` | `nlptown/bert-base-multilingual-uncased-sentiment` | `main` | 1 star … 5 stars | -1, -0.5, 0, 0.5, 1 |

Label order was checked against each checkpoint's `config.json` (`id2label`).
`labels` must match that index order exactly, or predictions get the wrong names.
The classifier logs a warning when the checkpoint's names differ from the
catalog's, and refuses a checkpoint whose number of labels differs.

`polarity` sorts classes for display and defines the explained quantity
(expected polarity; see `explainability.md`).

`preprocess="twitter"` (RoBERTa) replaces `@handles` with `@user` and links with
`http`, as cardiffnlp recommends. It works per word, so explanations still map
onto the user's original words.

## Why safetensors only, and the pinned revisions

The stack pins `torch==2.2.2`. transformers 4.57 calls `check_torch_load_is_safe()`
before unpickling `pytorch_model.bin` and raises on torch < 2.6 (CVE-2025-32434:
`torch.load(weights_only=True)` can still run code). safetensors files carry no
code and load on any torch. So:

- `SentimentClassifier.load()` always passes `use_safetensors=True`. A `.bin`-only
  checkpoint fails with a clear 503, never a silent fallback
  (`test_refuses_pickled_weights`).
- FinBERT and Twitter RoBERTa ship only `.bin` on `main`. Hugging Face's conversion
  bot (SFconvertbot) opened PRs holding `model.safetensors` converted from the
  same weights, so the catalog pins `refs/pr/29` and `refs/pr/43`. Tokenizer
  and config load from the same revision.
- `app.download` fetches only config, tokenizer files and `model.safetensors`,
  never `.bin`, `.h5` or `.msgpack` (FinBERT's repo is about 1.75 GB with them;
  only 438 MB is needed).

Don't "fix" a load error by dropping `use_safetensors=True` or downgrading
transformers. If the user moves to torch ≥ 2.6, `.bin` would load, but the pinned
safetensors revisions keep working either way.

## Adding a model

1. Check it (needs internet; run with the project's environment):
   ```bash
   cd api && uv run python <skill>/scripts/check_model.py <org/model> --domain "Reviews"
   ```
   This finds safetensors (on `main` or a bot PR), reads `id2label`, checks the
   tokenizer and architecture, and prints a `ModelSpec`. Set `polarity` yourself
   when the labels are generic (`LABEL_0`…), using the model card.
2. Paste the spec into `catalog.py` and add it to `CATALOG`.
3. Add example texts for its `domain` in `web/lib/config.ts` → `EXAMPLES`. The
   default examples show when the domain has none.
4. New label names? Give them colours in `web/lib/labels.ts` (`COLORS`) and a
   tone in `labelTone`. Unknown labels fall back to gray.
5. New architecture (not BERT/DistilBERT/RoBERTa)? Add a tiny builder to
   `api/tests/conftest.py`, and add it to the parametrised tests in
   `test_classifier.py` (label order, IG completeness, word coverage).
6. `uv run pytest`, then run it live with `python <skill>/scripts/doctor.py --api ... --load-all`.

Requirements for a model to work well here:
- sequence classification;
- single-label softmax (multi-label sigmoid models need code changes; see `extending.md`);
- a fast tokenizer (for word offsets);
- supports `inputs_embeds` (for explanations; all BERT-family encoders do).

## Your own fine-tuned model

Save it with `model.save_pretrained(dir, safe_serialization=True)` and
`tokenizer.save_pretrained(dir)`. Add a `ModelSpec` (any unique `id`), and point
`MODEL_SOURCES={"<id>": "/path/to/dir"}` at the folder. Local folders ignore
`revision`.

## Removing or limiting models

`ENABLED_MODELS` (JSON list) limits what is offered and loaded; `DEFAULT_MODEL`
must be one of them. The scaffolder writes these when you pass `--models`.
Nothing loads until it is used or preloaded.

## Sizes (safetensors, fp32)

DistilBERT SST-2 268 MB · FinBERT 438 MB · Twitter RoBERTa 501 MB · Multilingual BERT ~670 MB.
Memory in use is roughly the same per model.
