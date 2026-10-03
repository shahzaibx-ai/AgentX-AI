# Frontend guide

Stack: Next.js 16 (App Router, Turbopack), React 19, TypeScript 7, Tailwind CSS 4,
shadcn/ui (Radix base, new-york style, neutral base colour), lucide-react,
next-themes, react-markdown + remark-gfm, sonner, Geist font via the `geist`
package (self-hosted, no Google Fonts fetch at build time).

## Design language (keep it)

The target look is a calm, professional assistant UI in the spirit of Claude
and ChatGPT, suitable for international clients:

- Neutral greys only (oklch tokens in `app/globals.css`); **no gradients**, no
  glows, no coloured hero sections. Colour is reserved for state: destructive
  red, success green dot.
- One content column, `max-w-3xl`, centred. User messages are right-aligned
  rounded bubbles (`bg-secondary`); assistant messages are unboxed prose with a
  small square avatar.
- 15px body text, `leading-7`, Geist Sans; code in Geist Mono.
- Actions appear on hover (always visible on touch devices and on the latest reply).
- Light, dark and system themes with identical layout.
- Mobile: sidebar becomes a left `Sheet`; composer respects the safe-area inset;
  Enter inserts a newline on touch keyboards (send with the button).

## Rebranding

Everything user-visible that names the product lives in `web/lib/config.ts`:

```ts
export const APP_CONFIG = {
  appName: "Assistant",
  appDescription: "AI assistant powered by local and cloud models",
  user: { name: "Rizwan", subtitle: "Workspace" },   // placeholder until auth
};
```

`scaffold.py --app-name --user-name --description` rewrites these. The API's
display name is `APP_NAME` / `app_name` in `api/app/core/config.py`. Suggestions
on the empty screen are the `SUGGESTIONS` array in `components/chat/empty-state.tsx`.
Brand accent: change `--primary` (and `--ring`) in `:root` and `.dark`.

## Component map

| Component | Notes |
|---|---|
| `chat-app.tsx` | Owns `useModels` + `useChat`; desktop sidebar collapses with a negative margin and `inert`; shortcuts: Ctrl/⌘+Shift+O new chat, Ctrl/⌘+K search, Esc stop |
| `app-sidebar.tsx` | Date groups (Today / Yesterday / 7 days / 30 days / Older), search across titles and message text, per-chat menu, theme menu, API status dot |
| `model-picker.tsx` | Radio groups: Auto, Local · Ollama (size + params), Cloud sub-menus per provider (scrollable), setup hints when nothing is installed, Refresh |
| `message-list.tsx` | Sticks to bottom only while the user is near it (120 px); floating jump-to-latest button |
| `message.tsx` | Copy, thumbs up/down (toggle), regenerate on last reply, error card with Try again, model badge (local/cloud icon), fallback notice |
| `markdown.tsx` | GFM tables wrapped for horizontal scroll, fenced code with language label + copy, links open in new tab. Memoised |
| `composer.tsx` | `field-sizing-content` auto-grow (max ~13 rows), send ↔ stop toggle, disabled with an explanatory placeholder when no model exists |
| `empty-state.tsx` | Greeting rendered after mount (time-of-day differs server vs client, avoids hydration mismatch) |

## State rules

- All browser-only reads (localStorage, time, matchMedia) happen in effects,
  never during render, so the page prerenders statically without hydration warnings.
- `use-chat` keeps the latest `selection` in a ref, so an in-flight `send`
  always uses the model picked at send time.
- Deleting a chat or clearing all returns an undo function; the UI shows it in
  a sonner toast.
- Only finished messages are persisted (`pending` ones are filtered out).
  Storage is capped at 200 conversations.

## Adding shadcn components

`components.json` is configured (`@/components/ui`, `@/lib/utils`,
`app/globals.css`). On a machine with internet access:

```bash
npx shadcn@latest add dialog select avatar
```

If the registry is unreachable (air-gapped / proxied environments), hand-write
the component using the same conventions as the existing ones: `data-slot`
attributes, `cn()` for classes, primitives imported from the unified
`radix-ui` package (`import { Dialog as DialogPrimitive } from "radix-ui"`),
`Slot.Root` for `asChild`.

## Accessibility checklist

- Every icon-only button has `aria-label` (tooltips are not labels).
- The thread is `role="log"` with `aria-live="polite"` and `aria-busy` while streaming.
- Sheet has a visually-hidden `SheetTitle` and `SheetDescription`.
- Focus rings come from shadcn (`focus-visible:ring-[3px]`); don't remove them.
- Collapsed desktop sidebar is `inert` so it's skipped by keyboard and screen readers.
