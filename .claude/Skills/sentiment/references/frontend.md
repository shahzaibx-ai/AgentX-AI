# Frontend

Next.js 16 (App Router, standalone output) · React 19 · TypeScript 7 (`next typegen && tsc`) ·
Tailwind CSS 4 · shadcn/ui on the unified `radix-ui` package · `geist` fonts · `next-themes` · `sonner`.

## Design language

- A neutral, cool-biased palette with no gradients and no decorative colour.
  Tokens live in `app/globals.css` (light `:root`, dark `.dark`); edit tokens,
  never colours in components.
- **Sentiment colours** form a diverging scale, validated for colour-vision
  deficiency in both themes:

  | Token | Light | Dark | Meaning |
  |---|---|---|---|
  | `--positive` | `#2a78d6` | `#3987e5` | positive, 5 stars |
  | `--stars-4` | `#86b6ef` | `#256abf` | 4 stars |
  | `--neutral` | `#8b8983` | `#6b6964` | neutral, 3 stars |
  | `--stars-2` | `#ee8f8e` | `#a84a4a` | 2 stars |
  | `--negative` | `#e34948` | `#e66767` | negative, 1 star |

  Blue means positive, not green, so red/green colour blindness can't confuse the
  classes. Every colour appears with a text label (`LabelPill`, `Swatch` plus a
  name), never alone.
- Other rules:
  - `--warning` is for low confidence and truncation;
  - `--destructive` is for errors;
  - `--success` marks the "ready" status dot.
- Type: Geist Sans for UI, Geist Mono for ids, tokens and numbers
  (`tabular-nums` via the `tabular` utility).
- Layout: a 288 px sidebar (a sheet on mobile), a top bar with the model picker,
  status chip, theme toggle and tabs (full width on mobile), and content at a
  maximum of 1180 px. Cards (`components/ui/card.tsx`) hold each panel.

## Components worth knowing

- `ProbabilityBars`: one row per class in API order, a bar with a 4 px rounded
  end on a muted track, the value as text, and the logit in the tooltip.
- `WordInfluence`: the original text; each word's background is `color-mix` of
  the sentiment colour at 10–44 % by |weight|, and weights under 0.05 are
  unshaded. The legend is always shown.
- `ResultView`: verdict tile (icon plus colour plus name), a low-confidence chip
  under `limits.low_confidence`, expected star rating for star models, a
  truncation notice, and the tokens in `<details>`.
- `BatchView`: 64-row chunks, `Progress`, Cancel (AbortController), stats,
  distribution bar (proportional `flex: n 1 0%` segments, 2 px gaps, tooltips,
  legend with counts), filter chips, a sticky-header table, and
  `downloadFile(toCsv(...))`.
- `ModelView`: `Details` (a definition list that stacks on phones), and the
  load/use actions. It calls `onRefresh` after a failed load, because the
  server's status is the truth.

## State rules

- API types come only from `lib/types.ts`, which must match `api/app/schemas.py`.
- Every request goes through `lib/api.ts`:
  - timeouts are 15 s for status and 10 min for predictions and loads;
  - aborts use `anySignal`/`timeoutSignal`, with fallbacks for older Safari;
  - errors are `ApiError`, where status 0 means unreachable.
- Browser storage goes through `lib/storage.ts` only; it never throws. Keys are
  namespaced by app slug, and history entries are validated when read.
- Don't use `crypto.randomUUID()`: it is missing on plain-http LAN addresses.
- Hydration: localStorage is read in effects, never during render.

## Adding a view

1. Add a trigger in the `TabsList` in `studio-app.tsx`, and add the value to `VIEWS`.
2. Add a `TabsContent` with `forceMount` and `data-[state=inactive]:hidden`, so
   its state persists across tabs.
3. Build it from `Card`, `Eyebrow`, `LabelPill` and the tokens. Test light, dark
   and 390 px wide (`assets/testing/studio_e2e.js` checks the phone width).

## Accessibility

- Tabs, select and sheet are Radix (keyboard and ARIA handled).
- Result card is `aria-live="polite"`; errors use `role="alert"`; the status
  chip uses `role="status"`.
- Probability rows are focusable with an `aria-label`; the distribution bar has
  a `role="img"` label with its counts.
- Icon buttons have labels ("Open history", "Switch between light and dark"); the
  e2e test selects by them, so keep them stable.
- Animations respect `motion-reduce`.
