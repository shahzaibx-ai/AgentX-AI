# API contract

All under `/api`. Errors are `{"detail": "<readable message>"}`.

## Anyone (chat)

| Method | Path | Notes |
|---|---|---|
| GET | `/library/config` | `{enabled, reason, engine, label, local, model, owner_auth: open|token|disabled, limits{chat_file_max_bytes, chat_files_per_message, library_file_max_bytes, chat_file_retention_days, extensions[]}, collections[]}`. Only collections with documents are listed |
| POST | `/files` | multipart `file`, `chat_id` (`[A-Za-z0-9_-]{1,64}`). 201 → document (`status` queued…, `reused: true` if the chat already had this file). 413 too big, 415 type, 422 empty, 503 off |
| GET | `/files/{id}` | chat files only; poll every ~1 s until `indexed` or `failed` |
| DELETE | `/files/{id}` | 204; 403 for Library documents |
| GET | `/files/{id}/content` | original; PDF and text/plain inline, everything else attachment; `nosniff`, `CSP: sandbox; default-src 'none'` |

Document: `{id, kind, title, filename, ext, mime, size, status, step, error,
collection_id, collection, chat_id, uploaded_by, uses, engine, created_at,
updated_at, indexed_at, expires_at, reused}` (times are Unix seconds).

## Chat with documents

```json
POST /api/chat
{ "messages": [...], "rag": { "collections": ["<id>"], "files": ["<id>"], "chat_id": "<chat id>" } }
```

Limits: 20 collections, 50 files. `rag` with both lists empty → an ordinary reply.

```
event: meta     {"provider":"gemini","provider_label":"Gemini File Search","model":"…","local":false,"fallback":false,"notice":null|"…"}
data:           {"delta":"…"}                                   (repeated)
event: sources  {"cited_text":"…[1]","grounded":true,"sources":[{"number":1,"title":"…","text":"…","page":2,"cited":true,"document_id":"…","kind":"library|chat","collection":"HR"}]}
event: done     {}            or   event: error {"message":"…"}
```

`grounded:false` (the "I couldn't find that in the documents." reply) carries no
sources. `notice` explains a model switch (files are answered by the engine's
model) and
skipped files ("1 earlier file in this chat is no longer available").

## Owner (`Authorization: Bearer <LIBRARY_TOKEN>`)

| Method | Path | Notes |
|---|---|---|
| GET | `/library/overview` | `totals` (by status, sizes), 14-day `searches`, `queue`, `store` health or `store_error`, `activity` |
| GET/POST | `/library/collections` | POST `{name, description}`; 409 duplicate name |
| PATCH/DELETE | `/library/collections/{id}` | PATCH 409 on a duplicate name; DELETE removes its documents → `{deleted_documents}` |
| GET | `/library/documents` | `query, collection_id, status (incl. attention), limit ≤200, offset` → `{documents, total}` |
| POST | `/library/documents` | multipart `files[]` (≤50), `collection_id`, `replace` → 201 `{accepted[], rejected[{filename, reason, duplicate}]}` (each file judged on its own) |
| GET/DELETE | `/library/documents/{id}` | |
| POST | `/library/documents/{id}/reindex` | 409 while indexing, 410 original missing |
| POST | `/library/documents/bulk` | `{action: delete|reindex|move, ids[] (≤500), collection_id?}` → `{done[], failed[{id, reason}]}` |
| POST | `/library/test` | `{question, collection_ids[]}` → `{answer, cited_text, grounded, sources, retrieval_queries, model, seconds}` |
| GET | `/library/storage` | `totals`, `quota_bytes`, `data_dir`, `largest_chat_files`, limits |
| GET | `/library/settings` | engine, models, store, chunking, top_k, concurrency, owner_auth |

401 wrong/missing token, 403 locked (production without a token), 503 off.
