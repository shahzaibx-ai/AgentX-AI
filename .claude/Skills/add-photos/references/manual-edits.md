# Manual edits

Every edit `install_photos.py` makes to existing files, numbered the way its
report numbers them. Use this when the installer says a file was customised:
find the variant, file and edit number, then make the `+` lines appear where
the unchanged (space-prefixed) lines point. Lines starting with `-` are
replaced. Generated from `scripts/patches*.py`; do not edit by hand.

The installer reports which variant it matched: **with voice mode** (the
template after the livekit-voice-mode skill, and every template since) or
**without voice mode**. The API edits are the same in both.

What each file gets, in one line:

| File | Change |
|---|---|
| `api/app/core/config.py` | `max_images_per_message/_request`, `max_image_bytes`, `vision_models` |
| `api/app/main.py` | `BodySizeLimit` on `/api/chat`; registry gets `vision_models` |
| `api/app/schemas.py` | `ImageInput` (decode + sniff), `ChatMessage.images`, `ModelInfo.vision`, `default_vision`, `ImageLimits`, image count before decoding |
| `api/app/providers/ollama.py` | `to_ollama_messages` (bytes), capabilities via `show` (cached by digest), embeddings filter |
| `api/app/providers/anthropic.py` | `to_anthropic_turn` (image blocks), 5 MB guard, `vision` flag |
| `api/app/providers/openai_compat.py` | `to_openai_message` (`image_url` parts), `vision` flag |
| `api/app/providers/registry.py` | `vision_patterns`, `default_vision`, `model_info`, `vision_check`, vision-only candidates |
| `api/app/services/chat.py` | vision routing, `text_only_message`, `NO_VISION_MESSAGE` |
| `api/app/routes/chat.py` | per-message / per-request / size limits (422) |
| `api/app/routes/models.py` | `image_limits` in the response |
| `api/tests/conftest.py`, `test_models.py` | `FakeProvider(vision_models=…)`, registry patterns, `vision` in expectations |
| `web/lib/types.ts` | `ChatImage`, `ImageLimits`, `ModelInfo.vision`, `default_vision`, `ChatMessage.images` |
| `web/lib/api.ts` | `ApiMessage` with `images`; strip Pydantic's `Value error, ` |
| `web/hooks/use-chat.ts` | `ImagePolicy`, `toApiMessages`, `send(text, images)`, photo titles, cleanup at load |
| `web/components/chat/composer.tsx` | + menu, file/camera inputs, tray, notice slot, count, send rules |
| `web/components/chat/message*.tsx` | gallery, photo-only messages, "Looking at N photos…" |
| `web/components/chat/model-picker.tsx` | "Sees images" tags; Auto label shows the vision model |
| `web/components/chat/app-sidebar.tsx` | photo icon on chats with photos |
| `web/components/chat/chat-app.tsx` | attachments, vision notice, privacy line, drop/paste zone, suggestions with photos |

# With voice mode

Files: `api/app/core/config.py` (1), `api/app/main.py` (3), `api/app/schemas.py` (7), `api/app/providers/ollama.py` (7), `api/app/providers/anthropic.py` (4), `api/app/providers/openai_compat.py` (4), `api/app/providers/registry.py` (8), `api/app/services/chat.py` (3), `api/app/routes/chat.py` (3), `api/app/routes/models.py` (3), `api/tests/conftest.py` (4), `api/tests/test_models.py` (1), `api/.env.example` (1), `web/lib/types.ts` (5), `web/lib/api.ts` (2), `web/hooks/use-chat.ts` (8), `web/components/chat/composer.tsx` (11), `web/components/chat/message.tsx` (7), `web/components/chat/message-list.tsx` (1), `web/components/chat/model-picker.tsx` (6), `web/components/chat/app-sidebar.tsx` (2), `web/components/chat/chat-app.tsx` (11), `README.md` (1), `api/README.md` (3), `web/README.md` (4)

## api/app/core/config.py

**Edit 1 of 1**

```diff
     max_message_chars: int = 32_000
 
+    # Photos. The web app resizes to a 2048 px long edge before sending, so real
+    # photos are usually well under these limits.
+    max_images_per_message: int = Field(default=5, ge=0, le=10)
+    max_images_per_request: int = Field(default=20, ge=0, le=100)
+    max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
+    # Extra model ids (fnmatch patterns, e.g. "my-org/*-vl") that can read images.
+    vision_models: list[str] = Field(default_factory=list)
+
```

## api/app/main.py

**Edit 1 of 3**

```diff
 from app import __version__
+from app.core.body_limit import BodySizeLimit
 from app.core.config import Settings, get_settings
```

**Edit 2 of 3**

```diff
         app.state.registry = registry or ProviderRegistry(
-            build_providers(settings), settings.model_cache_ttl_seconds
+            build_providers(settings), settings.model_cache_ttl_seconds, settings.vision_models
         )
```

**Edit 3 of 3**

```diff
     )
+    # Base64 adds a third; allow the photo budget plus room for the text.
+    max_body = settings.max_images_per_request * settings.max_image_bytes * 4 // 3 + 8 * 1024 * 1024
+    app.add_middleware(BodySizeLimit, max_bytes=max_body, paths=("/api/chat",))
     for router in (health.router, models.router, chat.router):
```

## api/app/schemas.py

**Edit 1 of 7**

```diff
 
-from typing import Literal
+from typing import Any, Literal, Self
 
-from pydantic import BaseModel, Field
+from pydantic import BaseModel, Field, PrivateAttr, model_validator
 
+from app.images import ImageError, ImageMediaType, decode_image
+
```

**Edit 2 of 7**

```diff
+
+class ImageInput(BaseModel):
+    """A photo attached to a user message: base64 bytes (a data: URL also works)."""
+
+    media_type: ImageMediaType
+    data: str = Field(min_length=8, repr=False)
+    _bytes: bytes = PrivateAttr(default=b"")
+
+    @model_validator(mode="after")
+    def _decode(self) -> Self:
+        try:
+            raw, real_type = decode_image(self.data)
+        except ImageError as exc:
+            raise ValueError(str(exc)) from exc
+        # Trust the file signature, not the declared type.
+        self.media_type = real_type
+        self._bytes = raw
+        self.data = ""  # keep one copy in memory, not two
+        return self
+
+    @property
+    def raw(self) -> bytes:
+        return self._bytes
+
+    @property
+    def size(self) -> int:
+        return len(self._bytes)
+
 
 class ChatMessage(BaseModel):
     role: Role
-    content: str = Field(max_length=200_000)
+    content: str = Field(default="", max_length=200_000)
+    images: list[ImageInput] = Field(default_factory=list, max_length=10)
 
+    @model_validator(mode="after")
+    def _check(self) -> Self:
+        if self.images and self.role != "user":
+            raise ValueError("Only user messages can have images")
+        return self
+
+
+# Hard ceilings checked before any image is decoded (the route applies the configured limits).
+MAX_REQUEST_MESSAGES = 500
+MAX_REQUEST_IMAGES = 100
+
```

**Edit 3 of 7**

```diff
 class ChatRequest(BaseModel):
-    messages: list[ChatMessage] = Field(min_length=1)
+    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_REQUEST_MESSAGES)
     provider: str | None = Field(
```

**Edit 4 of 7**

```diff
     temperature: float | None = Field(default=None, ge=0, le=2)
 
+    @model_validator(mode="before")
+    @classmethod
+    def _count_images_first(cls, data: Any) -> Any:
+        messages = data.get("messages") if isinstance(data, dict) else None
+        if isinstance(messages, list):
+            total = sum(
+                len(m["images"])
+                for m in messages
+                if isinstance(m, dict) and isinstance(m.get("images"), list)
+            )
+            if total > MAX_REQUEST_IMAGES:
+                raise ValueError(f"Too many photos ({total}); the limit is {MAX_REQUEST_IMAGES}")
+        return data
+
```

**Edit 5 of 7**

```diff
     family: str | None = None
+    vision: bool = Field(default=False, description="Can read images")
 
```

**Edit 6 of 7**

```diff
+
+class ImageLimits(BaseModel):
+    per_message: int
+    per_request: int
+    max_bytes: int
+
 
 class ModelsResponse(BaseModel):
```

**Edit 7 of 7**

```diff
     default: ModelInfo | None = None
+    default_vision: ModelInfo | None = Field(
+        default=None, description="What Auto uses when a message has images"
+    )
     has_local_models: bool
+    image_limits: ImageLimits | None = None
 
```

## api/app/providers/ollama.py

**Edit 1 of 7**

```diff
 
+import asyncio
 from collections.abc import AsyncIterator
+from typing import Any
 
```

**Edit 2 of 7**

```diff
 from app.schemas import ChatMessage, ModelInfo
+from app.vision import ollama_vision
 
+SHOW_TIMEOUT_SECONDS = 5.0
+
+
+def to_ollama_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
+    """Ollama chat messages. Images go as raw bytes (never strings; see app/images.py)."""
+    out: list[dict[str, Any]] = []
+    for m in messages:
+        item: dict[str, Any] = {"role": m.role, "content": m.content}
+        if m.images:
+            item["images"] = [image.raw for image in m.images]
+        out.append(item)
+    return out
+
+
+def _is_chat_model(item: Any) -> bool:
+    """Embedding-only models can't chat, so they stay out of the dropdown."""
+    if not item.model:
+        return False
+    families = (item.details.families or []) if item.details else []
+    return not any("bert" in f for f in families) and "embed" not in item.model
+
```

**Edit 3 of 7**

```diff
         self._client = AsyncClient(host=host, timeout=timeout)
+        self._caps_cache: dict[tuple[str, str], list[str] | None] = {}
 
```

**Edit 4 of 7**

```diff
+
+        items = [item for item in response.models if _is_chat_model(item)]
+        capabilities = await self._capabilities(
+            [(item.model, getattr(item, "digest", None) or "") for item in items]
+        )
 
         models: list[ModelInfo] = []
-        for item in response.models:
-            if not item.model:
-                continue
+        for item in items:
             details = item.details
-            # Embedding-only models cannot chat, so keep them out of the dropdown.
             families = (details.families or []) if details else []
-            if any("bert" in f for f in families) or "embed" in item.model:
-                continue
             models.append(
```

**Edit 5 of 7**

```diff
                     family=details.family if details else None,
+                    vision=ollama_vision(item.model, capabilities.get(item.model), families),
                 )
```

**Edit 6 of 7**

```diff
         return sorted(models, key=lambda m: m.name)
 
+    async def _capabilities(self, models: list[tuple[str, str]]) -> dict[str, list[str] | None]:
+        """Each model's capabilities from `ollama show` (None when the server doesn't say).
+
+        Answers are cached by digest, so only new or re-pulled models are asked.
+        """
+        limit = asyncio.Semaphore(4)
+
+        async def one(name: str, digest: str) -> list[str] | None:
+            key = (name, digest)
+            if digest and key in self._caps_cache:
+                return self._caps_cache[key]
+            async with limit:
+                try:
+                    info = await asyncio.wait_for(self._client.show(name), SHOW_TIMEOUT_SECONDS)
+                except (httpx.HTTPError, ConnectionError, ResponseError, TimeoutError):
+                    return None  # not cached: ask again next time
+                caps = getattr(info, "capabilities", None)
+                result = list(caps) if caps is not None else None
+                if digest:
+                    self._caps_cache[key] = result
+                return result
+
+        results = await asyncio.gather(*(one(n, d) for n, d in models))
+        return {name: caps for (name, _), caps in zip(models, results, strict=True)}
+
```

**Edit 7 of 7**

```diff
                 model=model,
-                messages=[m.model_dump() for m in messages],
+                messages=to_ollama_messages(messages),
                 stream=True,
```

## api/app/providers/anthropic.py

**Edit 1 of 4**

```diff
 
+from app.images import to_base64
 from app.providers.base import Provider, ProviderError
 from app.schemas import ChatMessage, ModelInfo
+from app.vision import cloud_vision
 
```

**Edit 2 of 4**

```diff
         return [
-            ModelInfo(id=m.id, name=m.display_name or m.id, provider=self.id, local=False)
+            ModelInfo(
+                id=m.id,
+                name=m.display_name or m.id,
+                provider=self.id,
+                local=False,
+                vision=cloud_vision(self.id, m.id),
+            )
             for m in models
```

**Edit 3 of 4**

```diff
         client = self._require_client()
+        if any(img.size > ANTHROPIC_MAX_IMAGE_BYTES for m in messages for img in m.images):
+            # Raised before any text, so another model that can see images is tried.
+            raise ProviderError(f"{self.label}: photos must be under 5 MB")
         system = "\n\n".join(m.content for m in messages if m.role == "system")
-        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
+        turns = [to_anthropic_turn(m) for m in messages if m.role != "system"]
         kwargs: dict = {"model": model, "max_tokens": DEFAULT_MAX_TOKENS, "messages": turns}
```

**Edit 4 of 4**

```diff
             await self._client.close()
+
+
+# Anthropic's per-image limit (the web app keeps photos under it).
+ANTHROPIC_MAX_IMAGE_BYTES = 5 * 1024 * 1024
+
+
+def to_anthropic_turn(message: ChatMessage) -> dict:
+    """A user/assistant turn; with images, a list of content blocks (images first, then text)."""
+    if not message.images:
+        return {"role": message.role, "content": message.content}
+    blocks: list[dict] = [
+        {
+            "type": "image",
+            "source": {"type": "base64", "media_type": img.media_type, "data": to_base64(img.raw)},
+        }
+        for img in message.images
+    ]
+    if message.content.strip():  # Anthropic rejects empty text blocks
+        blocks.append({"type": "text", "text": message.content})
+    return {"role": message.role, "content": blocks}
```

## api/app/providers/openai_compat.py

**Edit 1 of 4**

```diff
 
+from app.images import to_base64
 from app.providers.base import Provider, ProviderError
 from app.schemas import ChatMessage, ModelInfo
+from app.vision import cloud_vision
 
```

**Edit 2 of 4**

```diff
         ids = sorted({i for i in ids if self._filter(i)} | ({self._default_model} - {""}))
-        return [ModelInfo(id=i, name=i, provider=self.id, local=False) for i in ids]
+        return [
+            ModelInfo(id=i, name=i, provider=self.id, local=False, vision=cloud_vision(self.id, i))
+            for i in ids
+        ]
 
```

**Edit 3 of 4**

```diff
                 model=model,
-                messages=[m.model_dump() for m in messages],
+                messages=[to_openai_message(m) for m in messages],
                 stream=True,
```

**Edit 4 of 4**

```diff
+
+def to_openai_message(message: ChatMessage) -> dict:
+    """Chat Completions message; with images, content parts with data: URLs."""
+    if not message.images:
+        return {"role": message.role, "content": message.content}
+    parts: list[dict] = []
+    if message.content.strip():
+        parts.append({"type": "text", "text": message.content})
+    parts += [
+        {
+            "type": "image_url",
+            "image_url": {"url": f"data:{img.media_type};base64,{to_base64(img.raw)}"},
+        }
+        for img in message.images
+    ]
+    return {"role": message.role, "content": parts}
+
 
 def openai_model_filter() -> ModelFilter:
```

## api/app/providers/registry.py

**Edit 1 of 8**

```diff
 from app.schemas import ModelInfo, ModelsResponse, ProviderStatus
+from app.vision import cloud_vision, matches_extra, ollama_vision
 
```

**Edit 2 of 8**

```diff
 class ProviderRegistry:
-    def __init__(self, providers: list[Provider], cache_ttl: float = 30.0) -> None:
+    def __init__(
+        self,
+        providers: list[Provider],
+        cache_ttl: float = 30.0,
+        vision_patterns: list[str] | None = None,
+    ) -> None:
+        self._vision_patterns = vision_patterns or []
         self._providers = {p.id: p for p in providers}
```

**Edit 3 of 8**

```diff
         try:
-            status.models = await asyncio.wait_for(provider.list_models(), timeout=10)
+            status.models = await asyncio.wait_for(provider.list_models(), timeout=15)
             status.available = True
+            for m in status.models:
+                if not m.vision and matches_extra(m.id, self._vision_patterns):
+                    m.vision = True
         except (ProviderError, TimeoutError) as exc:
```

**Edit 4 of 8**

```diff
     @staticmethod
-    def _preferred(provider: Provider, status: ProviderStatus) -> ModelInfo | None:
-        if not status.available or not status.models:
+    def _preferred(
+        provider: Provider, status: ProviderStatus, vision: bool = False
+    ) -> ModelInfo | None:
+        """The provider's configured default model, else its first; vision-capable only if asked."""
+        if not status.available:
+            return None
+        models = [m for m in status.models if m.vision] if vision else status.models
+        if not models:
             return None
         if provider.default_model:
-            for m in status.models:
+            for m in models:
                 if m.id == provider.default_model:
                     return m
-        return status.models[0]
+        return models[0]
 
```

**Edit 5 of 8**

```diff
         statuses = await self.statuses(refresh)
-        default = None
-        for status in statuses:
-            default = self._preferred(self._providers[status.id], status)
-            if default:
-                break
+
+        def first(vision: bool) -> ModelInfo | None:
+            for status in statuses:
+                found = self._preferred(self._providers[status.id], status, vision)
+                if found:
+                    return found
+            return None
+
         return ModelsResponse(
             providers=statuses,
-            default=default,
+            default=first(vision=False),
+            default_vision=first(vision=True),
             has_local_models=any(s.local and s.models for s in statuses),
```

**Edit 6 of 8**

```diff
+
+    async def model_info(self, provider_id: str, model: str) -> ModelInfo | None:
+        for status in await self.statuses():
+            if status.id == provider_id:
+                return next((m for m in status.models if m.id == model), None)
+        return None
+
+    async def vision_check(self, provider_id: str, model: str) -> tuple[bool, str]:
+        """(can it see images, display name). Unlisted models are judged by name."""
+        info = await self.model_info(provider_id, model)
+        if info is not None:
+            return info.vision, info.name
+        provider = self.get(provider_id)
+        if provider is None:
+            return False, model
+        by_name = (
+            ollama_vision(model, None, None) if provider.local else cloud_vision(provider_id, model)
+        )
+        return by_name or matches_extra(model, self._vision_patterns), model
 
     async def candidates(
-        self, provider_id: str | None, model: str | None, allow_fallback: bool
+        self,
+        provider_id: str | None,
+        model: str | None,
+        allow_fallback: bool,
+        vision: bool = False,
     ) -> list[Candidate]:
-        """Ordered list of (provider, model) pairs to try for a request."""
+        """Ordered list of (provider, model) pairs to try for a request.
+
+        With `vision`, automatic choices and fallbacks only use models that can read
+        images. The user's explicit pick is always tried first; the chat service
+        rejects it beforehand if it is known to be text-only.
+        """
         result: list[Candidate] = []
```

**Edit 7 of 8**

```diff
                     status = next(s for s in await self.statuses() if s.id == provider_id)
-                    preferred = self._preferred(provider, status)
+                    preferred = self._preferred(provider, status, vision)
                     chosen = preferred.id if preferred else ""
```

**Edit 8 of 8**

```diff
             provider = self._providers[status.id]
-            preferred = self._preferred(provider, status)
+            preferred = self._preferred(provider, status, vision)
             if preferred and all(c.provider.id != provider.id for c in result):
```

## api/app/services/chat.py

**Edit 1 of 3**

```diff
+
+NO_VISION_MESSAGE = (
+    "No model that can see images is available. Install one with `ollama pull gemma3` "
+    "(or `ollama pull llava`), or add a cloud API key, then try again."
+)
+
+
+def text_only_message(model: str) -> str:
+    return (
+        f'{model} can\'t see images. Pick a model marked "Sees images", '
+        "or remove the photos from this chat."
+    )
+
 
 class ChatService:
```

**Edit 2 of 3**

```diff
     async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
+        # Any photo in the conversation needs a model that can read it.
+        vision = any(m.images for m in request.messages)
+        if vision and request.provider:
+            provider = self._registry.get(request.provider)
+            chosen = request.model or (provider.default_model if provider else "")
+            if chosen:
+                can_see, name = await self._registry.vision_check(request.provider, chosen)
+                if not can_see:
+                    yield ChatEvent("error", {"message": text_only_message(name)})
+                    return
         try:
             candidates = await self._registry.candidates(
-                request.provider, request.model, self._allow_fallback
+                request.provider, request.model, self._allow_fallback, vision=vision
             )
```

**Edit 3 of 3**

```diff
         if not candidates:
-            yield ChatEvent("error", {"message": NO_MODELS_MESSAGE})
+            message = NO_VISION_MESSAGE if vision else NO_MODELS_MESSAGE
+            yield ChatEvent("error", {"message": message})
             return
```

## api/app/routes/chat.py

**Edit 1 of 3**

```diff
 
+from app.core.config import Settings
 from app.deps import ChatServiceDep, SettingsDep
```

**Edit 2 of 3**

```diff
 router = APIRouter(prefix="/chat", tags=["chat"])
 
+
+def _check_images(body: ChatRequest, settings: Settings) -> None:
+    def reject(message: str) -> None:
+        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)
+
+    total = 0
+    for m in body.messages:
+        if len(m.images) > settings.max_images_per_message:
+            reject(f"Up to {settings.max_images_per_message} photos per message")
+        for image in m.images:
+            if image.size > settings.max_image_bytes:
+                limit = settings.max_image_bytes / 1024 / 1024
+                reject(f"A photo is {image.size / 1024 / 1024:.1f} MB; the limit is {limit:g} MB")
+        total += len(m.images)
+    if total > settings.max_images_per_request:
+        reject(f"Up to {settings.max_images_per_request} photos per conversation request")
+
+
```

**Edit 3 of 3**

```diff
         raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Last message must be user")
+    _check_images(body, settings)
 
```

## api/app/routes/models.py

**Edit 1 of 3**

```diff
 
-from app.deps import RegistryDep
-from app.schemas import ModelsResponse
+from app.deps import RegistryDep, SettingsDep
+from app.schemas import ImageLimits, ModelsResponse
 
```

**Edit 2 of 3**

```diff
     registry: RegistryDep,
+    settings: SettingsDep,
     refresh: bool = Query(default=False, description="Bypass the short-lived model cache"),
```

**Edit 3 of 3**

```diff
     """Local Ollama models plus models from every configured cloud provider."""
-    return await registry.models_response(refresh=refresh)
+    response = await registry.models_response(refresh=refresh)
+    response.image_limits = ImageLimits(
+        per_message=settings.max_images_per_message,
+        per_request=settings.max_images_per_request,
+        max_bytes=settings.max_image_bytes,
+    )
+    return response
```

## api/tests/conftest.py

**Edit 1 of 4**

```diff
         default_model: str = "",
+        vision_models: set[str] | frozenset[str] = frozenset(),
     ) -> None:
```

**Edit 2 of 4**

```diff
         self._default = default_model
+        self._vision = set(vision_models)
         self.calls: list[tuple[str, list[ChatMessage]]] = []
```

**Edit 3 of 4**

```diff
             raise ProviderError(self._list_error)
-        return [ModelInfo(id=m, name=m, provider=self.id, local=self.local) for m in self._models]
+        return [
+            ModelInfo(id=m, name=m, provider=self.id, local=self.local, vision=m in self._vision)
+            for m in self._models
+        ]
 
```

**Edit 4 of 4**

```diff
         cfg = settings.model_copy(update=overrides)
-        registry = ProviderRegistry(list(providers), cache_ttl=0)
+        registry = ProviderRegistry(list(providers), cache_ttl=0, vision_patterns=cfg.vision_models)
         client = TestClient(create_app(cfg, registry))
```

## api/tests/test_models.py

**Edit 1 of 1**

```diff
         "family": None,
+        "vision": False,
     }
+    assert body["default_vision"] is None
 
```

## api/.env.example

**Edit 1 of 1**

```diff
+
+# ---------- Photos ----------
+# Limits the API enforces (the web app reads them from /api/models).
+MAX_IMAGES_PER_MESSAGE=5
+MAX_IMAGES_PER_REQUEST=20
+MAX_IMAGE_BYTES=10485760
+# Ollama reports which models can see images. Cloud models are matched by name;
+# add patterns here for any the rules miss, e.g. ["my-org/*-vl"].
+VISION_MODELS=[]
 
 # ---------- Voice mode (LiveKit) ----------
```

## web/lib/types.ts

**Edit 1 of 5**

```diff
   family?: string | null;
+  /** Can read images. */
+  vision?: boolean;
 }
```

**Edit 2 of 5**

```diff
+
+export interface ImageLimits {
+  per_message: number;
+  per_request: number;
+  max_bytes: number;
+}
 
 export interface ModelsResponse {
```

**Edit 3 of 5**

```diff
   default: ModelInfo | null;
+  /** What Auto answers with when a message has photos. */
+  default_vision?: ModelInfo | null;
   has_local_models: boolean;
+  image_limits?: ImageLimits | null;
 }
```

**Edit 4 of 5**

```diff
+
+/**
+ * A photo in a message. Only this metadata lives in the chat history
+ * (localStorage); the image itself is in IndexedDB under `id` (lib/image-store).
+ */
+export interface ChatImage {
+  id: string;
+  name: string;
+  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif";
+  width: number;
+  height: number;
+  size: number;
+  /** Original size when the photo was scaled down before sending, e.g. "4032×3024". */
+  resizedFrom?: string;
+}
 
 export interface ChatMessage {
```

**Edit 5 of 5**

```diff
   voice?: boolean;
+  /** Photos attached to a user message. */
+  images?: ChatImage[];
 }
```

## web/lib/api.ts

**Edit 1 of 2**

```diff
     if (typeof body.detail === "string") return body.detail;
-    if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
+    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
+      return String(body.detail[0].msg).replace(/^Value error, /, "");
+    }
   } catch {
```

**Edit 2 of 2**

```diff
+
+export interface ApiImage {
+  media_type: string;
+  /** Base64 without the data: prefix. */
+  data: string;
+}
+
+export interface ApiMessage {
+  role: Role;
+  content: string;
+  images?: ApiImage[];
+}
 
 export interface StreamChatOptions {
-  messages: { role: Role; content: string }[];
+  messages: ApiMessage[];
   selection: ModelSelection;
```

## web/hooks/use-chat.ts

**Edit 1 of 8**

```diff
 
-import { streamChat } from "@/lib/api";
+import { streamChat, type ApiMessage } from "@/lib/api";
 import { makeTitle, readStorage, uid, writeStorage } from "@/lib/helpers";
-import type { ChatMessage, Conversation, ModelSelection } from "@/lib/types";
+import { collectGarbage, loadImage } from "@/lib/image-store";
+import { blobToBase64, photoLabel, textWithPhotoNote } from "@/lib/images";
+import type { ChatImage, ChatMessage, Conversation, ModelSelection } from "@/lib/types";
 
```

**Edit 2 of 8**

```diff
 const MAX_SAVED = 200;
+const GC_GRACE_MS = 24 * 60 * 60 * 1000;
 
```

**Edit 3 of 8**

```diff
 
-export function useChat(selection: ModelSelection, onFinish?: () => void) {
+export interface ImagePolicy {
+  /** False when the chosen model is text-only: photos are described as text instead. */
+  send: boolean;
+  /** Most photos sent in one request; the newest are kept. */
+  perRequest: number;
+  /** The API's current limits; older photos beyond them become a note. */
+  perMessage: number;
+  maxBytes: number;
+}
+
+/**
+ * The request body for a history: the newest photos (up to the limit) are
+ * attached as base64; older or unsendable photos become a short text note so
+ * the model still knows they were there.
+ */
+async function toApiMessages(history: ChatMessage[], policy: ImagePolicy): Promise<ApiMessage[]> {
+  let budget = policy.send ? policy.perRequest : 0;
+  const out: ApiMessage[] = [];
+  for (let i = history.length - 1; i >= 0; i--) {
+    const m = history[i];
+    const images = m.images ?? [];
+    // An empty user turn (e.g. a voice transcript with no words) adds nothing.
+    if (m.role === "user" && !m.content.trim() && !images.length) continue;
+    if (!images.length || m.role !== "user") {
+      out.push({ role: m.role, content: m.content });
+      continue;
+    }
+    const allowed = Math.min(budget, policy.perMessage);
+    const chosen = allowed > 0 ? images.filter((img) => img.size <= policy.maxBytes).slice(-allowed) : [];
+    budget -= chosen.length;
+    const loaded = await Promise.all(
+      chosen.map(async (img) => {
+        const blob = await loadImage(img.id);
+        return blob ? { media_type: img.mediaType, data: await blobToBase64(blob) } : null;
+      }),
+    );
+    const sent = loaded.filter((x) => x !== null);
+    if (sent.length === images.length) {
+      out.push({ role: m.role, content: m.content, images: sent });
+    } else {
+      const left = images.length - sent.length;
+      const note = sent.length
+        ? `[${photoLabel(left)} more not included]\n${m.content}`.trim()
+        : textWithPhotoNote(m);
+      out.push({ role: m.role, content: note, ...(sent.length ? { images: sent } : {}) });
+    }
+  }
+  return out.reverse();
+}
+
+export function useChat(
+  selection: ModelSelection,
+  imagePolicy: ImagePolicy = { send: true, perRequest: 20, perMessage: 5, maxBytes: 10 * 1024 * 1024 },
+  onFinish?: () => void,
+) {
   const [conversations, setConversations] = useState<Conversation[]>([]);
```

**Edit 4 of 8**

```diff
   const onFinishRef = useRef(onFinish);
+  const imagePolicyRef = useRef(imagePolicy);
   useEffect(() => {
```

**Edit 5 of 8**

```diff
     onFinishRef.current = onFinish;
+    imagePolicyRef.current = imagePolicy;
   });
 
-  // Load once on the client (localStorage is not available during SSR).
+  // Load once on the client (localStorage is not available during SSR), then
+  // delete stored photos that no saved chat uses any more.
   useEffect(() => {
-    setConversations(readStorage<Conversation[]>(KEY, []));
+    const startedAt = Date.now();
+    const saved = readStorage<Conversation[]>(KEY, []);
+    setConversations(saved);
     setHydrated(true);
+    const keep = new Set(saved.flatMap((c) => c.messages.flatMap((m) => m.images ?? []).map((i) => i.id)));
+    // A day's grace: another tab may be sending photos its chats haven't saved yet.
+    void collectGarbage(keep, startedAt - GC_GRACE_MS).catch(() => {});
   }, []);
```

**Edit 6 of 8**

```diff
       try {
+        const messages = await toApiMessages(
+          history.filter((m) => !m.error),
+          imagePolicyRef.current,
+        );
+        if (ctrl.signal.aborted) throw new DOMException("Aborted", "AbortError");
         await streamChat({
-          messages: history.filter((m) => !m.error).map(({ role, content }) => ({ role, content })),
+          messages,
           selection: selectionRef.current,
```

**Edit 7 of 8**

```diff
   const send = useCallback(
-    (text: string) => {
+    (text: string, images: ChatImage[] = []) => {
       const content = text.trim();
-      if (!content || controller.current) return;
-      const userMsg: ChatMessage = { id: uid(), role: "user", content, createdAt: Date.now() };
+      if ((!content && !images.length) || controller.current) return;
+      const userMsg: ChatMessage = {
+        id: uid(),
+        role: "user",
+        content,
+        createdAt: Date.now(),
+        ...(images.length ? { images } : {}),
+      };
       const existing = conversations.find((c) => c.id === activeId);
```

**Edit 8 of 8**

```diff
         id: uid(),
-        title: makeTitle(content),
+        title: makeTitle(content || (images.length > 1 ? `${images.length} photos` : "Photo")),
         messages: [],
```

## web/components/chat/composer.tsx

**Edit 1 of 11**

```diff
 
-import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
-import { ArrowUpIcon, AudioLinesIcon, SquareIcon } from "lucide-react";
+import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
+import { ArrowUpIcon, AudioLinesIcon, CameraIcon, ImageIcon, PlusIcon, SquareIcon } from "lucide-react";
 
+import { AttachmentTray } from "@/components/photos/attachment-tray";
 import { Button } from "@/components/ui/button";
+import {
+  DropdownMenu,
+  DropdownMenuContent,
+  DropdownMenuItem,
+  DropdownMenuTrigger,
+} from "@/components/ui/dropdown-menu";
 import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
+import type { UseAttachments } from "@/hooks/use-attachments";
 import { APP_CONFIG } from "@/lib/config";
+import { ACCEPT_ATTR } from "@/lib/images";
+import type { ChatImage } from "@/lib/types";
 import { cn } from "@/lib/utils";
```

**Edit 2 of 11**

```diff
   onVoice,
+  attachments,
+  photoLimit,
+  notice,
+  blocked,
   streaming,
```

**Edit 3 of 11**

```diff
 }: {
-  onSend: (text: string) => void;
+  onSend: (text: string, images: ChatImage[]) => void;
   onStop: () => void;
```

**Edit 4 of 11**

```diff
   onVoice?: () => void;
+  /** Enables the + menu, the photo tray and sending photos. */
+  attachments?: UseAttachments;
+  photoLimit?: number;
+  /** Shown above the input, e.g. "llama3.2 can't see images". */
+  notice?: ReactNode;
+  /** Sending is not possible right now (the notice says why). */
+  blocked?: boolean;
   streaming: boolean;
```

**Edit 5 of 11**

```diff
   const ref = useRef<HTMLTextAreaElement>(null);
+  const fileInput = useRef<HTMLInputElement>(null);
+  const cameraInput = useRef<HTMLInputElement>(null);
+  const [coarse, setCoarse] = useState(false);
 
```

**Edit 6 of 11**

```diff
     if (autoFocus && window.matchMedia("(min-width: 768px)").matches) ref.current?.focus();
+    setCoarse(window.matchMedia("(pointer: coarse)").matches);
   }, [autoFocus]);
 
+  const photoCount = attachments?.items.length ?? 0;
+  const processing = !!attachments?.processing;
+  const hasContent = !!value.trim() || photoCount > 0;
+
```

**Edit 7 of 11**

```diff
     if (streaming) return onStop();
-    if (!value.trim() || disabled) return;
-    onSend(value);
+    if (!hasContent || disabled || processing || blocked) return;
+    onSend(value, attachments?.takeAll() ?? []);
     setValue("");
```

**Edit 8 of 11**

```diff
 
-  const canSend = streaming || (!!value.trim() && !disabled);
-  const showVoice = !!onVoice && !streaming && !value.trim();
+  const canSend = streaming || (hasContent && !disabled && !processing && !blocked);
+  const showVoice = !!onVoice && !streaming && !hasContent;
+  const sendLabel = streaming
+    ? "Stop generating"
+    : processing
+      ? "Waiting for photos to be ready"
+      : "Send message";
 
+  const pick = (input: HTMLInputElement | null) => {
+    // Let the menu close and return focus first, or some browsers ignore the click.
+    requestAnimationFrame(() => input?.click());
+  };
+  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
+    if (e.target.files?.length) attachments?.add([...e.target.files]);
+    e.target.value = "";
+  };
+
```

**Edit 9 of 11**

```diff
     >
+      {notice}
+      {attachments && <AttachmentTray attachments={attachments} />}
       <label htmlFor="composer" className="sr-only">
```

**Edit 10 of 11**

```diff
       />
-      <div className="mt-1 flex items-center justify-end">
+      <div className="mt-1 flex items-center gap-2">
+        {attachments && (
+          <>
+            <DropdownMenu>
+              <Tooltip>
+                <TooltipTrigger asChild>
+                  <DropdownMenuTrigger asChild>
+                    <Button
+                      type="button"
+                      variant="ghost"
+                      size="icon"
+                      aria-label="Add photos"
+                      disabled={disabled}
+                      className="-ml-2 rounded-full text-muted-foreground hover:text-foreground"
+                    >
+                      <PlusIcon />
+                    </Button>
+                  </DropdownMenuTrigger>
+                </TooltipTrigger>
+                <TooltipContent>Add photos</TooltipContent>
+              </Tooltip>
+              <DropdownMenuContent align="start" side="top" className="w-72">
+                <DropdownMenuItem onSelect={() => pick(fileInput.current)} className="items-start">
+                  <ImageIcon className="mt-0.5" />
+                  <span className="flex flex-col">
+                    <span>Add photos</span>
+                    <span className="text-xs text-muted-foreground">
+                      JPEG, PNG, WebP or GIF · up to {photoLimit ?? 5}
+                    </span>
+                  </span>
+                </DropdownMenuItem>
+                <DropdownMenuItem onSelect={() => pick(cameraInput.current)} className="items-start">
+                  <CameraIcon className="mt-0.5" />
+                  <span className="flex flex-col">
+                    <span>Take a photo</span>
+                    <span className="text-xs text-muted-foreground">
+                      {coarse ? "Opens your camera" : "Uses your camera on phones and tablets"}
+                    </span>
+                  </span>
+                </DropdownMenuItem>
+                <p className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
+                  You can also paste or drop photos.
+                </p>
+              </DropdownMenuContent>
+            </DropdownMenu>
+            <input
+              ref={fileInput}
+              type="file"
+              accept={ACCEPT_ATTR}
+              multiple
+              hidden
+              onChange={onFiles}
+              data-testid="photo-input"
+            />
+            <input
+              ref={cameraInput}
+              type="file"
+              accept="image/*"
+              capture="environment"
+              hidden
+              onChange={onFiles}
+            />
+            {photoCount > 0 && (
+              <span className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
+                {photoCount} of {photoLimit ?? 5} photos
+              </span>
+            )}
+          </>
+        )}
+        <div className="flex-1" />
         {showVoice ? (
```

**Edit 11 of 11**

```diff
             disabled={!canSend}
-            aria-label={streaming ? "Stop generating" : "Send message"}
+            aria-label={sendLabel}
             className={cn("rounded-full", !canSend && "opacity-30")}
```

## web/components/chat/message.tsx

**Edit 1 of 7**

```diff
 import { Markdown } from "@/components/chat/markdown";
+import { PhotoGallery } from "@/components/photos/photo-gallery";
+import { useImageUrl } from "@/hooks/use-image-url";
+import { photoLabel } from "@/lib/images";
 import { Button } from "@/components/ui/button";
```

**Edit 2 of 7**

```diff
+
+function MiniThumb({ id }: { id: string }) {
+  const url = useImageUrl(id);
+  return (
+    <span className="-ml-1.5 size-6 overflow-hidden rounded-md border-2 border-background bg-muted first:ml-0">
+      {/* eslint-disable-next-line @next/next/no-img-element -- local object URL */}
+      {url && <img src={url} alt="" className="size-full object-cover" />}
+    </span>
+  );
+}
+
+/** Waiting for a reply to a message with photos. */
+function Looking({ ids }: { ids: string[] }) {
+  return (
+    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
+      <span className="flex">
+        {ids.slice(0, 3).map((id) => (
+          <MiniThumb key={id} id={id} />
+        ))}
+      </span>
+      <span className="animate-pulse">Looking at {ids.length > 1 ? `${ids.length} photos` : "the photo"}…</span>
+    </span>
+  );
+}
 
 export function Message({
```

**Edit 3 of 7**

```diff
   isLast,
+  lookingIds,
   onRegenerate,
```

**Edit 4 of 7**

```diff
   isLast: boolean;
+  /** Photos in the message being answered, while the reply hasn't started. */
+  lookingIds?: string[];
   onRegenerate: (id: string) => void;
```

**Edit 5 of 7**

```diff
       <div className="group flex flex-col items-end gap-1">
-        <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
-          {message.content}
-        </div>
+        {!!message.images?.length && <PhotoGallery images={message.images} />}
+        {message.content && (
+          <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
+            {message.content}
+          </div>
+        )}
         <div className="flex items-center gap-1">
```

**Edit 6 of 7**

```diff
           )}
-          <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
-            <CopyAction text={message.content} />
-          </div>
+          {!!message.images?.length && !message.content && (
+            <span className="px-1 text-xs text-muted-foreground">
+              Sent {photoLabel(message.images.length)}
+            </span>
+          )}
+          {message.content && (
+            <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
+              <CopyAction text={message.content} />
+            </div>
+          )}
         </div>
```

**Edit 7 of 7**

```diff
           <Markdown content={message.content} />
+        ) : message.pending && lookingIds?.length ? (
+          <Looking ids={lookingIds} />
         ) : message.pending ? (
```

## web/components/chat/message-list.tsx

**Edit 1 of 1**

```diff
               isLast={i === conversation.messages.length - 1}
+              lookingIds={
+                m.pending && !m.content
+                  ? conversation.messages[i - 1]?.images?.map((img) => img.id)
+                  : undefined
+              }
               onRegenerate={onRegenerate}
```

## web/components/chat/model-picker.tsx

**Edit 1 of 6**

```diff
   CloudIcon,
+  EyeIcon,
   HardDriveIcon,
```

**Edit 2 of 6**

```diff
 import { formatBytes } from "@/lib/helpers";
+import type { ModelInfo } from "@/lib/types";
 
```

**Edit 3 of 6**

```diff
 
-export function ModelPicker({ models }: { models: UseModels }) {
-  const { data, loading, error, selection, effective, select, refresh } = models;
+function SeesImages({ model }: { model: ModelInfo }) {
+  if (!model.vision) return null;
+  return (
+    <span
+      className="inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 text-[10px] leading-4 font-medium text-muted-foreground"
+      title="This model can read photos"
+    >
+      <EyeIcon className="size-2.5" />
+      Sees images
+    </span>
+  );
+}
 
+export function ModelPicker({
+  models,
+  forPhotos = false,
+}: {
+  models: UseModels;
+  /** The chat has photos: Auto shows the model that will look at them. */
+  forPhotos?: boolean;
+}) {
+  const { data, loading, error, selection, select, refresh } = models;
+  const effective =
+    !selection && forPhotos && data?.default_vision ? data.default_vision : models.effective;
+
```

**Edit 4 of 6**

```diff
               <span className="text-xs text-muted-foreground">
-                Local model first, cloud if unavailable
+                Local model first, cloud if unavailable. With photos, picks a model that can
+                see images.
               </span>
```

**Edit 5 of 6**

```diff
               <span className="truncate">{m.name}</span>
+              <SeesImages model={m} />
               <span className="ml-auto pl-2 text-xs text-muted-foreground">
```

**Edit 6 of 6**

```diff
                       <span className="truncate">{m.name}</span>
+                      <span className="ml-auto pl-2">
+                        <SeesImages model={m} />
+                      </span>
                     </DropdownMenuRadioItem>
```

## web/components/chat/app-sidebar.tsx

**Edit 1 of 2**

```diff
   AudioLinesIcon,
+  ImageIcon,
   CheckIcon,
```

**Edit 2 of 2**

```diff
+                      )}
+                      {c.messages.some((m) => m.images?.length) && (
+                        <ImageIcon
+                          aria-label="Has photos"
+                          className="size-3.5 shrink-0 text-muted-foreground"
+                        />
                       )}
                       <span className="truncate">{c.title}</span>
```

## web/components/chat/chat-app.tsx

**Edit 1 of 11**

```diff
 
-import { useCallback, useEffect, useRef, useState } from "react";
+import { useCallback, useEffect, useMemo, useRef, useState } from "react";
 import dynamic from "next/dynamic";
-import { PanelLeftIcon, SquarePenIcon } from "lucide-react";
+import { CloudIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
 import { toast } from "sonner";
```

**Edit 2 of 11**

```diff
 import { ModelPicker } from "@/components/chat/model-picker";
+import { PhotoDropZone } from "@/components/photos/drop-overlay";
+import { VisionNotice } from "@/components/photos/vision-notice";
 import { Button } from "@/components/ui/button";
```

**Edit 3 of 11**

```diff
 import { VoiceLoading, VoiceTimer } from "@/components/voice/voice-chrome";
+import { useAttachments } from "@/hooks/use-attachments";
 import { useChat } from "@/hooks/use-chat";
```

**Edit 4 of 11**

```diff
 import { APP_CONFIG } from "@/lib/config";
-import type { ChatMessage } from "@/lib/types";
+import { DEFAULT_IMAGE_LIMITS, textWithPhotoNote } from "@/lib/images";
+import type { ChatMessage, ModelInfo } from "@/lib/types";
 import { cn } from "@/lib/utils";
```

**Edit 5 of 11**

```diff
+
+const Code = ({ children }: { children: React.ReactNode }) => (
+  <code className="rounded bg-background/70 px-1 font-mono text-[12px]">{children}</code>
+);
 
 export function ChatApp() {
   const models = useModels();
-  const chat = useChat(models.selection);
+  const limits = models.data?.image_limits ?? DEFAULT_IMAGE_LIMITS;
+  const attachments = useAttachments(limits);
+
+  // ---- photos: which model will look at them ----
+  const chosen: ModelInfo | null = models.selection ? models.effective : null; // null = Auto
+  const visionDefault = models.data?.default_vision ?? null;
+  const canSee = chosen ? !!chosen.vision : !!visionDefault;
+  const imagePolicy = useMemo(
+    // Before the model list loads, send photos and let the API decide.
+    () => ({
+      send: models.data ? canSee : true,
+      perRequest: limits.per_request,
+      perMessage: limits.per_message,
+      maxBytes: limits.max_bytes,
+    }),
+    [models.data, canSee, limits.per_request, limits.per_message, limits.max_bytes],
+  );
+  const chat = useChat(models.selection, imagePolicy);
   const voiceSetup = useVoiceConfig();
```

**Edit 6 of 11**

```diff
   const voiceEnabled = !!voiceSetup.config?.enabled && !noModels;
 
+  const pendingPhotos = attachments.items.length > 0;
+  const chatHasPhotos = !!chat.active?.messages.some((m) => m.images?.length);
+  const providerLabel = (id: string) => models.data?.providers.find((p) => p.id === id)?.label ?? id;
+  const cloudCanSee = !!models.data?.providers.some(
+    (p) => !p.local && p.available && p.models.some((m) => m.vision),
+  );
+
+  const switchToVision = useCallback(() => {
+    if (!visionDefault) return;
+    models.select({ provider: visionDefault.provider, model: visionDefault.id });
+    toast(`Switched to ${visionDefault.name}. It can see images.`);
+  }, [models, visionDefault]);
+
+  const switchAction = visionDefault
+    ? { label: `Use ${visionDefault.name}`, onClick: switchToVision }
+    : undefined;
+  const pullHint = (
+    <>
+      Run <Code>ollama pull gemma3</Code> or add a cloud API key, then refresh the model list.
+    </>
+  );
+
+  let notice: React.ReactNode = null;
+  let blocked = false;
+  if (pendingPhotos && models.data) {
+    if (chosen && !chosen.vision) {
+      blocked = true;
+      notice = (
+        <VisionNotice tone="warning" action={switchAction}>
+          <b className="font-medium">{chosen.name}</b> can&apos;t see images.{" "}
+          {visionDefault ? "Switch to a model that can, or remove the photos." : pullHint}
+        </VisionNotice>
+      );
+    } else if (!chosen && !visionDefault) {
+      blocked = true;
+      notice = (
+        <VisionNotice tone="warning">
+          No model that can see images is available. {pullHint}
+        </VisionNotice>
+      );
+    } else if (!chosen && visionDefault) {
+      notice = (
+        <VisionNotice tone="info">
+          Auto will answer with <b className="font-medium">{visionDefault.name}</b>,{" "}
+          {visionDefault.local ? "a local model" : `a ${providerLabel(visionDefault.provider)} model`}{" "}
+          that can see images.
+        </VisionNotice>
+      );
+    }
+  } else if (chatHasPhotos && chosen && !chosen.vision) {
+    notice = (
+      <VisionNotice tone="info" action={switchAction}>
+        <b className="font-medium">{chosen.name}</b> can&apos;t see images, so it only gets a note that
+        this chat has photos.
+      </VisionNotice>
+    );
+  }
+
+  // Where photos go: shown while photos are attached, and in a chat that has
+  // photos, since earlier photos are sent again with each message.
+  const photoTarget = chosen?.vision ? chosen : !chosen ? visionDefault : null;
+  const disclaimer =
+    (pendingPhotos || chatHasPhotos) && photoTarget ? (
+      photoTarget.local ? (
+        <>
+          <LockIcon className="mr-1 inline size-3 align-[-1px]" />
+          Photos stay on this computer: <b className="font-medium">{photoTarget.name}</b> runs
+          locally.{cloudCanSee && " If it fails, a cloud model may answer instead."}
+        </>
+      ) : (
+        <>
+          <CloudIcon className="mr-1 inline size-3 align-[-1px]" />
+          Photos are sent to <b className="font-medium">{providerLabel(photoTarget.provider)}</b> to
+          answer.
+        </>
+      )
+    ) : (
+      "AI can make mistakes. Check important information."
+    );
+
+  // A suggestion is sent like typed text, with any photos in the tray.
+  const sendSuggestion = (text: string) => {
+    if (blocked || attachments.processing || chat.streaming) return;
+    chat.send(text, attachments.takeAll());
+  };
+
```

**Edit 7 of 11**

```diff
     voiceBuffer.current = [];
-    setVoice({ key: Date.now(), startedAt: Date.now(), history: current?.messages ?? [] });
+    // Voice models get text only; photos become a short note.
+    const history = (current?.messages ?? []).map((m) =>
+      m.images?.length ? { ...m, content: textWithPhotoNote(m) } : m,
+    );
+    setVoice({ key: Date.now(), startedAt: Date.now(), history });
     setMobileOpen(false);
```

**Edit 8 of 11**

```diff
       onVoice={voiceEnabled ? startVoice : undefined}
+      attachments={attachments}
+      photoLimit={limits.per_message}
+      notice={notice}
+      blocked={blocked}
       streaming={chat.streaming}
```

**Edit 9 of 11**

```diff
           </Tooltip>
-          <ModelPicker models={models} />
+          <ModelPicker models={models} forPhotos={pendingPhotos || chatHasPhotos} />
           <div className="flex-1" />
```

**Edit 10 of 11**

```diff
             {composer}
-            <SuggestionGrid onPick={chat.send} />
+            <SuggestionGrid onPick={sendSuggestion} />
           </div>
```

**Edit 11 of 11**

```diff
         )}
-        <p className="shrink-0 pb-2 text-center text-xs text-muted-foreground">
-          AI can make mistakes. Check important information.
+        <p className="shrink-0 px-4 pb-2 text-center text-xs text-muted-foreground" aria-live="polite">
+          {voice ? "AI can make mistakes. Check important information." : disclaimer}
         </p>
       </main>
+      <PhotoDropZone
+        enabled={!voice && !noModels}
+        onFiles={attachments.add}
+        limitText={`JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`}
+      />
     </div>
```

## README.md

**Edit 1 of 1**

```diff
+
+## Photos
+
+Add photos with the **+** button, by pasting, or by dropping them on the page
+(up to 5 per message, JPEG, PNG, WebP or GIF, 10 MB each). The browser scales
+them to 2048 px on the long edge and re-encodes them, which also removes
+metadata such as GPS location. HEIC isn't supported yet; the app says how to
+share a JPEG instead.
+
+Photos need a model that can see images: `ollama pull gemma3` (or `llava`,
+`qwen2.5vl`), or a cloud key. The model menu marks these "Sees images". Auto
+picks one whenever a chat has photos; a chosen text-only model shows a notice
+with a one-click switch. The line under the input says whether photos stay on
+this computer or which provider receives them.
+
+Photos are stored in the browser (IndexedDB) next to the chat history; photos
+no chat uses are cleaned up after a day. Limits are set in `api/.env` (see
+`api/README.md`).
 
 ## How model selection works
```

## api/README.md

**Edit 1 of 3**

```diff
 | GET | `/api/health` | Liveness check |
-| GET | `/api/models?refresh=true` | Installed Ollama models + cloud models, grouped by provider, with the default pick |
+| GET | `/api/models?refresh=true` | Installed Ollama models + cloud models, grouped by provider, with the default pick, the default pick for photos (`default_vision`) and the photo limits. Each model has `vision: true/false` |
 | POST | `/api/chat` | Streams a reply as server-sent events |
```

**Edit 2 of 3**

```diff
 { "messages": [{"role": "user", "content": "Hi"}], "provider": "ollama", "model": "llama3.2:latest" }
 ```
+
+A user message can carry photos (JPEG, PNG, WebP or GIF, base64 or a `data:` URL; the
+real format is read from the file itself):
+
+```json
+{ "role": "user", "content": "What's on this receipt?", "images": [{"media_type": "image/jpeg", "data": "/9j/4AAQ..."}] }
+```
```

**Edit 3 of 3**

```diff
+
+## Photos
+
+- Limits: `MAX_IMAGES_PER_MESSAGE` (5), `MAX_IMAGES_PER_REQUEST` (20, the whole
+  history) and `MAX_IMAGE_BYTES` (10 MB). Breaking one returns 422 with a readable `detail`.
+  `/api/models` returns them as `image_limits` so the web app follows your settings.
+- Request bodies over the photo budget are refused with 413 while they stream in,
+  and at most 100 photos per request are ever decoded.
+- Ollama says which models can see images (`ollama show` capabilities). Cloud models
+  are matched by name (`app/vision.py`); `VISION_MODELS` adds patterns.
+- When any message has photos, Auto and fallback use only models that can see. A
+  chosen text-only model gets an `error` event instead of a reply that ignores the photo.
+- Photos go to Ollama as raw bytes (never strings: the Ollama SDK reads a string
+  that looks like a path from disk), to Anthropic as image blocks (5 MB each at
+  most; larger ones fall back to another model) and to OpenAI-compatible APIs as
+  `image_url` parts. Nothing is written to disk.
+- Try it locally: `ollama pull gemma3` (or `llava`, `qwen2.5vl`).
 
 ## Layout
```

## web/README.md

**Edit 1 of 4**

```diff
     markdown.tsx        GFM markdown with copyable code blocks
-    composer.tsx        auto-growing input, send/stop
+    composer.tsx        auto-growing input, + menu (add/take photos), send/stop/voice
     empty-state.tsx     greeting + suggestions
+  photos/
+    attachment-tray.tsx photos waiting to send, preparing spinner, errors (HEIC, size)
+    photo-gallery.tsx   photos in a sent message
+    photo-viewer.tsx    full-screen viewer with arrows and keyboard
+    drop-overlay.tsx    drop anywhere + paste from the clipboard
+    vision-notice.tsx   "can't see images" / "Auto will answer with …" notice
   voice/
```

**Edit 2 of 4**

```diff
 hooks/
+  use-attachments.ts    add/remove photos, resizing, limits
+  use-image-url.ts      object URL for a stored photo
   use-voice-config.ts   /api/voice/config + saved voice preferences
```

**Edit 3 of 4**

```diff
   types.ts              shared types (mirror the API schemas)
+  images.ts             photo checks, resize/re-encode, error wording
+  image-store.ts        IndexedDB photo storage + cleanup
   config.ts             app name + placeholder user (rebrand here)
```

**Edit 4 of 4**

```diff
 
-- Chat history is stored in the browser (localStorage). Swap `hooks/use-chat.ts`
-  persistence for your database when you add accounts.
+- Chat history is stored in the browser (localStorage) and photos in IndexedDB;
+  messages keep only photo metadata and ids. Swap `hooks/use-chat.ts` and
+  `lib/image-store.ts` for your database and object storage when you add accounts.
 - App name and the placeholder user (Rizwan) live in `lib/config.ts`; replace the user with real data once you add auth.
```

# Without voice mode

Files: `api/.env.example` (1), `web/lib/types.ts` (5), `web/components/chat/composer.tsx` (10), `web/components/chat/message.tsx` (6), `web/components/chat/app-sidebar.tsx` (3), `web/components/chat/chat-app.tsx` (9)

## api/.env.example

**Edit 1 of 1**

```diff
 META_MODEL=
+
+# ---------- Photos ----------
+# Limits the API enforces (the web app reads them from /api/models).
+MAX_IMAGES_PER_MESSAGE=5
+MAX_IMAGES_PER_REQUEST=20
+MAX_IMAGE_BYTES=10485760
+# Ollama reports which models can see images. Cloud models are matched by name;
+# add patterns here for any the rules miss, e.g. ["my-org/*-vl"].
+VISION_MODELS=[]
```

## web/lib/types.ts

**Edit 1 of 5**

```diff
   family?: string | null;
+  /** Can read images. */
+  vision?: boolean;
 }
```

**Edit 2 of 5**

```diff
+
+export interface ImageLimits {
+  per_message: number;
+  per_request: number;
+  max_bytes: number;
+}
 
 export interface ModelsResponse {
```

**Edit 3 of 5**

```diff
   default: ModelInfo | null;
+  /** What Auto answers with when a message has photos. */
+  default_vision?: ModelInfo | null;
   has_local_models: boolean;
+  image_limits?: ImageLimits | null;
 }
```

**Edit 4 of 5**

```diff
+
+/**
+ * A photo in a message. Only this metadata lives in the chat history
+ * (localStorage); the image itself is in IndexedDB under `id` (lib/image-store).
+ */
+export interface ChatImage {
+  id: string;
+  name: string;
+  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif";
+  width: number;
+  height: number;
+  size: number;
+  /** Original size when the photo was scaled down before sending, e.g. "4032×3024". */
+  resizedFrom?: string;
+}
 
 export interface ChatMessage {
```

**Edit 5 of 5**

```diff
   feedback?: "up" | "down" | null;
+  /** Photos attached to a user message. */
+  images?: ChatImage[];
 }
```

## web/components/chat/composer.tsx

**Edit 1 of 10**

```diff
 
-import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
-import { ArrowUpIcon, SquareIcon } from "lucide-react";
+import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
+import { ArrowUpIcon, CameraIcon, ImageIcon, PlusIcon, SquareIcon } from "lucide-react";
 
+import { AttachmentTray } from "@/components/photos/attachment-tray";
 import { Button } from "@/components/ui/button";
+import {
+  DropdownMenu,
+  DropdownMenuContent,
+  DropdownMenuItem,
+  DropdownMenuTrigger,
+} from "@/components/ui/dropdown-menu";
+import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
+import type { UseAttachments } from "@/hooks/use-attachments";
 import { APP_CONFIG } from "@/lib/config";
+import { ACCEPT_ATTR } from "@/lib/images";
+import type { ChatImage } from "@/lib/types";
 import { cn } from "@/lib/utils";
```

**Edit 2 of 10**

```diff
   onStop,
+  attachments,
+  photoLimit,
+  notice,
+  blocked,
   streaming,
```

**Edit 3 of 10**

```diff
 }: {
-  onSend: (text: string) => void;
+  onSend: (text: string, images: ChatImage[]) => void;
   onStop: () => void;
+  /** Enables the + menu, the photo tray and sending photos. */
+  attachments?: UseAttachments;
+  photoLimit?: number;
+  /** Shown above the input, e.g. "llama3.2 can't see images". */
+  notice?: ReactNode;
+  /** Sending is not possible right now (the notice says why). */
+  blocked?: boolean;
   streaming: boolean;
```

**Edit 4 of 10**

```diff
   const ref = useRef<HTMLTextAreaElement>(null);
+  const fileInput = useRef<HTMLInputElement>(null);
+  const cameraInput = useRef<HTMLInputElement>(null);
+  const [coarse, setCoarse] = useState(false);
 
```

**Edit 5 of 10**

```diff
     if (autoFocus && window.matchMedia("(min-width: 768px)").matches) ref.current?.focus();
+    setCoarse(window.matchMedia("(pointer: coarse)").matches);
   }, [autoFocus]);
 
+  const photoCount = attachments?.items.length ?? 0;
+  const processing = !!attachments?.processing;
+  const hasContent = !!value.trim() || photoCount > 0;
+
```

**Edit 6 of 10**

```diff
     if (streaming) return onStop();
-    if (!value.trim() || disabled) return;
-    onSend(value);
+    if (!hasContent || disabled || processing || blocked) return;
+    onSend(value, attachments?.takeAll() ?? []);
     setValue("");
```

**Edit 7 of 10**

```diff
 
-  const canSend = streaming || (!!value.trim() && !disabled);
+  const canSend = streaming || (hasContent && !disabled && !processing && !blocked);
+  const sendLabel = streaming
+    ? "Stop generating"
+    : processing
+      ? "Waiting for photos to be ready"
+      : "Send message";
 
+  const pick = (input: HTMLInputElement | null) => {
+    // Let the menu close and return focus first, or some browsers ignore the click.
+    requestAnimationFrame(() => input?.click());
+  };
+  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
+    if (e.target.files?.length) attachments?.add([...e.target.files]);
+    e.target.value = "";
+  };
+
```

**Edit 8 of 10**

```diff
     >
+      {notice}
+      {attachments && <AttachmentTray attachments={attachments} />}
       <label htmlFor="composer" className="sr-only">
```

**Edit 9 of 10**

```diff
       />
-      <div className="mt-1 flex items-center justify-end">
+      <div className="mt-1 flex items-center gap-2">
+        {attachments && (
+          <>
+            <DropdownMenu>
+              <Tooltip>
+                <TooltipTrigger asChild>
+                  <DropdownMenuTrigger asChild>
+                    <Button
+                      type="button"
+                      variant="ghost"
+                      size="icon"
+                      aria-label="Add photos"
+                      disabled={disabled}
+                      className="-ml-2 rounded-full text-muted-foreground hover:text-foreground"
+                    >
+                      <PlusIcon />
+                    </Button>
+                  </DropdownMenuTrigger>
+                </TooltipTrigger>
+                <TooltipContent>Add photos</TooltipContent>
+              </Tooltip>
+              <DropdownMenuContent align="start" side="top" className="w-72">
+                <DropdownMenuItem onSelect={() => pick(fileInput.current)} className="items-start">
+                  <ImageIcon className="mt-0.5" />
+                  <span className="flex flex-col">
+                    <span>Add photos</span>
+                    <span className="text-xs text-muted-foreground">
+                      JPEG, PNG, WebP or GIF · up to {photoLimit ?? 5}
+                    </span>
+                  </span>
+                </DropdownMenuItem>
+                <DropdownMenuItem onSelect={() => pick(cameraInput.current)} className="items-start">
+                  <CameraIcon className="mt-0.5" />
+                  <span className="flex flex-col">
+                    <span>Take a photo</span>
+                    <span className="text-xs text-muted-foreground">
+                      {coarse ? "Opens your camera" : "Uses your camera on phones and tablets"}
+                    </span>
+                  </span>
+                </DropdownMenuItem>
+                <p className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
+                  You can also paste or drop photos.
+                </p>
+              </DropdownMenuContent>
+            </DropdownMenu>
+            <input
+              ref={fileInput}
+              type="file"
+              accept={ACCEPT_ATTR}
+              multiple
+              hidden
+              onChange={onFiles}
+              data-testid="photo-input"
+            />
+            <input
+              ref={cameraInput}
+              type="file"
+              accept="image/*"
+              capture="environment"
+              hidden
+              onChange={onFiles}
+            />
+            {photoCount > 0 && (
+              <span className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
+                {photoCount} of {photoLimit ?? 5} photos
+              </span>
+            )}
+          </>
+        )}
+        <div className="flex-1" />
         <Button
```

**Edit 10 of 10**

```diff
           disabled={!canSend}
-          aria-label={streaming ? "Stop generating" : "Send message"}
+          aria-label={sendLabel}
           className={cn("rounded-full", !canSend && "opacity-30")}
```

## web/components/chat/message.tsx

**Edit 1 of 6**

```diff
 import { Markdown } from "@/components/chat/markdown";
+import { PhotoGallery } from "@/components/photos/photo-gallery";
+import { useImageUrl } from "@/hooks/use-image-url";
+import { photoLabel } from "@/lib/images";
 import { Button } from "@/components/ui/button";
```

**Edit 2 of 6**

```diff
+
+function MiniThumb({ id }: { id: string }) {
+  const url = useImageUrl(id);
+  return (
+    <span className="-ml-1.5 size-6 overflow-hidden rounded-md border-2 border-background bg-muted first:ml-0">
+      {/* eslint-disable-next-line @next/next/no-img-element -- local object URL */}
+      {url && <img src={url} alt="" className="size-full object-cover" />}
+    </span>
+  );
+}
+
+/** Waiting for a reply to a message with photos. */
+function Looking({ ids }: { ids: string[] }) {
+  return (
+    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
+      <span className="flex">
+        {ids.slice(0, 3).map((id) => (
+          <MiniThumb key={id} id={id} />
+        ))}
+      </span>
+      <span className="animate-pulse">Looking at {ids.length > 1 ? `${ids.length} photos` : "the photo"}…</span>
+    </span>
+  );
+}
 
 export function Message({
```

**Edit 3 of 6**

```diff
   isLast,
+  lookingIds,
   onRegenerate,
```

**Edit 4 of 6**

```diff
   isLast: boolean;
+  /** Photos in the message being answered, while the reply hasn't started. */
+  lookingIds?: string[];
   onRegenerate: (id: string) => void;
```

**Edit 5 of 6**

```diff
       <div className="group flex flex-col items-end gap-1">
-        <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
-          {message.content}
+        {!!message.images?.length && <PhotoGallery images={message.images} />}
+        {message.content && (
+          <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
+            {message.content}
+          </div>
+        )}
+        <div className="flex items-center gap-1">
+          {!!message.images?.length && !message.content && (
+            <span className="px-1 text-xs text-muted-foreground">
+              Sent {photoLabel(message.images.length)}
+            </span>
+          )}
+          {message.content && (
+            <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
+              <CopyAction text={message.content} />
+            </div>
+          )}
         </div>
-        <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
-          <CopyAction text={message.content} />
-        </div>
```

**Edit 6 of 6**

```diff
           <Markdown content={message.content} />
+        ) : message.pending && lookingIds?.length ? (
+          <Looking ids={lookingIds} />
         ) : message.pending ? (
```

## web/components/chat/app-sidebar.tsx

**Edit 1 of 3**

```diff
 import {
+  ImageIcon,
   CheckIcon,
```

**Edit 2 of 3**

```diff
                       className={cn(
-                        "w-full truncate rounded-md py-1.5 pr-9 pl-3 text-left text-sm transition-colors hover:bg-sidebar-accent",
+                        "flex w-full items-center gap-2 rounded-md py-1.5 pr-9 pl-3 text-left text-sm transition-colors hover:bg-sidebar-accent",
                         active && "bg-sidebar-accent font-medium",
```

**Edit 3 of 3**

```diff
                     >
-                      {c.title}
+                      {c.messages.some((m) => m.images?.length) && (
+                        <ImageIcon
+                          aria-label="Has photos"
+                          className="size-3.5 shrink-0 text-muted-foreground"
+                        />
+                      )}
+                      <span className="truncate">{c.title}</span>
                     </button>
```

## web/components/chat/chat-app.tsx

**Edit 1 of 9**

```diff
 
-import { useCallback, useEffect, useState } from "react";
-import { PanelLeftIcon, SquarePenIcon } from "lucide-react";
+import { useCallback, useEffect, useMemo, useState } from "react";
+import { CloudIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
 import { toast } from "sonner";
```

**Edit 2 of 9**

```diff
 import { ModelPicker } from "@/components/chat/model-picker";
+import { PhotoDropZone } from "@/components/photos/drop-overlay";
+import { VisionNotice } from "@/components/photos/vision-notice";
 import { Button } from "@/components/ui/button";
```

**Edit 3 of 9**

```diff
 import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
+import { useAttachments } from "@/hooks/use-attachments";
 import { useChat } from "@/hooks/use-chat";
 import { useModels } from "@/hooks/use-models";
+import { DEFAULT_IMAGE_LIMITS } from "@/lib/images";
+import type { ModelInfo } from "@/lib/types";
 import { cn } from "@/lib/utils";
 
+const Code = ({ children }: { children: React.ReactNode }) => (
+  <code className="rounded bg-background/70 px-1 font-mono text-[12px]">{children}</code>
+);
+
```

**Edit 4 of 9**

```diff
   const models = useModels();
-  const chat = useChat(models.selection);
+  const limits = models.data?.image_limits ?? DEFAULT_IMAGE_LIMITS;
+  const attachments = useAttachments(limits);
+
+  // ---- photos: which model will look at them ----
+  const chosen: ModelInfo | null = models.selection ? models.effective : null; // null = Auto
+  const visionDefault = models.data?.default_vision ?? null;
+  const canSee = chosen ? !!chosen.vision : !!visionDefault;
+  const imagePolicy = useMemo(
+    // Before the model list loads, send photos and let the API decide.
+    () => ({
+      send: models.data ? canSee : true,
+      perRequest: limits.per_request,
+      perMessage: limits.per_message,
+      maxBytes: limits.max_bytes,
+    }),
+    [models.data, canSee, limits.per_request, limits.per_message, limits.max_bytes],
+  );
+  const chat = useChat(models.selection, imagePolicy);
   const [sidebarOpen, setSidebarOpen] = useState(true); // desktop
```

**Edit 5 of 9**

```diff
   const noModels = !models.loading && !models.effective;
 
+  const pendingPhotos = attachments.items.length > 0;
+  const chatHasPhotos = !!chat.active?.messages.some((m) => m.images?.length);
+  const providerLabel = (id: string) => models.data?.providers.find((p) => p.id === id)?.label ?? id;
+  const cloudCanSee = !!models.data?.providers.some(
+    (p) => !p.local && p.available && p.models.some((m) => m.vision),
+  );
+
+  const switchToVision = useCallback(() => {
+    if (!visionDefault) return;
+    models.select({ provider: visionDefault.provider, model: visionDefault.id });
+    toast(`Switched to ${visionDefault.name}. It can see images.`);
+  }, [models, visionDefault]);
+
+  const switchAction = visionDefault
+    ? { label: `Use ${visionDefault.name}`, onClick: switchToVision }
+    : undefined;
+  const pullHint = (
+    <>
+      Run <Code>ollama pull gemma3</Code> or add a cloud API key, then refresh the model list.
+    </>
+  );
+
+  let notice: React.ReactNode = null;
+  let blocked = false;
+  if (pendingPhotos && models.data) {
+    if (chosen && !chosen.vision) {
+      blocked = true;
+      notice = (
+        <VisionNotice tone="warning" action={switchAction}>
+          <b className="font-medium">{chosen.name}</b> can&apos;t see images.{" "}
+          {visionDefault ? "Switch to a model that can, or remove the photos." : pullHint}
+        </VisionNotice>
+      );
+    } else if (!chosen && !visionDefault) {
+      blocked = true;
+      notice = (
+        <VisionNotice tone="warning">
+          No model that can see images is available. {pullHint}
+        </VisionNotice>
+      );
+    } else if (!chosen && visionDefault) {
+      notice = (
+        <VisionNotice tone="info">
+          Auto will answer with <b className="font-medium">{visionDefault.name}</b>,{" "}
+          {visionDefault.local ? "a local model" : `a ${providerLabel(visionDefault.provider)} model`}{" "}
+          that can see images.
+        </VisionNotice>
+      );
+    }
+  } else if (chatHasPhotos && chosen && !chosen.vision) {
+    notice = (
+      <VisionNotice tone="info" action={switchAction}>
+        <b className="font-medium">{chosen.name}</b> can&apos;t see images, so it only gets a note that
+        this chat has photos.
+      </VisionNotice>
+    );
+  }
+
+  // Where photos go: shown while photos are attached, and in a chat that has
+  // photos, since earlier photos are sent again with each message.
+  const photoTarget = chosen?.vision ? chosen : !chosen ? visionDefault : null;
+  const disclaimer =
+    (pendingPhotos || chatHasPhotos) && photoTarget ? (
+      photoTarget.local ? (
+        <>
+          <LockIcon className="mr-1 inline size-3 align-[-1px]" />
+          Photos stay on this computer: <b className="font-medium">{photoTarget.name}</b> runs
+          locally.{cloudCanSee && " If it fails, a cloud model may answer instead."}
+        </>
+      ) : (
+        <>
+          <CloudIcon className="mr-1 inline size-3 align-[-1px]" />
+          Photos are sent to <b className="font-medium">{providerLabel(photoTarget.provider)}</b> to
+          answer.
+        </>
+      )
+    ) : (
+      "AI can make mistakes. Check important information."
+    );
+
+  // A suggestion is sent like typed text, with any photos in the tray.
+  const sendSuggestion = (text: string) => {
+    if (blocked || attachments.processing || chat.streaming) return;
+    chat.send(text, attachments.takeAll());
+  };
+
```

**Edit 6 of 9**

```diff
       onStop={chat.stop}
+      attachments={attachments}
+      photoLimit={limits.per_message}
+      notice={notice}
+      blocked={blocked}
       streaming={chat.streaming}
```

**Edit 7 of 9**

```diff
           </Tooltip>
-          <ModelPicker models={models} />
+          <ModelPicker models={models} forPhotos={pendingPhotos || chatHasPhotos} />
           <div className="flex-1" />
```

**Edit 8 of 9**

```diff
             {composer}
-            <SuggestionGrid onPick={chat.send} />
+            <SuggestionGrid onPick={sendSuggestion} />
           </div>
```

**Edit 9 of 9**

```diff
         )}
-        <p className="shrink-0 pb-2 text-center text-xs text-muted-foreground">
-          AI can make mistakes. Check important information.
+        <p className="shrink-0 px-4 pb-2 text-center text-xs text-muted-foreground" aria-live="polite">
+          {disclaimer}
         </p>
       </main>
+      <PhotoDropZone
+        enabled={!noModels}
+        onFiles={attachments.add}
+        limitText={`JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`}
+      />
     </div>
```
