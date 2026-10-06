# Architecture: files and the Library

```
+ menu: Add files ─► POST /api/files (multipart, chat_id) ─► originals on disk + SQLite row
                       └─► queue worker ─► engine.add_document(metadata scope=chat:<id>, doc=<id>)
+ menu: Search Library ─► collections (owner uploads via /library → POST /api/library/documents)
POST /api/chat {messages, rag:{collections, files, chat_id}}
  └─► resolve_scope: look up ids → filter (scope="c:a" OR doc="d1"), skip stale files
  └─► engine.stream(turns, [store], filter) ─► meta · delta* · sources{cited_text, sources} · done
Web: [n] → citation buttons, Sources list, passage panel, "Open original" (/api/files/{id}/content)
```

People ask about documents two ways, both from the composer's **+** menu:

- **Add files**: files attached to a chat (PDF, Word, Excel, PowerPoint, ODT,
  text, CSV, Markdown, HTML, JSON, code; 10 per message, 25 MB each). Later
  questions in that chat keep searching them.
- **Search Library**: shared collections managed by owners at `/library`
  (Overview, Documents, Collections, Retrieval test, Storage, Index settings).

Answers stream like any reply, then a `sources` event replaces the text with a
version carrying `[n]` markers and the passages. The UI turns `[n]` into
buttons, lists Sources under the answer, and opens a side panel with the
passage and an "Open original" link.

## Turning it on

```bash
# api/.env
GEMINI_API_KEY=...          # Gemini File Search (also enables the Gemini chat provider)
RAG_ENGINE=offline          # or: local keyword stand-in, no key (dev + tests)
LIBRARY_TOKEN=...           # owner access; required in production
```

Off (no key, no `RAG_ENGINE`): `/api/library/config` says `enabled: false`, the
+ menu shows photos only and `/library` explains how to turn it on.

## Backend (`api/app/library/`)

| File | Role |
|---|---|
| `engine.py` | `RagEngine` protocol, `Turn`, `Source`, `Answer`, `Delta`, `NOT_FOUND`, `build_filter` |
| `gemini.py` | Gemini File Search engine: one store, resumable upload + operation polling with retries, `generate_content_stream` with the `file_search` tool, `purge` by `doc` metadata |
| `offline.py` | `OfflineClient`: same SDK surface and types (stores, documents, operations, grounding metadata) with keyword search and PDF/DOCX text extraction |
| `citations.py` | Grounding metadata → `[n]` markers (byte offsets, deduped sources, `grounded`) |
| `db.py` | SQLite (WAL): collections, documents, activity, daily search counts |
| `service.py` | Uploads (streamed, sha256, size limits, duplicates), indexing queue + resume, retention sweep, scope checks, answering, overview |
| `routes.py` | `/api/files*` (anyone) and `/api/library/*` (owner token) |
| `__init__.py` | `build_engine(settings)` and `mount_library(app, ...)` (returns a lifespan) |

`app/library_chat.py` turns a `ChatRequest` with `rag` into the normal chat
event stream (`meta` → `delta`* → `sources` → `done`).

### Rules that matter

- **One store, server-built filters.** Each document has metadata
  `scope=c:<collection>` or `chat:<chat id>`, and `doc=<id>`. The filter is
  built only from ids the server looked up: `(scope="c:a" OR doc="d1")`.
- **Chat files belong to a chat.** `rag.chat_id` is required for isolation;
  ids of other chats, Library documents, or deleted/expired files are skipped
  (a `notice` says how many), so an old file never breaks a chat. If nothing is
  left to search: a readable error.
- **Duplicates.** The same file twice in one chat returns the existing copy
  with `reused: true`; the client must not delete it when the new chip is
  removed. In a collection, a duplicate is a 409 unless `replace=true`.
- **Keep originals.** Gemini deletes raw uploads after 48 h; the index stays.
  Originals in `LIBRARY_DATA_DIR` power "Open original" and re-indexing.
- **Serving files.** Only PDF and `text/plain` inline; everything else as an
  attachment, with `nosniff` and a sandbox CSP (uploaded HTML must never run).
- **Orphans.** An upload that times out or is cut off by a restart can still
  finish on Google's side; `purge(store, doc_id)` deletes every copy with that
  `doc` metadata before retrying or after failing.
- **Citations map back** by `retrieved_context.document_name`, falling back to
  the chunk's `doc` custom metadata.
- **Answer contract.** Gemini answers only from File Search results, otherwise
  exactly "I couldn't find that in the documents." (`grounded=false`, no
  sources). Files are answered by the engine's model (`RAG_MODEL` for
  Gemini); if another model was picked, `meta.notice` says so (not a fallback).
  The stream and the UI take the engine's `name`, `label`, `local` and `model`.
- **Owner auth.** Bearer `LIBRARY_TOKEN` (constant-time compare). Unset: open
  in development, 403 in production. Without accounts, every collection with
  documents is searchable by anyone who can chat; add sign-in before storing
  confidential collections.

## Frontend

| File | Role |
|---|---|
| `hooks/use-library-config.ts` | `/api/library/config` (on/off, limits, collections) |
| `hooks/use-chat-files.ts` | Tray: XHR upload with progress, poll until indexed, remove/discard (respects `reused`) |
| `hooks/use-chat.ts` | `send(text, {images, files, collections, newChatId})`; `ragFor` sends the last question's collections + all files in the chat + `chat_id` |
| `components/chat/composer.tsx` | + menu: Add files, Search Library (checkbox sub-menu), file chips, Library pills |
| `components/chat/message*.tsx`, `markdown.tsx` | File chips on questions, "Searching …" state, `[n]` buttons, Sources, notice |
| `components/files/*` | File chip, Sources list, passage side panel |
| `components/library/*`, `app/library/**` | Owner pages and the token prompt (token kept in sessionStorage) |

New chats upload files under a draft chat id that becomes the conversation id
on send. Deleting a chat deletes its server files after the Undo toast closes.
Dropped files are routed: photos to the photo tray, others to files.

`next.config.ts` raises the `/api` rewrite's body limit (`proxyClientMaxBodySize`
110 MB; the default 10 MB breaks uploads with "socket hang up") and
`proxyTimeout` (120 s). Library uploads go one file per request.

## Engines

`RagEngine` is the seam. Gemini File Search and the offline engine implement it
today; a self-hosted LangChain/LangGraph engine is described step by step in
`references/custom-engine.md`. On start, documents indexed by another engine
are re-queued, so switching engines re-indexes from the stored originals.

## Data model (SQLite, `LIBRARY_DATA_DIR/library.db`)

- `collections(id, name unique, description, created/updated)`
- `documents(id, kind library|chat, collection_id | chat_id, title, filename, ext, mime,
  size, sha256, status queued|processing|indexed|failed, step, error, engine,
  engine_doc_id, uses, last_used_at, uploaded_by, created/updated/indexed_at)`
- `activity(at, actor, text)` (last 500), `searches(day, count)`, `kv`
- Originals: `LIBRARY_DATA_DIR/files/<id><ext>` (name = id + allow-listed extension: no
  path traversal). WAL mode, one process. For several API instances move records to
  Postgres and originals to object storage (S3/GCS) behind the same service methods.

## Testing

- `tests/test_library.py` (offline engine through the full app) and
  `tests/test_library_gemini.py` (the real `google-genai` SDK against
  `tests/fake_gemini_api.py`, which also serves streamed `generateContent`).
- Browser: `assets/testing/files_e2e.js` with the API on `RAG_ENGINE=offline`
  and `fake_ollama_vision.py`: creates collections, uploads, checks indexing,
  duplicates, the drawer, the retrieval test, Search Library answers with
  citations, chat files, rejected types, delete-with-chat, phone layouts.
- Live Gemini answer quality needs a real key; the fakes check wire formats.
