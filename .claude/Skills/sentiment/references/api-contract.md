# API contract

Base: `http://localhost:8000/api` (the web app proxies `/api`). JSON everywhere.
Errors are `{"detail": "<message>"}`, or FastAPI's validation list for body
shape errors. `web/lib/api.ts` flattens both into one message.

| Status | When |
|---|---|
| 404 | Unknown or disabled model id (the message lists the available ones) |
| 422 | Invalid body; blank text; text over `MAX_TEXT_CHARS`; more than `MAX_BATCH_ITEMS` texts; a blank row (`Row N is empty`) |
| 503 | The model failed to load (download, network, not safetensors…); the message explains why and hints at `app.download` |

## GET /health

```json
{"status": "ok", "version": "1.0.0", "device": "cuda:0 (NVIDIA L4)",
 "models": {"ProsusAI/finbert": "ready", "nlptown/...": "not_loaded"}}
```

Model status is one of `not_loaded | loading | ready | error`.

## GET /models

```json
{
  "default_model": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
  "device": "cpu",
  "limits": {"max_length": 512, "max_text_chars": 5000, "max_batch_items": 1000,
             "batch_size": 32, "explain_steps": 16, "low_confidence": 0.6},
  "models": [{"id": "ProsusAI/finbert", "name": "FinBERT", "domain": "Financial",
              "description": "...", "languages": "English", "parameters": "110M",
              "architecture": "BertForSequenceClassification",
              "labels": ["negative", "neutral", "positive"], "revision": "refs/pr/29",
              "default": false, "status": "ready", "error": null}]
}
```

`labels` is in display order (most negative first), not checkpoint order.

## POST /models/load

`{"model": "<id>"}` → the model's `ModelInfo` once it is ready. This blocks while
the model downloads and loads (can take minutes the first time).

## POST /predict

Request: `{"text": "...", "model": "<id>" (optional), "explain": true (default)}`

```json
{
  "label": "negative", "score": 0.9731,
  "probs": [{"label": "negative", "score": 0.9731, "logit": 2.41},
            {"label": "neutral", "score": 0.0198, "logit": -1.47},
            {"label": "positive", "score": 0.0071, "logit": -2.49}],
  "tokens": ["[CLS]", "shares", "fell", "...", "[SEP]"],
  "num_tokens": 14, "truncated": false,
  "attributions": [{"text": "Shares", "weight": -0.12}, {"text": " ", "weight": 0.0},
                   {"text": "fell", "weight": -1.0}],
  "model": "ProsusAI/finbert", "device": "cpu", "latency_ms": 41.3
}
```

- `attributions` covers the **original** text exactly: joining every `text` gives
  back the input, whitespace included. `weight` runs from -1 to +1, normalised to
  the strongest word; positive means it pushed toward positive sentiment. It is
  `null` when `explain` is false or `EXPLAIN_STEPS=0`.
- `tokens` are the model's tokens after truncation. RoBERTa shows byte-level
  tokens such as `Ġgreat`.
- `latency_ms` includes the explanation.

## POST /predict/batch

Request: `{"texts": ["...", "..."], "model": "<id>"}`. Results come back in the
same order: `{"model", "device", "latency_ms", "results": [{"label", "score",
"probs", "num_tokens", "truncated"}]}`. There are no tokens and no explanations.
The web app sends 64 rows per request for progress, while the API batches
`BATCH_SIZE` rows per forward pass.

## curl

```bash
curl -s localhost:8000/api/predict -H 'content-type: application/json' \
  -d '{"text": "Revenue beat expectations.", "model": "ProsusAI/finbert", "explain": false}'
curl -s localhost:8000/api/predict/batch -H 'content-type: application/json' \
  -d '{"texts": ["love it", "hate it"]}'
```

When you change a schema, update `api/app/schemas.py` and `web/lib/types.ts`
together, and add a test in `api/tests/test_api.py`.
