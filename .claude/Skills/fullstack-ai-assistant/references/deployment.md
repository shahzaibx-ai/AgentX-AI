# Deployment

## Environment variables

### API (`api/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` hides `/docs` |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list; only needed if browsers call the API directly |
| `SYSTEM_PROMPT` | helpful-assistant text | Prepended to every chat |
| `ALLOW_CLOUD_FALLBACK` | `true` | Try other providers when the chosen one fails before replying |
| `REQUEST_TIMEOUT_SECONDS` | `120` | Per SDK request |
| `MODEL_CACHE_TTL_SECONDS` | `30` | `/api/models` cache |
| `MAX_MESSAGES` / `MAX_MESSAGE_CHARS` | `100` / `32000` | Request limits |
| `OLLAMA_ENABLED` / `OLLAMA_HOST` | `true` / `http://localhost:11434` | Local models |
| `CLOUD_PRIORITY` | `["anthropic","openai","gemini","grok","meta"]` | Cloud fallback order |
| `<PROVIDER>_API_KEY` / `_MODEL` / `_BASE_URL` | — | See `providers.md` |

### Web (`web/.env.local`)

| Variable | Default | Purpose |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Where `/api/*` is forwarded. **Read at build time** (rewrites are compiled), so set it before `npm run build` |
| `NEXT_PUBLIC_API_BASE` | `/api` | Only change to call a different public API origin directly (then configure `CORS_ORIGINS`) |

## Docker Compose

```bash
cp api/.env.example api/.env        # add keys
docker compose up --build           # web :3000, api :8000, Ollama on the host
docker compose --profile ollama up  # also run Ollama in a container (set OLLAMA_HOST=http://ollama:11434)
```

- API image: `ghcr.io/astral-sh/uv` build stage with `uv sync --frozen --no-dev`,
  slim runtime, non-root user, healthcheck on `/api/health`.
- Web image: `output: "standalone"`, non-root, `node server.js`.
  `API_URL` is a build arg (default `http://api:8000`).
- `host.docker.internal:host-gateway` lets the API container reach Ollama on the host
  (Linux included).

## Reverse proxy (streaming must not buffer)

nginx in front of the web app:

```nginx
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_buffering off;          # stream tokens immediately
    proxy_read_timeout 300s;      # long local generations
    gzip off;                     # or exclude text/event-stream
}
```

Caddy: `reverse_proxy 127.0.0.1:3000 { flush_interval -1 }`.
Cloudflare / other CDNs: disable response buffering and compression for `/api/chat`.

Symptom of buffering: the reply appears all at once after a long pause.

## Platform notes

- **Vercel (web) + separate API host**: set `API_URL` to the API's public URL
  in Vercel env vars before building. Put the API on Render/Fly/Railway/a VM.
  Serverless function timeouts apply to the rewrite; long local generations may
  need a direct connection (`NEXT_PUBLIC_API_BASE` + CORS).
- **Single VM**: Compose + nginx/Caddy for TLS. Ollama needs RAM/VRAM for the
  models you pull (roughly the model file size plus 1–2 GB).
- **GPU**: run Ollama natively or with the GPU-enabled Ollama image; the API
  itself is CPU-light.

## Production checklist

- [ ] HTTPS in front of the web app; streaming buffering disabled.
- [ ] `ENVIRONMENT=production`; `.env` files not committed; keys in the platform's secret store.
- [ ] Authentication in front of `/api/chat` (cloud calls cost money). Options:
      NextAuth/Auth.js on the web app plus a shared secret or JWT verification in a FastAPI dependency.
- [ ] Rate limiting per user/IP (e.g. at the proxy, or `slowapi` in FastAPI).
- [ ] `*_MODEL` set for each enabled cloud provider so fallback is predictable.
- [ ] Monitoring: API logs include provider failures at WARNING; ship them.
- [ ] Replace the placeholder user in `web/lib/config.ts` with session data.
- [ ] Decide on chat persistence (browser-only today) and privacy wording.
