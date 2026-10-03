---
name: add-photos
description: Add production-ready photo input ("Add photos") to an AI chat app so users can ask vision models about images. It covers a + menu (add or take a photo), paste and drag-and-drop, browser-side resize to 2048 px with metadata stripping, HEIC/size/type errors, a tray with previews, a gallery and full-screen viewer, and IndexedDB storage with cleanup. The API side sniffs image bytes, enforces limits and a request size cap, routes photos only to vision models (Ollama capabilities, Claude, GPT-4o, Gemini, Grok, Llama 4), shows a text-only notice with a one-click switch, and formats images per provider. Use whenever the user wants image upload, photo attachments, screenshots, vision, "ask about a picture", multimodal input, or camera capture in a chat app or a fullstack-ai-assistant project, or wants to customise, test, secure or debug that feature (photos not sent, model can't see images, HEIC, too large, 413/422).
---

# Add photos

A complete, tested photo feature for a chat app. Users add photos with the
composer's **+** menu, by pasting, or by dropping them on the page. The
browser prepares them, the API checks them, and only a model that can see
images answers.

```
+ menu / paste / drop / camera
  → web: precheck (HEIC, type, size) → redraw ≤2048 px as JPEG/PNG ≤5 MB (EXIF/GPS gone)
  → IndexedDB (message keeps only metadata: id, name, size, dimensions)
  → POST /api/chat  messages[].images = [{media_type, data: base64}]   (newest 20)
  → API: 413 size cap → count check → decode + sniff magic bytes → 422 limits
  → vision routing: Auto/fallback use vision models only; chosen text-only model → error event
  → provider format: Ollama raw bytes · Anthropic image blocks · OpenAI-compatible image_url parts
```

Verified September 2026 (Next.js 16, React 19, TypeScript 7, FastAPI,
Python 3.13, ollama SDK 0.6). The installer was run on the
fullstack-ai-assistant template both with and without voice mode. Each
result matched the hand-verified reference byte for byte, and a re-run
changed nothing. Each result passes ruff, pytest (68 API tests with voice,
49 without), the typecheck and the production build. A 35-check browser
test also passed against a stand-in Ollama with one text model and one
vision model. It covers desktop, dark mode and a 390 px phone.

## Workflow

### 1. Identify the target

| Project | Path |
|---|---|
| Built from **fullstack-ai-assistant** (`api/app/main.py` has `create_app`, `web/components/chat/chat-app.tsx` exists), with or without voice mode | Run the installer (step 2) |
| Current fullstack-ai-assistant template | Photos are already built in; the installer reports "already wired". Skip to step 4 |
| Another FastAPI backend | `references/integrate-fastapi.md` |
| Another React / Next.js frontend | `references/integrate-react.md` |
| Another backend language | Implement the contract in `references/architecture.md`; keep the web part |

Ask at most one question, and only if the answer changes the build. Example:
"Should photos ever go to cloud providers?" If not, set `VISION_MODELS` and
the cloud keys accordingly, or turn off `ALLOW_CLOUD_FALLBACK`. Defaults:
5 photos per message, 10 MB each, 20 per request, HEIC rejected with a
how-to, and photos stored in the browser. The placeholder user name is
**Rizwan**.

### 2. Install (template projects)

```bash
python <skill>/scripts/install_photos.py --project <app> --dry-run   # preview
python <skill>/scripts/install_photos.py --project <app>             # install
```

It is safe to re-run, and adds **no dependencies**. It:

- copies the self-contained files: `api/app/images.py`, `vision.py`,
  `core/body_limit.py`, `tests/test_photos.py`, `web/lib/images.ts`,
  `image-store.ts`, `hooks/use-attachments.ts`, `use-image-url.ts` and
  `components/photos/*`;
- applies anchored edits to the 22 files that wire photos in (plus optional
  README edits).

There are two edit lists, with and without voice mode, and the installer
picks the one that fits each file.

If a customised file doesn't match, it is **left unchanged** and reported
with its edit numbers. Make those edits by hand from
`references/manual-edits.md`, or re-run with `--partial`. Exit code 1 means
manual steps remain. Don't rewrite the feature from memory: the assets
contain fixes for several non-obvious traps (see "Rules" below).

### 3. Configure

Nothing is required. Optional settings in `api/.env`:

```bash
MAX_IMAGES_PER_MESSAGE=5        # the web app reads limits from /api/models
MAX_IMAGES_PER_REQUEST=20       # whole history; newest kept, older become a text note
MAX_IMAGE_BYTES=10485760        # per photo; the request cap (413) is derived from these
VISION_MODELS=[]                # extra fnmatch patterns, e.g. ["my-org/*-vl"]
```

Install a model that can see images: `ollama pull gemma3` (or `llava` or
`qwen2.5vl`), or set a cloud key.

### 4. Verify (always, before delivering)

```bash
bash <skill>/scripts/verify_photos.sh <app>      # wiring + ruff/pytest + typecheck/build
python <skill>/scripts/doctor_photos.py --api http://localhost:8000 --web http://localhost:3000 --send
```

For a browser test without real models, run the stand-in Ollama, then point
the API at it and run the test:

```bash
cd <skill>/assets/testing && uv run --with fastapi --with uvicorn uvicorn fake_ollama_vision:app --port 11434
# API with OLLAMA_HOST=http://localhost:11434, web on :3000, then:
BASE_URL=http://localhost:3000 node <skill>/assets/testing/photos_e2e.js
```

Look at the screenshots it writes (light, dark, phone). Details are in
`references/testing.md`.

### 5. Deliver

Report:
- what was installed;
- which checks passed, with numbers;
- what could not be tested here (real vision models, cloud APIs, a phone
  camera).

Give the run commands and `ollama pull gemma3`.

## Rules that keep photos correct and safe

- **Bytes to Ollama, never strings.** The Ollama SDK treats a string image
  as a file path and reads it if the file exists. The API decodes base64
  once and passes `image.raw`, and `verify_photos.sh` checks this.
- **Trust the file signature, not the declared type.** Sniff the first
  bytes: `ffd8ff`, `89504e47`, `GIF8`, `RIFF…WEBP`.
- **Limit before decoding.**
  - The `BodySizeLimit` middleware returns 413 while the body streams in.
  - A `mode="before"` validator refuses more than 100 images.
  - Decoded images drop their base64 copy.
- **Send what every provider accepts.** Redraw on a canvas as JPEG, or PNG
  for PNG input, at most 2048 px and 5 MB (Anthropic's limit). Redrawing
  also applies EXIF rotation and removes GPS data. GIFs keep their first
  frame.
- **Photos need a vision model.**
  - With photos anywhere in the history, Auto and fallback skip text-only
    models.
  - A chosen text-only model (or a provider's default) gets a clear error
    event.
  - The UI blocks sending and offers "Use <vision model>".
  - For earlier photos with a text-only model, the web app sends a
    "[Shared 2 photos]" note instead.
- **Vision flags.** For Ollama, use `ollama show` → `capabilities`, cached
  per digest. For cloud models, use the name rules in `app/vision.py`, plus
  `VISION_MODELS` for any the rules miss.
- **Storage.** Messages keep metadata only, and the photo bytes live in
  IndexedDB. Cleanup at load deletes unreferenced photos that are **older
  than a day**, because another tab may be mid-send. Without IndexedDB,
  photos stay in memory for the tab.
- **Say where photos go.** The line under the input says "Photos stay on
  this computer: <model> runs locally" or "Photos are sent to <provider>".
  It shows while photos are attached and in chats that have photos.
- **Paste.** If the clipboard also has plain text and a text field has
  focus (Office copies both), let the text paste.
- **Voice mode** (if present) receives text only: photos become a note. The
  voice button shows only when there is no text and no photo.
- **Design.** Use neutral shadcn tokens and no gradients. Keep the error
  wording in `references/ux.md` and the aria-labels, which the browser test
  relies on.

## References

| Need | Read |
|---|---|
| Data shapes, API contract, routing, limits, storage, config | `references/architecture.md` |
| Add to another FastAPI backend (schema, providers, routing) | `references/integrate-fastapi.md` |
| Add to another React / Next.js frontend (components, hooks, props) | `references/integrate-react.md` |
| Exact edits the installer makes (both variants, numbered) | `references/manual-edits.md` |
| States, wording, layout, accessibility | `references/ux.md` |
| Unit tests, stand-in Ollama, browser test | `references/testing.md` |
| Symptom → cause → fix, extending (HEIC, server storage, PDFs) | `references/troubleshooting.md` |

## Contents

```
scripts/install_photos.py        installer (stdlib; --dry-run, --force, --partial, --skip api|web)
scripts/patches.py               edits for projects with voice mode (generated)
scripts/patches_no_voice.py      edits for projects without voice mode (generated)
scripts/verify_photos.sh         wiring + quality gates (CI-safe)
scripts/doctor_photos.py         live checks: limits, vision models, file-path rejection, a test photo
scripts/maintain/                regenerate the edit lists and manual-edits.md
assets/api/                      images.py, vision.py, core/body_limit.py, tests/test_photos.py
assets/web/                      lib/images.ts, lib/image-store.ts, hooks/*, components/photos/*
assets/testing/                  fake_ollama_vision.py, photos_e2e.js, fixtures/
```

When the photo code changes in the template, update `assets/`, then
regenerate the edits:

```bash
python scripts/maintain/make_patches.py <pre-photos> <photos> scripts/patches.py
python scripts/maintain/make_patches.py <pre-photos-no-voice> <photos-no-voice> scripts/patches_no_voice.py
python scripts/maintain/render_manual_edits.py
```

Re-test the installer on pre-photos copies; the results should match byte
for byte.
