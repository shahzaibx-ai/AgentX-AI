# Adding photos to another FastAPI backend

Copy these files from `assets/api/`; they have no dependencies beyond FastAPI
and Pydantic:

| File | Gives you |
|---|---|
| `app/images.py` | `decode_image(value) -> (bytes, media_type)`, `sniff`, `to_base64`, `ImageError` |
| `app/vision.py` | `ollama_vision(name, capabilities, families)`, `cloud_vision(provider, model)`, `matches_extra` |
| `app/core/body_limit.py` | `BodySizeLimit` ASGI middleware (413 while the body streams in) |
| `tests/test_photos.py` | Reference tests. Adapt the imports and fixtures |

## 1. Schema

```python
class ImageInput(BaseModel):
    media_type: ImageMediaType
    data: str = Field(min_length=8, repr=False)
    _bytes: bytes = PrivateAttr(default=b"")

    @model_validator(mode="after")
    def _decode(self) -> Self:
        try:
            raw, real_type = decode_image(self.data)
        except ImageError as exc:
            raise ValueError(str(exc)) from exc
        self.media_type, self._bytes, self.data = real_type, raw, ""
        return self

    @property
    def raw(self) -> bytes: return self._bytes
    @property
    def size(self) -> int: return len(self._bytes)

class ChatMessage(BaseModel):
    role: Role
    content: str = ""
    images: list[ImageInput] = Field(default_factory=list, max_length=10)
    # validator: images only on role == "user"
```

On the request model, count the images before they are decoded:

```python
@model_validator(mode="before")
@classmethod
def _count_images_first(cls, data):
    msgs = data.get("messages") if isinstance(data, dict) else None
    if isinstance(msgs, list):
        total = sum(len(m["images"]) for m in msgs
                    if isinstance(m, dict) and isinstance(m.get("images"), list))
        if total > 100:
            raise ValueError(f"Too many photos ({total}); the limit is 100")
    return data
```

## 2. Limits

- In the route, apply the per-message, per-request and size limits, returning
  422 with a readable `detail`.
- Register the middleware:

  ```python
  app.add_middleware(BodySizeLimit, max_bytes=..., paths=("/api/chat",))
  ```

- Add `image_limits` to whatever endpoint the frontend reads its config from.

## 3. Providers

Convert inside each provider, so no SDK type leaks out:

```python
# Ollama: bytes, never str (the SDK reads a str image as a file path if it exists)
{"role": m.role, "content": m.content, "images": [img.raw for img in m.images]}

# Anthropic: image blocks first; skip an empty text block
[{"type": "image", "source": {"type": "base64", "media_type": img.media_type,
  "data": to_base64(img.raw)}} for img in m.images] + ([{"type": "text", "text": m.content}] if m.content.strip() else [])

# OpenAI-compatible
[{"type": "text", "text": m.content}] + [{"type": "image_url", "image_url": {
  "url": f"data:{img.media_type};base64,{to_base64(img.raw)}"}} for img in m.images]
```

Anthropic caps each image at 5 MB. Raise your provider error before
streaming so fallback can pick another model.

Mark each listed model with `vision`:
- For Ollama, call `client.show(name)` (4 at a time, 5 s timeout) and read
  `capabilities`, caching by digest. Use `ollama_vision(...)`.
- For cloud models, use `cloud_vision(provider_id, model_id)` or
  `matches_extra(model_id, patterns)`.

## 4. Routing

In the chat pipeline:

1. `vision = any(m.images for m in messages)`.
2. If the client chose a provider, find the chosen model: the requested
   model or the provider's default. If it can't see images, emit an error
   ("<model> can't see images. Pick a model marked "Sees images", or remove
   the photos from this chat.").
3. Build the candidates (Auto and fallback) from vision models only.
4. If there are none, emit the "No model that can see images…" message with
   the `ollama pull gemma3` hint.

## 5. Tests to keep

The minimum set:

- a string path such as `/etc/passwd` is rejected;
- the declared type is overridden by the sniffed type;
- 422 for each limit, and 413 for both a Content-Length and a chunked body;
- Ollama receives bytes (check what the SDK serialises: `ollama._client._copy_messages`);
- the Anthropic and OpenAI shapes are correct;
- Auto picks a vision model;
- a chosen text-only model is refused, including when only the provider is given;
- fallback skips text-only models;
- a photo earlier in the history still needs vision.
