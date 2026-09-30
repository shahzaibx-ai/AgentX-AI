# Testing

## Unit tests (API)

`api/tests/test_photos.py` has 29 tests, with no network. It needs a
`FakeProvider` that accepts `vision_models`:

```python
class FakeProvider(Provider):
    def __init__(self, ..., vision_models: set[str] | frozenset[str] = frozenset()):
        self._vision = set(vision_models)
    async def list_models(self):
        return [ModelInfo(id=m, name=m, provider=self.id, local=self.local, vision=m in self._vision)
                for m in self._models]
```

The `make_client` fixture must pass `vision_patterns=cfg.vision_models` to the
registry (the installer does both). Coverage:

- **Decoding and sniffing:** the file path string, bad base64, a
  non-image, a data URL, the declared type overridden, and the base64 copy
  dropped.
- **Limits:** per message, per request, size, 100 images counted before
  decoding, and 413 for both a Content-Length and a chunked body.
- **Routing:**
  - Auto picks the vision model, and text requests are unchanged;
  - cloud vision is used when no local model can see;
  - a chosen text-only model is refused, including a provider default or an
    unlisted model judged by name;
  - fallback goes only to vision models;
  - a photo earlier in the history still needs vision;
  - `/api/models` reports the vision flags and limits;
  - the `VISION_MODELS` patterns work.
- **Providers:**
  - what the Ollama SDK actually sends (`_copy_messages`) is base64 of the bytes;
  - the Anthropic blocks, including a photo-only message;
  - the 5 MB guard;
  - the OpenAI parts;
  - Ollama capabilities with a failed `show`, and digest caching;
  - the cloud name rules.

## Live checks

```bash
python <skill>/scripts/doctor_photos.py --api http://localhost:8000 --web http://localhost:3000 --send
```

It checks the limits, which models can see images and Auto's choice, that a
file path is refused as image data, and that a real 1×1 test photo gets a
reply. It also checks the web proxy.

## Browser test with a stand-in Ollama

`assets/testing/fake_ollama_vision.py` serves `llama3.2:latest` (text) and
`gemma3:4b` (vision) with `/api/show` capabilities. It records what each
chat request received at `GET /log`: per image, the byte count and the magic
bytes in hex. `DELETE /log` clears it.

```bash
# 1. stand-in Ollama
cd <skill>/assets/testing
uv run --with fastapi --with uvicorn uvicorn fake_ollama_vision:app --port 11434
# 2. API pointed at it (no cloud keys, so everything stays local)
cd <app>/api && OLLAMA_HOST=http://localhost:11434 uv run uvicorn app.main:app --port 8000
# 3. web
cd <app>/web && npm run build && API_URL=http://localhost:8000 npm start
# 4. test (npm i -D playwright-core in any folder; CHROME_PATH if needed)
BASE_URL=http://localhost:3000 OLLAMA_URL=http://localhost:11434 node <skill>/assets/testing/photos_e2e.js
```

It runs 35 checks and exits 1 on any failure or page error. It starts by
clearing the app's storage. Screenshots are saved to `./photos-e2e-out`:
menu, attached, picker, text-only, sent, viewer, drop, dark text-only and
phone. **Look at them.**

Fixtures (`assets/testing/fixtures/`):
- `receipt.jpg` (900×1200);
- `large-4032x3024.jpg` (to test resizing);
- `IMG_5520.heic` (rejected by name);
- `broken.png` (text in a .png).

## What these can't test

- Real vision models: answer quality, and how Ollama decodes the images.
- Cloud APIs: request limits, and naming rules for models released later.
- A real phone camera, including HEIC from iOS and `capture`.
- Clipboard behaviour in each browser, and Safari's IndexedDB quotas.

Say so when delivering.
