# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **Voice button gone after installing the Library** (and/or chat says the API is offline) | The API isn't starting. Older versions of this skill crashed the API when `GEMINI_API_KEY` was set but `google-genai` wasn't installed (the API run with plain `uvicorn`/`fastapi dev` from a venv, not `uv run`). Fix: `cd api && uv sync`, restart, and re-run the installer with `--force` to get the version that turns the Library off instead. Also check that `api/.env` still has `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` (don't recreate it from `.env.example`). `doctor_library.py` reports "voice mode is on/off" |
| No *Add files* in the + menu | `/api/library/config` says `enabled:false`: set `GEMINI_API_KEY` or `RAG_ENGINE=offline`, restart the API. Or the web can't reach the API |
| Upload over 10 MB fails, "socket hang up" in the Next log | The `/api` rewrite's default body limit: `experimental.proxyClientMaxBodySize: "110mb"` in `next.config.ts`, rebuild. Behind nginx: `client_max_body_size 110m` |
| 413 on upload | Over `CHAT_FILE_MAX_BYTES` (25 MB) or `LIBRARY_FILE_MAX_BYTES` (100 MB, File Search's maximum) |
| 415 | Type not supported (or a photo: use Add photos) |
| File stuck on "Reading the file…" | Indexing queue: see Library → Overview (queue, failures). Gemini can take a minute for big PDFs; `RAG_INDEX_TIMEOUT_SECONDS` (600) |
| "couldn't be indexed: No text could be extracted" | Scanned PDF without a text layer; OCR it first (`ocrmypdf`) |
| "Gemini API error 403: API key not valid" | Wrong key, or the key's project has no Gemini API access |
| "Gemini API error 404" on the model | `RAG_MODEL` must support File Search (Gemini 2.5+/3 Flash or Pro) |
| Answers say "I couldn't find that in the documents." | Nothing relevant retrieved: check the right collection is picked, try the Retrieval test page, raise `RAG_TOP_K`, or re-index with smaller `RAG_CHUNK_TOKENS` |
| Citations show the title but no "Open original" | The chunk didn't map back to a document (deleted since, or indexed outside this app). Re-index |
| `/library` asks for a token | `LIBRARY_TOKEN` is set; enter it. Locked in production without one: set it |
| 401 after a while on Library pages | Token changed on the server; sign out (top left) and enter the new one |
| Duplicate copies in the index after a restart | Fixed by `purge`: interrupted uploads are purged on resume. Old installs: re-index the document |
| Chat says "The files in this chat are no longer available" | They expired (`CHAT_FILE_RETENTION_DAYS`) or were deleted; add them again |
| Installer: "customised, left unchanged" | Apply that file's edits by hand from `references/manual-edits.md`, or re-run with `--partial` |
| Installer: "`uv lock` failed" | Offline; run `cd api && uv lock` later |
| `next build` panics "Symlink … points out of the filesystem root" | `web/node_modules` is a symlink; install or copy it for real |
