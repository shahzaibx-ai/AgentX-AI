# Sentiment Studio web

Next.js 16 · React 19 · TypeScript 7 · Tailwind CSS 4 · shadcn/ui. Requires Node.js 24.

```bash
npm install
npm run dev          # http://localhost:3000 (API expected on http://localhost:8000)
npm run typecheck
npm run build && npm start
```

`/api/*` is forwarded to `API_URL` (default `http://localhost:8000`, read at build
time; see `next.config.ts`).

```
app/                      layout (fonts, theme, toasts), page, globals.css (tokens)
components/studio/        studio-app (shell, state), analyze-view, result-view,
                          probability-bars, word-influence, batch-view, model-view,
                          sidebar (history), topbar (model picker, status, theme)
components/ui/            shadcn/ui primitives
hooks/                    use-models (catalog + status polling), use-history
lib/                      api client, types (mirror api/app/schemas.py), labels,
                          csv import/export, formatting, config (name, placeholder user)
```
