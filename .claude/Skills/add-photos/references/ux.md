# UX: states, wording, layout, accessibility

The feature was designed first as an HTML prototype. It follows the chat app's
design language: neutral shadcn tokens, rounded cards and no gradients. The
only colours are the destructive red for errors and amber for the text-only
warning.

## Entry points

- **+ button** at the bottom-left of the composer, with the tooltip "Add
  photos". Its menu has:
  - **Add photos**: "JPEG, PNG, WebP or GIF · up to 5".
  - **Take a photo**: "Opens your camera" on touch devices, otherwise "Uses
    your camera on phones and tablets".
  - A footer: "You can also paste or drop photos."
- **Paste** anywhere, unless a text field has focus and the clipboard also
  has plain text.
- **Drop** anywhere. A full-page overlay says "Drop photos to add them" and
  "JPEG, PNG, WebP or GIF · up to 5 photos, 10 MB each". Esc hides it.

## Tray (above the input)

- 64 px square thumbnails with rounded corners. Each has an × to remove it,
  and hovering shows a title with the name, dimensions and "(resized from
  4032×3024)".
- While a photo is being prepared, a spinner ring is shown and the send
  button says "Waiting for photos to be ready".
- A "2048px" badge appears on photos that were scaled down.
- Rejected files show as a red chip (file-x icon and name) plus an alert
  line: "**name** · reason". Dismissing the chip removes the line.
- The count "2 of 5 photos" appears next to the + button.

## Wording (keep it)

| Case | Text |
|---|---|
| HEIC | HEIC photos aren't supported yet. On iPhone, share it as JPEG (or set Camera → Formats → Most Compatible). |
| Wrong type | Only JPEG, PNG, WebP and GIF photos can be added. |
| Broken file | This file couldn't be read as an image. |
| Too large | 14.2 MB is over the 10 MB limit. Export a smaller copy. |
| Too many (toast) | Up to 5 photos per message. · "receipt.jpg wasn't added." |
| Text-only model | **llama3.2** can't see images. Switch to a model that can, or remove the photos. [Use gemma3:4b] |
| Switched (toast) | Switched to gemma3:4b. It can see images. |
| No vision model | No model that can see images is available. Run `ollama pull gemma3` or add a cloud API key, then refresh the model list. |
| Auto info | Auto will answer with **gemma3:4b**, a local model that can see images. |
| History + text-only | **llama3.2** can't see images, so it only gets a note that this chat has photos. [Use gemma3:4b] |
| Privacy (local) | 🔒 Photos stay on this computer: **gemma3:4b** runs locally. (+ "If it fails, a cloud model may answer instead." when a cloud vision model exists) |
| Privacy (cloud) | ☁ Photos are sent to **OpenAI** to answer. |
| Waiting | Looking at 2 photos… |
| Photo-only message | Sent 2 photos |
| Missing photo | This photo is no longer stored in this browser. |

## Messages

- User photos sit right-aligned above the text bubble.
  - A single photo keeps its aspect ratio, up to 320 px wide and 320 px tall.
  - Two or four photos use a 2-column grid; three or five use 3 columns.
    The tiles are square.
- The viewer is a near-black overlay (95%). The header has the name,
  "900×1200 · 72 KB · resized from …", "1 of 2" and a close button. There
  are round previous/next buttons, and ←/→/Esc work. Clicking the backdrop
  closes it.

## Accessibility

- Every button has an aria-label: "Add photos", "Remove <name>", "Dismiss
  <name>", "View <name>", "Previous photo", "Next photo", "Close".
- Errors use `role="alert"`. The vision notice uses `alert` (warning) or
  `status` (info). The count and privacy line are `aria-live="polite"`.
- The viewer is a Radix Dialog, which traps focus and returns it on close.
  It has a title and a description.
- The drop overlay is `aria-hidden` because the same actions exist in the
  + menu.

## Layout

- Phone (390 px): the notice wraps and its button stays on the right. The
  tray wraps, and there is no sideways scrolling.
- Dark mode uses the same tokens. The warning uses `amber-500/10` with
  `amber-200` text.
