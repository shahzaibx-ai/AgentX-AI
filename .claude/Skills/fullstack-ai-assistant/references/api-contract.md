# API contract

Base path: `/api`. The web app reaches it through its own origin
(`/api/*` → `API_URL`). Types in `web/lib/types.ts` mirror `api/app/schemas.py`;
change both together.

## `GET /api/health`

```json
{ "status": "ok", "version": "1.0.0" }
```

## `GET /api/models?refresh=false`

Probes every provider concurrently (10 s timeout each). Cached for
`MODEL_CACHE_TTL_SECONDS` (default 30 s); `refresh=true` bypasses the cache.

```json
{
  "providers": [
    {
      "id": "ollama", "label": "Ollama (local)", "local": true,
      "configured": true, "available": true, "error": null,
      "models": [
        { "id": "llama3.2:latest", "name": "llama3.2", "provider": "ollama", "local": true,
          "size_bytes": 2019393189, "parameter_size": "3.2B", "family": "llama" }
      ]
    },
    { "id": "anthropic", "label": "Anthropic Claude", "local": false,
      "configured": false, "available": false, "error": null, "models": [] }
  ],
  "default": { "id": "llama3.2:latest", "provider": "ollama", "...": "..." },
  "has_local_models": true
}
```

- `configured=false`: no key / disabled. `configured=true, available=false`:
  key set but listing failed; `error` says why.
- `default` is what **Auto** will use: first local model, else the first
  cloud provider's preferred model, else `null`.
- Ollama embedding models (`*embed*` names or `bert` families) are excluded.
- OpenAI's list is filtered to chat models (`gpt*`, `o*`, `chatgpt*`, minus
  embeddings, audio, image, realtime, etc.).

## `POST /api/chat`

Request:

```json
{
  "messages": [
    { "role": "user", "content": "Hi" }
  ],
  "provider": "ollama",
  "model": "llama3.2:latest",
  "temperature": 0.7
}
```

| Field | Rules |
|---|---|
| `messages` | 1..`MAX_MESSAGES` (100); roles `system`/`user`/`assistant`; last must be `user`; each ≤ `MAX_MESSAGE_CHARS` (32 000) |
| `provider`, `model` | Optional. Omit both for Auto |
| `temperature` | Optional, 0–2 (clamped to 1 for Anthropic) |

The server prepends `SYSTEM_PROMPT` unless the request already has a `system` message.

Validation failures return **HTTP 422** (JSON). Everything else, including
provider failures, returns **HTTP 200** with an SSE stream so the client has one
code path.

### Response: `text/event-stream`

Headers: `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`.

```
event: meta
data: {"provider":"ollama","provider_label":"Ollama (local)","model":"llama3.2:latest","local":true,"fallback":false,"notice":null}

data: {"delta":"Hel"}

data: {"delta":"lo"}

event: done
data: {}
```

| Event | When | Payload |
|---|---|---|
| `meta` | Once, before the first delta | Which provider/model is answering; `fallback` + `notice` when earlier candidates failed |
| *(unnamed)* | Each text chunk | `{"delta": string}` |
| `done` | Reply complete | `{}` |
| `error` | Terminal failure (before or during the reply) | `{"message": string}` — safe to show users |

A stream that ends without `done` or `error` means the connection dropped; the
client reports "The connection closed before the reply finished."

### Client parsing rules (implemented in `web/lib/api.ts`)

- Split on blank lines; collect `event:` and `data:` lines per block.
- Unnamed events are deltas; `error` throws `ApiError(message)`.
- Normalise `\r\n` before splitting.

### curl

```bash
curl -N -X POST localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hi"}]}'
```
