# Troubleshooting & known pitfalls

Real issues hit while building and testing this template, with fixes. Check
here before debugging from scratch.

## Build & tooling

| Symptom | Cause | Fix |
|---|---|---|
| `tsc`: `Cannot find name 'LayoutProps'` | Next.js generates route types (`.next/types`); a fresh checkout has none | `typecheck` script is `next typegen && tsc --noEmit`. Keep it that way |
| `next build` fails fetching Google Fonts | `next/font/google` downloads at build time; blocked in CI/proxies | Template uses the `geist` npm package (`geist/font/sans`, `geist/font/mono`) — self-hosted |
| `npx shadcn init/add` fails (`ui.shadcn.com` unreachable) | Registry is fetched over the network | Write components by hand following `references/frontend.md` conventions; `components.json` stays valid |
| `uv sync --frozen` fails in Docker after renaming | `uv.lock` still has the old project name | `scaffold.py` rewrites `pyproject.toml` and `uv.lock` together; if renaming by hand, run `uv lock` |
| `npm ci` complains lock is out of sync | `package.json` name changed without regenerating the lock | `npm install --package-lock-only` |
| Ruff `PLR0917` too many positional args | Provider constructors with many params | Make trailing params keyword-only (`*,`) |
| `create-next-app` scaffolds `typescript@^5` | CLI default | `npm i -D typescript@^7` — Next.js 16.3+ supports TS 7 for type checking |

## Runtime

| Symptom | Cause | Fix |
|---|---|---|
| Reply appears all at once | Something buffers the SSE stream (gzip, nginx, CDN) | `compress: false` in `next.config.ts`; `proxy_buffering off`; see `deployment.md` |
| Model dropdown shows "API offline" | Web can't reach `API_URL` | Start the API; check `web/.env.local`; remember `API_URL` is baked in at build time |
| "Ollama is not reachable" | Ollama not running or wrong host (Docker!) | `ollama serve`; in Compose use `http://host.docker.internal:11434` |
| Local list is empty but Ollama runs | Only embedding models installed | `ollama pull llama3.2` (embedding models are hidden on purpose) |
| Cloud provider shows an error in the menu | Bad key, no quota, or model listing unsupported | Read the message; set `<PROVIDER>_MODEL` so a model is offered even if listing fails |
| Fallback picked an odd cloud model | `*_MODEL` empty → first listed model | Set `*_MODEL` for each enabled provider |
| Selected model disappears after refresh | It was removed/unpulled | `use-models` resets to Auto automatically; expected |
| Tests pick up real `.env` values | Settings read from global cache | Routes read `request.app.state.settings`; tests pass `Settings(_env_file=None, ...)` to `create_app` |

## Testing notes

- Backend tests use `FakeProvider` (in `tests/conftest.py`) and never touch the
  network. Extend it rather than mocking HTTP.
- To exercise the real Ollama SDK without Ollama installed, run a tiny FastAPI
  stand-in that serves `GET /api/tags` and streams NDJSON from `POST /api/chat`
  on port 11434 (lines like `{"message":{"role":"assistant","content":"Hi "},"done":false}`
  then a `"done":true` line).
- Headless browser screenshots in sandboxes: if Playwright can't download
  Chromium, `@sparticuz/chromium` (npm) + `playwright-core` works; it runs in
  single-process mode, so launch **one browser per scenario** (closing a
  context kills the browser).
