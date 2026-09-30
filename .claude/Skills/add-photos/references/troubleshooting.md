# Troubleshooting

Start with `python <skill>/scripts/doctor_photos.py --api http://localhost:8000 --web http://localhost:3000 --send`.

| Symptom | Cause | Fix |
|---|---|---|
| No + button | Web part not installed, or `attachments` not passed to `Composer` | Run the installer, or wire it as in `integrate-react.md` |
| Notice "No model that can see images…" | No vision model installed or configured | `ollama pull gemma3` (or `llava`, `qwen2.5vl`), or add a cloud key. Then use **Refresh models** |
| A vision model isn't marked "Sees images" | Old Ollama without `capabilities` whose name isn't in the rules, or a new cloud model | Update Ollama, or add a pattern to `VISION_MODELS` (e.g. `["*-vl","my-org/*"]`) |
| A text-only model is marked "Sees images" | A name rule is too broad | Narrow the rule in `app/vision.py` and add a test in `test_vision_rules` |
| The error event says "<model> can't see images" | A text-only model was chosen, or the provider's default model can't see | Pick a vision model, or change `*_MODEL` |
| 413 "Request is too large…" | Too many or too large photos (API callers), or the limits were lowered | Send fewer photos. The web app keeps requests under the limit automatically |
| 422 "Only JPEG, PNG, WebP and GIF…" | The data isn't an image in those formats (e.g. HEIC renamed to .jpg, or AVIF) | The web app redraws everything as JPEG/PNG. API callers must convert first |
| 422 "Image data is not valid base64" | A file path or URL was sent as `data` | Send base64 or a `data:` URL. URLs are not fetched, on purpose |
| Anthropic: "photos must be under 5 MB" and a fallback | An API caller sent a photo over 5 MB | Resize to 2048 px (`prepareImage` does). The web app caps sends at 5 MB |
| "This photo is no longer stored in this browser" | Site data was cleared, a private window was closed, or another browser was used | Expected with browser storage. Use server storage when you add accounts (below) |
| Photos vanish after reload in a private window | IndexedDB is unavailable, so photos lived in memory | Expected. Chat text survives if localStorage works |
| Pasting a table from Excel attaches an image | Old paste handler | The current handler lets text through when a text field has focus |
| The dropped file opens in the tab | `PhotoDropZone` isn't mounted | Mount it once at page level. It guards drops even while disabled |
| "Looking at…" but the reply ignores the photo | The model can't really see (wrong flag), or the prompt is weak | Check `/log` with the stand-in, and the vision flag. Try `gemma3:4b` or a cloud model |
| Ollama is slow to list models | `show` is called per model | Results are cached by digest. Only new or re-pulled models are asked (4 at a time, 5 s each) |
| Sideways photos | The browser didn't apply EXIF rotation | Redrawing on a canvas applies it in current browsers. Keep `prepareImage` |
| Typecheck: `Property 'images' does not exist` | `web/lib/types.ts` wasn't updated | Add `ChatImage` and `images?` (manual-edits, types.ts) |
| pytest: `unexpected keyword 'vision_models'` | `tests/conftest.py` FakeProvider wasn't updated | See `testing.md` |

## Extending

- **HEIC.** Add a browser decoder (e.g. `heic2any`, about 2 MB, loaded only
  when needed) and convert to JPEG before `prepareImage`. Then remove the
  HEIC precheck.
- **Server storage (accounts).** Upload each prepared blob to object storage
  (S3/R2/GCS) and keep `ChatImage.id` as its key. Replace
  `lib/image-store.ts` (`saveImage`, `loadImage`, `deleteImage`,
  `imageUrl`). You can then send ids instead of base64 and have the API
  fetch the bytes. Keep the size and type checks on the server.
- **Per-user limits and costs.** Count images per user in the chat route.
  Cloud vision is billed per image tile, roughly by pixel count, so the
  2048 px edge limits cost.
- **PDFs and documents.** Make these a separate attachment kind with text
  extraction; don't overload `images`.
- **More formats in.** Anything the browser can decode (AVIF, BMP) can be
  accepted by adding it to `ACCEPTED_TYPES`. It is redrawn as JPEG/PNG
  anyway.
