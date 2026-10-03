# Architecture

## Data shapes

**Web: a message** (history in localStorage, photo bytes in IndexedDB under `id`)

```ts
interface ChatImage {
  id: string;                                   // IndexedDB key
  name: string;                                 // original file name
  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif"; // sent: jpeg or png
  width: number; height: number;                // as sent (≤2048 px long edge)
  size: number;                                 // bytes as sent (≤5 MB)
  resizedFrom?: string;                         // "4032×3024" when scaled down
}
interface ChatMessage { /* … */ images?: ChatImage[] }   // user messages only
```

**API: a message**

```json
{ "role": "user", "content": "What's the total?",
  "images": [{ "media_type": "image/jpeg", "data": "<base64, or a data: URL>" }] }
```

- `ImageInput` decodes `data` once with `b64decode(validate=True)` and sniffs
  the format from the first bytes. It replaces `media_type` with the real
  type, keeps the bytes (`.raw`, `.size`), and clears `data`.
- Only `user` messages may have images. A photo-only message may have empty
  `content`.

## Endpoints

### `GET /api/models`

Adds these fields:

```json
{
  "providers": [{ "models": [{ "id": "gemma3:4b", "vision": true, "...": "..." }] }],
  "default": { "...": "what Auto answers text with" },
  "default_vision": { "...": "what Auto answers photos with, or null" },
  "image_limits": { "per_message": 5, "per_request": 20, "max_bytes": 10485760 }
}
```

### `POST /api/chat`

The order of checks:

1. **413** `BodySizeLimit`: the body is larger than
   `per_request × max_bytes × 4/3 + 8 MB`. This is checked on
   `Content-Length`, or counted while a chunked body streams in.
2. **422** more than 100 images in total. This check runs before any image
   is decoded.
3. **422** decode or sniff failure: "Image data is not valid base64" or
   "Only JPEG, PNG, WebP and GIF images are supported".
4. **422** the route's limits:
   - "Up to 5 photos per message"
   - "A photo is 12.3 MB; the limit is 10 MB"
   - "Up to 20 photos per conversation request"
5. **200** SSE. Vision routing (below) can end in an `error` event.

## Vision routing (`services/chat.py`, `providers/registry.py`)

```
vision = any(message.images for message in request.messages)
if vision and request.provider:
    chosen = request.model or provider.default_model
    if chosen and not registry.vision_check(provider, chosen): → error text_only_message(name)
candidates = registry.candidates(provider, model, allow_fallback, vision=vision)
    # the explicit pick first, then each provider's preferred *vision* model
if not candidates: → error NO_VISION_MESSAGE  ("… ollama pull gemma3 …")
```

- `vision_check` uses the listed `ModelInfo.vision`. An unlisted model is
  judged by its name, the same way as below.
- The fallback happens only before the first token, as with text.
  - Anthropic raises a `ProviderError` for any image over 5 MB before
    sending anything, so the next vision model is tried.

## Which models can see images (`app/vision.py`)

| Provider | Rule |
|---|---|
| Ollama | `ollama show` → `capabilities` contains `"vision"`. This is cached per (name, digest). A failed `show` isn't cached. Older servers fall back to families (`clip`, `mllama`, `gemma3`, `qwen25vl`, …) or names (`llava`, `moondream`, `-vision`, …). `gemma3:1b`, `gemma3:270m` and `gemma3n` are text-only |
| Anthropic | `claude*` except `claude-2*` and `claude-instant*` |
| OpenAI | `gpt-4o*`, `gpt-4.1*`, `gpt-4-turbo*`, `gpt-4.5*`, `gpt-5*`, `chatgpt-4o*`, `o1`/`o3`/`o4` (not `-mini`/`-preview`) |
| Gemini | `gemini*` |
| Grok | `*vision*`, `grok-4*`, `grok-5*` |
| Meta | `*llama-4*`, `*vision*` |
| Any | `VISION_MODELS` fnmatch patterns (case-insensitive) |

## Provider formats

| Provider | Message with photos |
|---|---|
| Ollama (SDK 0.6) | `{"role", "content", "images": [bytes, …]}`. **bytes only** |
| Anthropic | `content: [{type:"image", source:{type:"base64", media_type, data}}…, {type:"text", text}]`. Images first. There is no text block when the text is empty, because Anthropic rejects empty text |
| OpenAI-compatible (OpenAI, Gemini, Grok, Meta) | `content: [{type:"text", text}, {type:"image_url", image_url:{url:"data:<type>;base64,…"}}…]` |

## Web flow

| Step | Where |
|---|---|
| Limits from `/api/models` (`DEFAULT_IMAGE_LIMITS` until loaded) | `chat-app.tsx` |
| Add: precheck → `prepareImage` → `saveImage` → tray | `hooks/use-attachments.ts`, `lib/images.ts`, `lib/image-store.ts` |
| Vision notice, blocking, "Use X", privacy line | `chat-app.tsx` (`VisionNotice`) |
| Send: `takeAll()` → `chat.send(text, images)` | `composer.tsx` → `hooks/use-chat.ts` |
| Build the request: newest ≤ `per_request`, ≤ `per_message` per message, ≤ `max_bytes`; the rest (or all, for a text-only model) become `"[Shared N photos]"`; empty user turns are skipped | `toApiMessages` in `use-chat.ts` |
| Show: gallery, viewer, "Looking at N photos…" | `components/photos/*`, `message.tsx` |
| Cleanup at load: delete unreferenced photos older than 24 h | `collectGarbage` in `use-chat.ts` |

`ImagePolicy.send` is:
- for Auto, whether `default_vision` exists;
- for a chosen model, its `vision` flag;
- `true` before the model list loads, so the API decides.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `MAX_IMAGES_PER_MESSAGE` | 5 (0–10) | 422 over it. The web tray caps here |
| `MAX_IMAGES_PER_REQUEST` | 20 (0–100) | 422 over it. The web app sends the newest this many |
| `MAX_IMAGE_BYTES` | 10 MB (1 KB–20 MB) | Largest accepted file. The web app sends at most min(this, 5 MB) |
| `VISION_MODELS` | `[]` | Extra vision model patterns |
| `ALLOW_CLOUD_FALLBACK` | true | With `false`, photos stay with the chosen or first model |

In the web code: `MAX_EDGE` (2048) and `SEND_MAX_BYTES` (5 MB) in
`lib/images.ts`, and `GC_GRACE_MS` (24 h) in `hooks/use-chat.ts`.
