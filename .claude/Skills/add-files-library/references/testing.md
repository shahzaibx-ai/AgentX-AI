# Testing

```bash
bash <skill>/scripts/verify_library.sh <project>        # wiring, ruff, pytest, typecheck, build
python <skill>/scripts/doctor_library.py --api http://localhost:8000 --web http://localhost:3000 --ask
```

- `tests/test_library.py`: the offline engine through the whole app: off mode,
  config, collections, uploads (limits, duplicates, replace), chat answers with
  citations, scope isolation, chat files (reuse, skipped stale files, other
  chats ignored), indexing errors, re-index/move/bulk, retrieval test,
  overview/storage/settings, safe file serving, owner token, production lock,
  resume after restart, retention, engine switch, purge.
- `tests/test_library_gemini.py`: the real `google-genai` SDK against
  `tests/fake_gemini_api.py` (store, resumable upload with metadata and
  chunking, operation polling, streamed `generateContent` with the `fileSearch`
  tool, citations from streamed grounding, metadata fallback, purge, errors).
  It checks wire formats; answer quality needs a real key.
- **Browser** (`assets/testing/files_e2e.js`, Playwright): start
  `assets/testing/fake_ollama_vision.py` on 11434, the API with
  `RAG_ENGINE=offline` and an empty `LIBRARY_DATA_DIR`, and the web app; then
  `PROJECT=<project> OUT=/tmp/shots node files_e2e.js` (Chromium from
  `PLAYWRIGHT_CHROMIUM` or `@sparticuz/chromium`). 25 checks: collections,
  uploads, indexing, duplicate → Replace, drawer, retrieval test, settings,
  Search Library with citations and the passage panel, original via the proxy,
  chat files, voice hidden with files, rejected types, delete-with-chat, dark
  mode, 390 px phone without horizontal scroll, no page errors.
- **Live Gemini:** with a key, `doctor_library.py --ask` uploads, indexes, asks and
  deletes a tiny file; then try the Retrieval test page with your own documents.
