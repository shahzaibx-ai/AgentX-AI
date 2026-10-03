# Adding photos to another React / Next.js frontend

Copy from `assets/web/`. They use shadcn/ui (`Button`, `DropdownMenu`,
`Tooltip`), `lucide-react`, `sonner` (for the limit toast) and `radix-ui`
`Dialog` for the viewer.

| File | Role |
|---|---|
| `lib/images.ts` | Limits, error wording, `precheck`, `prepareImage` (canvas resize/re-encode), `blobToBase64`, `textWithPhotoNote` |
| `lib/image-store.ts` | IndexedDB `saveImage` / `loadImage` / `deleteImage` / `imageUrl` / `collectGarbage` (in-memory fallback) |
| `hooks/use-attachments.ts` | Tray state: `add(files)`, `remove`, `dismiss`, `takeAll()`, `processing`, `problems` |
| `hooks/use-image-url.ts` | Object URL for a stored photo (`undefined` while loading, `null` if gone) |
| `components/photos/attachment-tray.tsx` | Thumbnails with a spinner, a "2048px" badge, remove buttons, error chips and lines |
| `components/photos/photo-gallery.tsx` | Photos inside a sent message; opens the viewer |
| `components/photos/photo-viewer.tsx` | Full-screen viewer: arrows, ←/→, Esc, "1 of 3", size and resize info |
| `components/photos/drop-overlay.tsx` | `PhotoDropZone`: drop anywhere, paste, and guards against the browser opening dropped files |
| `components/photos/vision-notice.tsx` | The info or warning line above the input, with an optional action button |

Types to add (they mirror the API): `ChatImage`, `ImageLimits`,
`ModelInfo.vision`, `ModelsResponse.default_vision` and `image_limits`, and
`ChatMessage.images`.

## Wiring

**Composer.** Add these props: `attachments?: UseAttachments`,
`photoLimit`, `notice?: ReactNode` and `blocked?: boolean`.

```tsx
const hasContent = !!value.trim() || (attachments?.items.length ?? 0) > 0;
const canSend = streaming || (hasContent && !disabled && !attachments?.processing && !blocked);
const submit = () => { onSend(value, attachments?.takeAll() ?? []); setValue(""); };
```

Render `{notice}` and `<AttachmentTray attachments={attachments} />` above the
textarea. Put a **+** `DropdownMenu` with two hidden inputs:

```tsx
<input type="file" accept={ACCEPT_ATTR} multiple hidden onChange={onFiles} data-testid="photo-input" />
<input type="file" accept="image/*" capture="environment" hidden onChange={onFiles} />
```

Open the input in `requestAnimationFrame` after the menu closes; some
browsers ignore a click that happens while the menu is closing. If you have
a voice button, show it only when `!hasContent`.

**Page (chat-app).**

```tsx
const limits = models.data?.image_limits ?? DEFAULT_IMAGE_LIMITS;
const attachments = useAttachments(limits);
const chosen = models.selection ? models.effective : null;        // null = Auto
const visionDefault = models.data?.default_vision ?? null;
const canSee = chosen ? !!chosen.vision : !!visionDefault;
const chat = useChat(selection, { send: models.data ? canSee : true, perRequest: limits.per_request,
                                  perMessage: limits.per_message, maxBytes: limits.max_bytes });
```

Notice rules:

| Situation | Tone | Text | Blocks send |
|---|---|---|---|
| Photos attached, chosen model is text-only | warning | "**X** can't see images. Switch to a model that can, or remove the photos." + **Use Y** | yes |
| Photos attached, Auto, no vision model | warning | "No model that can see images is available. Run `ollama pull gemma3` or add a cloud API key, then refresh the model list." | yes |
| Photos attached, Auto | info | "Auto will answer with **Y**, a local model that can see images." | no |
| No photos attached, chat has photos, chosen model is text-only | info | "**X** can't see images, so it only gets a note that this chat has photos." + **Use Y** | no |

Mount `<PhotoDropZone enabled={!voice && !noModels} onFiles={attachments.add} limitText=… />`
once, at page level. Suggestions and quick actions should also send the tray
photos (`chat.send(text, attachments.takeAll())`).

**Chat hook.**
- `send(text, images)` stores metadata in the message.
- Build the request with `toApiMessages(history, policy)`: load the blobs
  and base64-encode them, newest first within the budget.
- The title of a photo-only chat is "Photo" or "N photos".
- At load, run `collectGarbage(idsInSavedChats, Date.now() - 24h)`.

**Messages.**
- Render `<PhotoGallery images={m.images} />` above the bubble, and omit the
  empty bubble for photo-only messages.
- While a reply is pending with no text yet, show "Looking at N photos…"
  with mini thumbnails.

**Model picker.** Show a "Sees images" tag on vision models. When photos are
attached or already in the chat, show Auto's label as `Auto · <default_vision>`.

**Sidebar.** Show an image icon on chats that contain photos.

## Without Next.js

Nothing in the photo code depends on Next.js. `"use client"` is harmless
elsewhere, and `@/` is the usual path alias.
