# Extending

Ask the user before large additions. Each item says where it goes.

## Authentication

- **API:** add a dependency (API key header or JWT) and include it on the
  `predict` and `models/load` routers in `factory.py`
  (`app.include_router(router, prefix="/api", dependencies=[Depends(require_key)])`).
  Keep `/health` open for container health checks.
- **Web:** Auth.js or the host's SSO in front of Next.js. Forward the credential
  in `lib/api.ts` (`headers`).

## Shared history (database)

- History lives in the browser today (`hooks/use-history.ts`).
- For shared or audited history, add `POST /api/analyses` / `GET /api/analyses`
  backed by SQLAlchemy plus Postgres, with a table of:
  - `id`, `user_id`, `model`, `label`, `score`;
  - `probs` (JSON);
  - `text` (or a hash, if texts are sensitive);
  - `created_at`.
- Swap the hook's storage calls for these endpoints.

## Fine-tuning a model on the user's data

Train separately (a notebook or a script), then serve the result as a local
model:

```python
# minimal loop; see api/tests/conftest.py for tokenizer/model construction patterns
tok = AutoTokenizer.from_pretrained(base)
model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=3, id2label=..., label2id=...)
# … train (AdamW, lr 2e-5, 2-4 epochs, eval on a held-out split) …
model.save_pretrained(out, safe_serialization=True)
tok.save_pretrained(out)
```

Then add a `ModelSpec` and set `MODEL_SOURCES={"<id>": "<out>"}`.

Report accuracy and macro-F1 on a held-out set before swapping models in.

## Multi-label or emotions (sigmoid heads)

- Models like `SamLowe/roberta-base-go_emotions` use independent sigmoids,
  not softmax. They need:
  - a `problem_type` field on `ModelSpec`;
  - `torch.sigmoid` in `classifier.predict`;
  - "top-k above threshold" instead of argmax;
  - a different polarity mapping for explanations.
- The UI's probability bars already handle any label list.
- Colours for the new labels go in `lib/labels.ts`.

## Long documents

- Anything past `MAX_LENGTH` (512 tokens) is truncated, and the UI says so.
- For documents, split into sentences or 512-token windows with overlap,
  predict each chunk, and aggregate (mean probabilities, or length-weighted).
  Return per-chunk results for a sentence-level heat map.

## Aspect-based sentiment

This is out of scope for these models. It needs an ABSA model (for example a
`yangheng/deberta-v3-*-absa` checkpoint) whose input is a text/aspect pair.
Check it with `check_model.py` first (DeBERTa-v3 tokenizers need `sentencepiece`).

## Faster inference

- GPU plus a larger `BATCH_SIZE`.
- `torch.compile` isn't worth it on torch 2.2 for these sizes.
- ONNX Runtime or quantisation would need extra dependencies and changes to the
  explanation code (it needs gradients), so keep PyTorch for explanations.
