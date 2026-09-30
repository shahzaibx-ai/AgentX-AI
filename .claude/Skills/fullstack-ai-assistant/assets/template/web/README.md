# AI Assistant — Web

Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui

## Run

```bash
npm install
cp .env.example .env.local     # API_URL=http://localhost:8000
npm run dev                    # http://localhost:3000
```

The browser calls `/api/*` on this app; `next.config.ts` forwards those
requests to the FastAPI server at `API_URL`, so no CORS setup is needed.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with Turbopack |
| `npm run typecheck` | TypeScript 7 type check |
| `npm run build` | Production build (standalone output) |
| `npm start` | Serve the production build |

## Structure

```
app/
  layout.tsx            fonts, theme provider, tooltips, toasts
  page.tsx              renders <ChatApp />
  globals.css           Tailwind 4 + shadcn theme tokens (light/dark) + chat typography
components/
  ui/                   shadcn/ui primitives (button, dropdown-menu, sheet, tooltip, …)
  chat/
    chat-app.tsx        layout, sidebar, header, shortcuts
    app-sidebar.tsx     history, search, theme, delete
    model-picker.tsx    Auto / local Ollama models / cloud providers dropdown
    message-list.tsx    thread with stick-to-bottom scrolling
    message.tsx         bubbles, actions, model badge, fallback notice
    markdown.tsx        GFM markdown with copyable code blocks
    composer.tsx        auto-growing input, send/stop
    empty-state.tsx     greeting + suggestions
hooks/
  use-models.ts         loads /api/models, remembers the chosen model
  use-chat.ts           conversations, streaming, stop/regenerate, local persistence
lib/
  api.ts                fetch + server-sent-event parser
  types.ts              shared types (mirror the API schemas)
  config.ts             app name + placeholder user (rebrand here)
```

## Adding shadcn components

`components.json` is configured, so `npx shadcn@latest add dialog` (etc.) drops
new components into `components/ui`.

## Notes

- Chat history is stored in the browser (localStorage). Swap `hooks/use-chat.ts`
  persistence for your database when you add accounts.
- App name and the placeholder user (Rizwan) live in `lib/config.ts`; replace the user with real data once you add auth.
