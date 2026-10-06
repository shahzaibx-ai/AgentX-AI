# Another FastAPI backend

The package is self-contained: `app/library/` depends only on FastAPI,
pydantic-settings and `google-genai`. Rename the `app.` imports if your package
differs.

1. Copy `assets/api/app/library/` and `assets/api/app/library_chat.py`, plus the
   tests, `fake_gemini_api.py` and `fixtures/library/`.
2. Dependencies: `uv add "google-genai>=2.26"`, dev: `uv add --dev pypdf python-docx`
   (the offline engine reads PDF/DOCX with them).
3. Mount it in your app factory and run its lifespan inside yours:

```python
from app.library import LibrarySettings, mount_library

library_settings = LibrarySettings()
library_lifespan = mount_library(app, settings=library_settings, engine=None,
                                 production=settings.environment == "production")
# in your lifespan:   async with library_lifespan(app): yield
```

   `mount_library` sets `app.state.library` and includes the router under `/api`.
4. Upload size limits before the body is parsed (Starlette buffers multipart):
   `chat_file_max_bytes + 1 MB` on `/api/files`, `library_file_max_bytes × 10 + 1 MB`
   on `/api/library/documents`. The template's `BodySizeLimit` middleware does it;
   otherwise use your proxy (`client_max_body_size` in nginx).
5. CORS: allow `PATCH` and `DELETE` if the browser calls the API cross-origin.
6. Chat: add `rag: RagScope | None` to your chat request model and branch:

```python
class RagScope(BaseModel):
    collections: list[str] = Field(default_factory=list, max_length=20)
    files: list[str] = Field(default_factory=list, max_length=50)
    chat_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")

if body.rag and (body.rag.collections or body.rag.files) and request.app.state.library:
    events = rag_chat_events(request.app.state.library, body)   # yields ChatEvent(name, data)
```

   `rag_chat_events` expects `ChatEvent` and `ChatRequest.messages` with `role`
   and `content`; adapt `to_turns()` if your messages differ, and format events
   with your SSE writer. The stream order is meta → delta* → sources → done.
7. Tests: `make_client(..., library=LibrarySettings(_env_file=None, rag_engine="offline",
   library_data_dir=tmp_path), library_engine=None)`; see `tests/conftest.py` in a
   template project for the fixture.

Not FastAPI? Implement `references/api-contract.md`; the web part only depends on it.
