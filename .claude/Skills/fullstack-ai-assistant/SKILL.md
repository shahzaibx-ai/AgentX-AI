---
name: fullstack-ai-assistant
description: Build a production-ready full-stack AI chat assistant (ChatGPT/Claude-style) with a FastAPI backend (Python 3.13, uv, ruff, pytest) that uses local Ollama models first and falls back to cloud AI (Anthropic, OpenAI, Gemini, Grok, Meta Llama), plus a Next.js 16 / React 19 / TypeScript 7 / Tailwind 4 / shadcn/ui frontend with streaming chat, a local-vs-cloud model dropdown, history, and light/dark themes. Use whenever the user asks to create, scaffold, extend, rebrand, deploy, or debug an AI chatbot / AI assistant web app, a local-LLM chat UI, an Ollama + cloud fallback backend, or "the full stack AI app" built with this system, including adding providers, auth, database history, or file uploads to it.
---

# Full-stack AI Assistant

A tested, client-ready template plus the knowledge to adapt it. The bundled
project passes ruff, 20 pytest tests, a TypeScript 7 type check and a Next.js
production build straight out of the scaffolder.

```
<project>/
├── api/   FastAPI · Python 3.13 · uv · ruff · pytest · ollama / anthropic / openai SDKs
├── web/   Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui (Radix)
├── docker-compose.yml   api + web (+ optional Ollama profile)
└── README.md
```

**Core behaviour:** the model dropdown offers *Auto*, every installed Ollama
chat model, and live model lists from each cloud provider whose API key is set.
Auto uses the first local model, then cloud in `CLOUD_PRIORITY` order. If the
chosen model fails before sending text, the API falls back to the next one and
tells the UI (`meta.fallback`, `meta.notice`). Replies stream over SSE.

## Workflow

### 1. Settle the brief (ask only what changes the build)

Defaults are good; ask at most one short question, and only if the request
leaves a real choice open. Useful inputs:

| Input | Default |
|---|---|
| App display name | `Assistant` |
| Placeholder user name | `Rizwan` |
| Cloud providers to enable | all five, enabled by whichever keys are set |
| Extra scope (auth, DB history, uploads, RAG) | none; see `references/extending.md` |

Never use other invented person names in UI or docs; the placeholder user is
**Rizwan** unless the user gives another name.

### 2. Refresh versions when time has passed

The template was pinned and verified in **September 2026**: Next.js 16.3.6,
React 19.2.8, TypeScript 7.0.2, Tailwind 4, FastAPI 0.141, ollama 0.6,
anthropic 1.8, openai 3.19. If the current date is months later, check the
latest stable versions (web search / `npm view <pkg> version` /
`pip index versions <pkg>`) and bump them after scaffolding, then re-run
verification. Don't downgrade the user's requested major versions.

### 3. Scaffold

```bash
python <skill-dir>/scripts/scaffold.py --dest ./<folder> \
  --app-name "Acme Copilot" --user-name "Rizwan" \
  --description "Acme's internal AI assistant"
```

This copies `assets/template/`, renames packages (`<slug>-api`, `<slug>-web`,
including both lockfiles), sets the UI name/user in `web/lib/config.ts`, the
API title, the README heading, and creates `api/.env` + `web/.env.local` from
the examples. It refuses to overwrite an existing folder without `--force`.

Do not rebuild the project by hand or from memory; the template encodes fixes
for several non-obvious pitfalls (`references/troubleshooting.md`).

### 4. Customise

Read only the reference you need:

| Task | Read |
|---|---|
| Understand how the pieces fit / change behaviour | `references/architecture.md` |
| Change or consume the HTTP/SSE API | `references/api-contract.md` |
| Add or tune an AI provider (Mistral, Groq, LM Studio, …) | `references/providers.md` |
| UI changes, rebranding, new shadcn components, a11y | `references/frontend.md` |
| Auth, database history, attachments, RAG, reasoning, usage | `references/extending.md` |
| Docker, env vars, reverse proxy, platform notes, go-live | `references/deployment.md` |
| Anything failing | `references/troubleshooting.md` |

Rules that keep the codebase coherent:

- SDK types stay inside `api/app/providers/`; everything else sees `Provider`,
  `ModelInfo`, `ChatMessage` and `ProviderError`.
- Routes stay thin; logic lives in `services/` and the registry.
- Settings are read from `request.app.state.settings` (via `deps.py`), never
  from the global `get_settings()` inside routes, so tests can inject config.
- Keep `web/lib/types.ts` in sync with `api/app/schemas.py`.
- New UI uses shadcn/ui primitives, the neutral token palette and the existing
  spacing; **no gradients or decorative colour** (see "Design language" in
  `references/frontend.md`).
- Every new backend behaviour gets a pytest using `FakeProvider`; no network in tests.
- User-facing error strings are short and never leak keys or stack traces.

### 5. Verify (always, before delivering)

```bash
bash <skill-dir>/scripts/verify.sh ./<folder>          # api + web
bash <skill-dir>/scripts/verify.sh ./<folder> --api    # backend only
```

Runs `uv sync`, `ruff check`, `ruff format --check`, `pytest`, `npm ci`,
`npm run typecheck` (next typegen + tsc 7) and `npm run build`. Fix every
failure; don't deliver with red checks.

For a live smoke test, start the API (`uv run fastapi dev app/main.py`) and web
(`npm run dev`), then:

```bash
python <skill-dir>/scripts/doctor.py --api http://localhost:8000 --web http://localhost:3000
```

If Ollama isn't installable in the environment, the troubleshooting guide
describes a stand-in server that exercises the real Ollama SDK path. When UI
changes are made and a headless browser is available, screenshot light, dark
and a 390 px mobile viewport and look at them before delivering.

### 6. Deliver

Exclude `node_modules`, `.next`, `.venv`, caches and real `.env` files, zip the
project folder, and send it. Summarise in a few sentences: what was built or
changed, what was verified (with numbers, e.g. "20 tests pass"), anything that
could not be tested (e.g. live cloud keys), and the three run commands:

```bash
ollama pull llama3.2
cd api && uv sync && uv run fastapi dev app/main.py
cd web && npm install && npm run dev
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/scaffold.py` | Create a new project from the template (stdlib only) |
| `scripts/verify.sh` | All quality gates; non-zero exit on failure (CI-safe) |
| `scripts/doctor.py` | Check tools (uv, Node ≥ 20.9, Ollama), Ollama models, a running API and the web proxy |

## Template map (key files)

```
api/app/main.py                  create_app() factory, lifespan, CORS
api/app/core/config.py           all settings / env vars
api/app/providers/base.py        Provider interface + ProviderError
api/app/providers/ollama.py      local models (filters embedding models)
api/app/providers/anthropic.py   Claude via anthropic SDK
api/app/providers/openai_compat.py  OpenAI, Gemini, Grok, Meta via OpenAI-compatible APIs
api/app/providers/registry.py    build_providers(), model probing + cache, candidate order
api/app/services/chat.py         streaming + fallback-before-first-token
api/tests/                       FakeProvider fixtures; chat, models, provider tests
web/lib/config.ts                app name + placeholder user (rebrand here)
web/lib/api.ts                   fetch + SSE parser
web/hooks/use-chat.ts            conversations, streaming, persistence
web/hooks/use-models.ts          model list + persisted selection
web/components/chat/*            sidebar, model picker, messages, markdown, composer
web/components/ui/*              shadcn/ui primitives
web/next.config.ts               /api rewrite to API_URL, standalone output, no compression
```
