---
name: add-files-library
description: Add "Add files" and a shared Library to an AI chat app, so people can ask questions about documents and get answers with numbered citations (RAG). Covers chat file uploads (PDF, Word, Excel, PowerPoint, text, CSV, Markdown, code) with progress and indexing states; a Search Library menu for shared collections; [n] citation buttons, a Sources list and a passage panel; and owner pages at /library (overview, documents, collections, retrieval test, storage, index settings). The FastAPI side covers Gemini File Search behind a pluggable RagEngine (offline test engine included), scope isolation, SQLite records, an indexing queue, retention and an owner token. Use whenever the user wants chat with files or documents, file attachments, a knowledge base or document library, RAG, citations, Gemini File Search, or a LangChain/LangGraph + Ollama + pgvector/Qdrant RAG engine in a chat app or a fullstack-ai-assistant project. Also use to customise, secure, test or debug this feature (upload fails, stuck indexing, no citations, 413/415, owner token).
---

# Add files + Library

A complete, tested document feature for a chat app. People attach files to a
chat or pick shared collections; answers come only from those documents, with
numbered citations that open the passage and the original. Owners manage the
collections at `/library`.

```
+ menu: Add files ─► POST /api/files ─► original on disk + SQLite ─► queue ─► engine (scope=chat:<id>)
+ menu: Search Library ─► collections that owners fill at /library
POST /api/chat {rag:{collections, files, chat_id}} ─► server-built filter ─► engine.stream
  ─► meta · delta* · sources{cited_text "[1]", passages} · done ─► [n] buttons, Sources, passage panel
```

The installer report says which edit list each file got. Most files get the
same edits with or without voice mode; only the chat UI files and `main.py`
differ.

Verified October 2026 (Next.js 16, React 19, TypeScript 7, FastAPI, Python 3.13,
google-genai 2.26). The installer was run on the fullstack-ai-assistant
template (with photos) both with and without voice mode. Each result matched
the hand-verified reference byte for byte (`uv.lock` too, apart from newer
package releases), and a re-run changed nothing. Each result passes ruff, pytest (96 API tests with voice, 77
without), the typecheck and the production build. The installed app also
passed a 25-check browser test (desktop, dark, 390 px phone) and the doctor's
live upload → index → cited answer check. Gemini itself was checked with the
real SDK against a local fake of its REST API; answer quality needs a real key.

## Workflow

### 1. Identify the target

| Project | Path |
|---|---|
| Built from **fullstack-ai-assistant** with photos (`web/components/photos/` exists), with or without voice | Run the installer (step 2) |
| fullstack-ai-assistant without photos | Install the **add-photos** skill first (the Library uses its + menu, drop zone and body-size limit); the installer refuses otherwise |
| Current fullstack-ai-assistant template | Already built in; the installer reports "already wired". Go to step 3 |
| Another FastAPI backend | `references/integrate-fastapi.md` |
| Another React / Next.js frontend | `references/integrate-react.md` |
| Another backend language | Implement `references/api-contract.md`; keep the web part |

Ask at most one question, and only if it changes the build. Usually it is:
"Is it OK that files and questions go to Google (Gemini File Search), or should
everything stay on your servers?" On-premises means the self-hosted engine
(`references/custom-engine.md`); until it exists, `RAG_ENGINE=offline` works for
demos only. Defaults: 25 MB × 10 files per message, 100 MB Library files, chat
files kept 30 days after last use, one shared index. The placeholder user is
**Rizwan**.

### 2. Install (template projects)

```bash
python <skill>/scripts/install_library.py --project <app> --dry-run   # preview
python <skill>/scripts/install_library.py --project <app>             # install
```

It is safe to re-run. It:

- copies the self-contained files: `api/app/library/` (engine protocol, Gemini
  and offline engines, citations, SQLite records, service, routes),
  `library_chat.py`, the tests, fixtures and fake Gemini API; on the web side
  `app/library/**`, `components/files/*`, `components/library/*`,
  `components/ui/dialog.tsx`, `hooks/use-chat-files.ts`,
  `hooks/use-library-config.ts`, `lib/library.ts` and `lib/library-admin.ts`;
- applies anchored edits to the 21 files that wire it in, plus 3 optional
  README edits. It picks the with-voice or without-voice edit list per file;
- runs `uv lock` in `api/`. This adds `google-genai`, plus `pypdf` and
  `python-docx` as dev dependencies for the offline engine. There are no new
  npm packages.

If a customised file doesn't match, it is **left unchanged** and reported with
its edit numbers. Make those edits by hand from `references/manual-edits.md`,
or re-run with `--partial`. Exit code 1 means manual steps remain. Don't
rewrite the feature from memory; the assets encode the fixes listed under
Rules.

### 3. Configure (`api/.env`)

If `api/.env` already exists, **add** these lines to it; never replace it with
`.env.example`, or keys such as `LIVEKIT_*` (voice mode) and cloud API keys are
lost. Only a project with no `.env` starts from `cp api/.env.example api/.env`.
The installer added a commented "Files and the Library" block to `.env.example`
with every setting. The ones that matter:

```bash
GEMINI_API_KEY=...          # Gemini File Search (also the Gemini chat provider)
# RAG_ENGINE=offline        # no key: keyword search stand-in for dev, demos and tests
LIBRARY_TOKEN=...           # owner access; required in production
# Often tuned: RAG_MODEL (Gemini answer model), RAG_TOP_K (6), RAG_CHUNK_TOKENS (400),
# CHAT_FILE_MAX_BYTES (25 MB), CHAT_FILE_RETENTION_DAYS (30), LIBRARY_DATA_DIR (data/library)
```

Generate a token with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. The installer
already ran `uv sync`. Restart the API and the web app; start the API with
`uv run fastapi dev app/main.py` (or `uv sync` first), because its environment
needs `google-genai`. If the package is missing, the Library turns itself off
with "Run `uv sync`…" and everything else keeps working. Docker Compose gets a
`library` volume for the originals; rebuild the images.

**Upgrading an older install:** re-run the installer with `--force`. That
replaces the Library's own copied files, such as `api/app/library/`, and keeps
your wired files.

### 4. Verify (always, before delivering)

```bash
bash <skill>/scripts/verify_library.sh <app>     # wiring, uv sync, ruff, pytest, typecheck, build
python <skill>/scripts/doctor_library.py --api http://localhost:8000 --web http://localhost:3000 \
  --ask --token "$LIBRARY_TOKEN"     # --token only when LIBRARY_TOKEN is set
```

The doctor checks:

- the engine, limits and owner access, and the health of the index;
- that unknown file ids return 404;
- that a file over 10 MB gets through the web proxy;
- with `--ask`, a real upload → index → cited answer → delete round trip.

For UI changes, run `assets/testing/files_e2e.js` (see `references/testing.md`).
Screenshot light, dark and a 390 px phone, and look at them.

### 5. Customise

| Task | Read |
|---|---|
| How it fits together, data model, rules | `references/architecture.md` |
| Endpoints, request/stream formats | `references/api-contract.md` |
| Self-hosted RAG: LangChain/LangGraph, Ollama, pgvector or Qdrant, agentic RAG | `references/custom-engine.md` |
| Access, privacy, what goes to Google, retention | `references/security.md` |
| Wording, menu order, states, layout | `references/ux.md` |
| Tests, browser test, live checks | `references/testing.md` |
| Something failing | `references/troubleshooting.md` |

### 6. Deliver

Exclude `node_modules`, `.next`, `.venv`, `data/` and real `.env` files, then zip
and send. In a few sentences, say:

- what was installed and how it was verified (with numbers);
- what could not be tested (usually the live Gemini service without a key);
- the one decision to make: with no accounts yet, every collection is
  searchable by anyone who can chat;
- how to turn it on (`GEMINI_API_KEY` or `RAG_ENGINE=offline`, plus `LIBRARY_TOKEN`).

## Rules (the traps the assets already handle)

- **Isolation is server-side.** The metadata filter is built only from ids the
  service looked up. Files must belong to the request's `chat_id`, and Library
  ids are never accepted as chat files. Never pass client text into a filter.
- **A stale file must not break a chat.** Deleted or expired files are skipped
  with a `notice`. The request errors only when nothing is left to search.
- **Duplicates are reused.** The same file added twice in one chat returns the
  existing copy with `reused: true`, and the client never deletes a reused copy.
- **Keep the originals.** Gemini deletes raw uploads after 48 h. "Open original"
  and re-indexing need the stored copy.
- **Never serve uploads as active content.** Only PDF and text/plain open inline,
  always with `nosniff` and a sandbox CSP.
- **Orphaned index copies.** An upload that timed out or was cut off can still
  finish on the service. `purge` by the `doc` metadata runs after a failure and
  on resume.
- **The proxy body limit.** The Next.js `/api` rewrite caps bodies at 10 MB, so
  set `proxyClientMaxBodySize`. The Library uploads one file per request.
- **One answer contract.** The stream is `Delta`s, then one `Answer`. The refusal
  sentence means `grounded=false` with no sources, and `[n]` only for real
  sources. Questions about files are answered by the engine's model (`RAG_MODEL`
  for Gemini), and `meta.notice` says so when another model was picked.
- **Owner auth.** Bearer token compared in constant time. With no token it is
  open in development and locked (403) in production.
- **The Library never stops the API.** A missing package, a bad setting or an
  unwritable data folder turns it off with a reason in `/api/library/config`.
  Chat, models and voice mode keep working. Voice mode hides its button whenever
  `/api/voice/config` can't be reached, so an API that failed to start looks
  like "voice is gone". The doctor checks voice mode too.
- **The engine is a seam.** SDK types stay inside the engine modules. The UI
  and the stream take the engine's `name`, `label`, `local` and `model`, so a new
  engine needs no UI changes. Switching `RAG_ENGINE` re-indexes from the
  originals automatically.

## Scripts and assets

| Path | Purpose |
|---|---|
| `scripts/install_library.py` | Install into a template project (stdlib only) |
| `scripts/patches.py`, `patches_no_voice.py` | Generated anchored edits (with / without voice) |
| `scripts/verify_library.sh` | Wiring checks + all quality gates (CI-safe) |
| `scripts/doctor_library.py` | Live checks on a running app; `--ask` for a real round trip |
| `scripts/maintain/make_patches.py` | Regenerate edits from a verified before/after pair |
| `scripts/maintain/render_manual_edits.py` | Regenerate `references/manual-edits.md` |
| `assets/api/…`, `assets/web/…` | The feature's files |
| `assets/testing/files_e2e.js` | 25-check browser test (Playwright) |
| `assets/testing/fake_ollama_vision.py` | Stand-in Ollama for the browser test |

**Maintaining:**

1. Change a verified app.
2. Run `make_patches.py <before> <after> scripts/patches.py`, and the same for
   the without-voice pair.
3. Run `render_manual_edits.py`.
4. Re-run the installer on fresh copies of both baselines. Each result must
   equal its reference, and verify must pass.
