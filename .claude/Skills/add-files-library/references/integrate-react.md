# Another React / Next.js frontend

Needs shadcn/ui-style primitives (`button`, `dropdown-menu` with
`DropdownMenuCheckboxItem` and `Sub*`, `sheet`, `input`, `textarea`, `skeleton`,
`dialog` is included), `sonner`, `lucide-react`, `react-markdown`.

Copy from `assets/web/`: `lib/library.ts`, `lib/library-admin.ts`,
`hooks/use-chat-files.ts`, `hooks/use-library-config.ts`, `components/files/*`,
`components/library/*`, `components/ui/dialog.tsx`, `app/library/**` (Next App
Router; for other routers render `<LibraryShell>` around each page component).
`lib/library.ts` imports `API_BASE`, `ApiError` and `errorMessage` from
`lib/api.ts`; provide them.

Wire it in:

1. **Types:** `ChatFile {id,name,ext,size}`, `CollectionRef {id,name}`,
   `Citation {number,title,text,page,cited,document_id,kind,collection}`; messages
   get `files?`, `collections?`, `sources?`; conversations `collections?`.
2. **Send:** the user message stores `files` (from `takeReady()`) and the chosen
   `collections`. Each request sends `rag = {collections: <last question's>, files:
   <every file in the chat, deduped>, chat_id: <conversation id>}`, or nothing.
3. **Stream:** on `event: sources`, replace the reply's content with
   `cited_text` and store `sources` (only when `grounded`).
4. **New chats:** upload files under a draft id and create the conversation with
   that id on send, so `chat_id` matches. Discard the tray when switching chats.
5. **Composer:** + menu → *Add files* (hidden `<input type=file multiple
   accept=extensions>`) and *Search Library* (checkbox sub-menu of
   `config.collections`); chips with progress/"Reading the file…"/errors; pills
   with ×; block sending while files are uploading or indexing.
6. **Messages:** `<Markdown citations={sources.length} onCite>` turns `[n]` into
   buttons (only n ≤ sources); `<SourcesList>` + `<SourcePanel>`; "Searching
   HR…" while pending; show `meta.notice` when not a fallback.
7. **Removing files:** never delete an uploaded file whose upload said
   `reused: true`. Deleting a chat deletes its file ids after the Undo window.
8. **Proxy:** if `/api` is proxied, raise its body limit above 100 MB (Next:
   `experimental.proxyClientMaxBodySize: "110mb"`, `proxyTimeout: 120_000`;
   nginx: `client_max_body_size 110m`) and keep buffering off for `/api/chat`.
