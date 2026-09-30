# Architecture and contracts

Verified September 2026 with livekit-agents 1.8.3, livekit-plugins-ai-coustics
0.3.2, livekit-api 1.2.1, livekit-client 2.22.3, @livekit/components-react
2.9.24, and livekit-server 1.13.7 for local tests.

## Pieces

```
web/                                    api/                                 agent/
components/voice/voice-session.tsx      app/voice/          (portable)       voice_agent.py
  useSession + SessionProvider            routes.py   /api/voice/*           AgentServer, rtc_session
  live transcript, saving                 service.py  tokens, context        STT → turn → LLM → TTS
components/voice/voice-bar.tsx            settings.py LIVEKIT_*, VOICE_*       interrupt RPC, attributes
  controls + every state                  schemas.py                         app_llm.py
components/voice/level-bars.tsx           brain.py    Brain contract           AppLLM → /api/voice/chat
components/voice/voice-chrome.tsx       app/voice_brain.py  (adapter)        settings.py  VOICE_*, API_URL
hooks/use-voice-config.ts                 ChatService → Brain events
lib/voice.ts   API calls, attr names    app/main.py  mount_voice(app, brain=chat_brain)
```

The voice package (`api/app/voice/`) knows nothing about the host app. It needs
only a **brain**: a function that streams a reply for a list of messages. The
template's brain (`voice_brain.py`) wraps the existing `ChatService`, so voice
uses the same model dropdown, Ollama-first order, and cloud fallback as typed
chat.

## Session flow

1. The composer is empty and voice is enabled, so it shows **Start voice mode**.
   `ChatApp` mounts `VoiceSession` (a `next/dynamic` import, so LiveKit's
   JavaScript is downloaded only now).
2. `TokenSource.literal(fn)` calls `POST /api/voice/session` with the model
   selection, the voice preference, the participant name and the open chat's
   history. Use `literal`, not `custom`: `custom` caches by fetch options and
   would reuse a room.
3. The API creates the room name `voice-<uuid4 hex>` and the identity
   `user-<12 hex>`. It stores `VoiceContext(provider, model, history)` in a TTL
   store and returns a JWT. The JWT's `RoomConfiguration(agents=[RoomAgentDispatch(agent_name, metadata={"voice": tts_id})])`
   makes LiveKit dispatch the agent when the user joins.
4. `session.start({tracks: {microphone: {enabled: true}}})` runs inside a 0 ms
   timer. React Strict Mode mounts twice in development; the timer lets the
   first cleanup cancel instead of opening two rooms. Cleanup calls
   `session.end()`.
5. The agent joins and greets with `session.say(VOICE_GREETING)`.
6. For each user turn, `AppLLM.chat()` sends `POST /api/voice/chat {room, messages}`.
   The API then:
   - merges the agent's instructions, the stored history and the spoken turns;
   - normalises them: one system message first, same-speaker turns merged, a
     leading assistant turn dropped;
   - calls the brain and streams its events back as SSE.
7. The agent publishes participant attributes. The UI shows the answering model
   under the reply, plus banners for fallbacks and errors.

## HTTP contract

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/voice/config` | → `{enabled, reason, voices: [{id, name, description}]}` |
| POST | `/api/voice/session` | `{provider?, model?, voice?, participant_name?, history?: [{role, content}]}` → 201 `{server_url, participant_token, room_name, participant_identity}`. 503 if LiveKit isn't configured; 422 for an unknown voice id |
| POST | `/api/voice/chat` | `{room: "voice-<32 hex>", messages: [{role, content}], temperature?}` → `text/event-stream` |

SSE events from `/api/voice/chat` (the same shape as the app's `/api/chat`):

```
event: meta    data: {"provider","provider_label","model","local","fallback","notice"}   optional, first
event: delta   data: {"delta": "text"}                                                   repeated
event: error   data: {"message": "user-safe reason"}                                     last, or
event: done    data: {}                                                                  last
```

An unknown or expired room is not an error: the reply uses automatic model
choice without history. A brain that raises becomes
`error {"message": "The assistant failed to answer."}`, and the exception is
logged.

## Brain contract (`api/app/voice/brain.py`)

```python
@dataclass(frozen=True)
class BrainRequest:
    messages: list[dict[str, str]]   # system first, history, spoken turns; ends with user
    provider: str | None = None      # what the user picked; None = automatic
    model: str | None = None
    temperature: float | None = None

BrainEvent = tuple[Literal["meta", "delta", "error", "done"], dict[str, Any]]
Brain = Callable[[Request, BrainRequest], AsyncIterator[BrainEvent]]
```

The brain receives the FastAPI `Request`, so it can reach `request.app.state`
(settings, registries, DB pools) and the user (for example, a dependency that
put the user on `request.state`). See `integrate-fastapi.md` for brains over
other stacks.

## Agent ↔ web signals

Participant attributes on the agent (names are in `web/lib/voice.ts` → `AGENT_ATTR`):

| Attribute | Meaning |
|---|---|
| `assistant.model`, `assistant.provider`, `assistant.local` | Who answered the last turn (from `meta`) |
| `assistant.notice` | Why a fallback model answered (the `meta.notice` text) |
| `assistant.error` | Why the last reply failed (the agent also says a spoken apology) |

RPC: the web calls `performRpc({destinationIdentity: agent.identity, method: "interrupt", payload: ""})`
for **Stop** and Esc. The agent handles it with `session.interrupt()`.

Transcripts come from LiveKit's synced transcription streams
(`useSessionMessages`). User segments carry `lk.transcription_final = "true"`.
For agent segments the final flag arrives only in the stream trailer, which the
client hook doesn't re-emit, so the UI treats an agent reply as finished when
the agent stops speaking or thinking.

## Why the agent uses a custom `llm.LLM`

`AgentActivity` skips generating a reply when `session.llm is None`, even if
`Agent.llm_node` is overridden. So the brain has to be an `llm.LLM` instance
(`AppLLM`), not an `llm_node` override. `AppLLMStream`:

- sets `_retry_on_chunk_sent = False`;
- **never raises**: on HTTP errors, an SSE `error` before any text, timeouts
  or connection errors, it emits a spoken apology (`FALLBACK_REPLY`) and
  reports the real reason through `on_error`, which sets `assistant.error`;
- keeps partial text when an error arrives after text has started.

The default TTS text transforms (`filter_markdown`, `filter_emoji`) keep
markdown symbols from being read aloud. The instructions still ask the model
for plain spoken text.

`VOICE_LLM` set to anything other than `app` uses LiveKit Inference directly
(`inference.LLM(model)`), bypassing the app. That is useful for latency tests,
but it loses the app's model choice and fallback.
