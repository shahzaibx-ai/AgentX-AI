# Integrating the API side

## In the fullstack-ai-assistant template

`install_voice.py` does all of this. By hand, it's three edits to
`api/app/main.py`, plus the copied files:

```python
from app.voice import VoiceSettings, mount_voice
from app.voice_brain import chat_brain

def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
    voice_settings: VoiceSettings | None = None,      # tests inject config here
) -> FastAPI:
    ...
    for router in (health.router, models.router, chat.router):
        app.include_router(router, prefix="/api")
    mount_voice(app, brain=chat_brain, settings=voice_settings)  # voice mode (LiveKit)
    return app
```

Also add `"livekit-api>=1.2.1"` to `api/pyproject.toml` and run `uv sync`.

`app/voice_brain.py` adapts the template's `ChatService` to the Brain contract:

```python
async def chat_brain(request: Request, req: BrainRequest) -> AsyncIterator[BrainEvent]:
    settings = request.app.state.settings
    service = ChatService(request.app.state.registry, settings.system_prompt, settings.allow_cloud_fallback)
    chat_request = ChatRequest(
        messages=[ChatMessage(**m) for m in req.messages],
        provider=req.provider, model=req.model, temperature=req.temperature,
    )
    async for event in service.stream(chat_request):
        yield event.type, event.data
```

## In any other FastAPI app

1. Copy `assets/api/app/voice/` into your package (it uses only relative
   imports, so any location works, e.g. `myapp/voice/`).
2. Install the dependencies: `fastapi`, `pydantic-settings`, and
   `livekit-api>=1.2.1`.
3. Write a brain (examples below) and call
   `mount_voice(app, brain=my_brain)` once, where the app is created.
4. Copy `assets/api/tests/test_voice.py`. Most of it tests the package on a
   bare FastAPI app with a recording brain. To run it in another app:
   - change `app.voice` to your import path;
   - replace the `tests.conftest` import with a copy of `parse_sse` (a
     12-line SSE parser; it's in the template's `api/tests/conftest.py`);
   - delete the imports of `Settings`, `create_app`, `ProviderRegistry` and
     `FakeProvider`, and the tests from the `app_client` fixture onward (they
     check the template's adapter), or adapt them to your app.

`mount_voice(app, brain, settings=None, prefix="/api/voice")`:

- `settings`: a `VoiceSettings` (defaults to reading env and `.env`). Pass one
  in tests: `VoiceSettings(_env_file=None, livekit_url=..., ...)`.
- `prefix`: change it if your API isn't under `/api`. The web client uses
  `NEXT_PUBLIC_API_BASE` (default `/api`) + `/voice/...`, and the agent uses
  `API_URL` + `/api/voice/chat` (see `app_llm.py`).
- It stores `voice_settings`, `voice_store` and `voice_brain` on `app.state`.

## Writing a brain

A brain is an async generator of `(event, data)` tuples. Rules:

- Yield `("delta", {"delta": text})` chunks as they arrive. Smaller chunks
  mean earlier speech, because TTS starts on the first sentence.
- End with `("done", {})`, or with `("error", {"message": ...})` using a short,
  user-safe message (it's shown in the UI and summarised aloud).
- `meta` is optional, but include it when you know the model. The UI shows it
  under the reply.
- Don't raise for expected failures; yield `error`. Unexpected exceptions are
  caught, logged, and turned into a generic error.
- `req.messages` already starts with the system message (the agent's voice
  instructions) and ends with a user turn. Keep that system prompt: it's what
  makes answers short and speakable.

OpenAI-compatible SDK:

```python
from openai import AsyncOpenAI
client = AsyncOpenAI()

async def openai_brain(request, req):
    model = req.model or "gpt-5-mini"
    yield "meta", {"provider": "openai", "provider_label": "OpenAI", "model": model,
                   "local": False, "fallback": False, "notice": None}
    try:
        stream = await client.chat.completions.create(model=model, messages=req.messages, stream=True)
        async for chunk in stream:
            if chunk.choices and (text := chunk.choices[0].delta.content):
                yield "delta", {"delta": text}
    except Exception:
        yield "error", {"message": "The AI service is unavailable right now."}
        return
    yield "done", {}
```

LangChain / LangGraph (any runnable with `astream`):

```python
async def graph_brain(request, req):
    async for chunk in chain.astream({"messages": req.messages}):
        if text := getattr(chunk, "content", None):
            yield "delta", {"delta": text}
    yield "done", {}
```

Non-streaming backends: yield a single `delta` with the whole reply. Speech then
starts only after the full answer, so prefer streaming when latency matters.

Per-user brains: resolve the user in a dependency or middleware that sets
`request.state.user`, then read it inside the brain. The agent's calls carry
no user session, so put anything user-specific into the room context at
`/session` time (see "Auth" in `deployment.md`).

## Settings (`VoiceSettings`, env or `.env`)

| Variable | Default | Notes |
|---|---|---|
| `LIVEKIT_URL` | — | Must be reachable **from the browser** (`wss://…`) |
| `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | — | Voice is enabled only when all three are set |
| `VOICE_AGENT_NAME` | `my-agent` | Must equal the agent's `VOICE_AGENT_NAME` |
| `VOICE_TOKEN_TTL_SECONDS` | 900 | Participant token lifetime (only for joining) |
| `VOICE_CONTEXT_TTL_SECONDS` | 3600 | How long a room's model and history are remembered |
| `VOICE_HISTORY_MESSAGES` | 20 | Earlier chat messages carried into voice |
| `VOICE_MAX_MESSAGES`, `VOICE_MAX_MESSAGE_CHARS` | 100, 32000 | Request caps |
| `VOICE_VOICES` | `[]` | JSON `[{id, name, description, tts_voice}]`. Empty hides the picker |

## Scaling note

`VoiceContextStore` is in-process memory with a TTL and a lock. With more than
one API instance, `/session` and `/chat` can hit different processes, and the
context is then missing. The reply still works, but on automatic model choice
and without history. Use sticky routing, or reimplement the store's
`put`/`get` on Redis (for example, `SETEX voice:<room> <ttl> <json>`).
