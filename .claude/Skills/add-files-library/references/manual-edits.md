# Manual edits

Every edit `install_library.py` makes to existing files, numbered the way its
report numbers them. Use this when the installer says a file was customised:
find the variant, file and edit number, then make the `+` lines appear where
the unchanged (space-prefixed) lines point. Lines starting with `-` are
replaced. Generated from `scripts/patches*.py`; do not edit by hand.

The installer reports which variant it matched: **with voice mode** or
**without voice mode**. Most API edits are the same in both.

What each file gets, in one line:

| File | Change |
|---|---|
| `api/pyproject.toml` | `google-genai` dependency; dev `pypdf`, `python-docx`; ruff per-file ignores; a pytest warning filter |
| `api/.env.example` | Files and the Library block (`RAG_*`, `LIBRARY_*`, chat file limits) |
| `api/.gitignore`, `api/Dockerfile`, `docker-compose.yml` | `data/` ignored; writable `/app/data/library`; a `library` volume |
| `api/app/main.py` | `create_app(library_settings=, library_engine=)`, PATCH/DELETE in CORS, body limits for uploads, `mount_library` + its lifespan |
| `api/app/schemas.py` | `RagScope` (collections, files, chat_id) and `ChatRequest.rag` |
| `api/app/routes/chat.py` | requests with `rag` go to `rag_chat_events` |
| `api/tests/conftest.py` | `library_settings` fixture; `make_client(library=, library_engine=)` |
| `web/next.config.ts` | rewrite body limit 110 MB, proxy timeout 120 s |
| `web/lib/types.ts` | `ChatFile`, `CollectionRef`, `Citation`; message `files`/`collections`/`sources`; conversation `collections` |
| `web/lib/api.ts` | exports `API_BASE`, `errorMessage`; `rag` in the request; `sources` event |
| `web/hooks/use-chat.ts` | `send(text, {images, files, collections, newChatId})`, `ragFor`, citations, `setCollections` |
| `web/components/ui/dropdown-menu.tsx` | `DropdownMenuCheckboxItem` |
| `web/components/photos/drop-overlay.tsx` | optional `title` |
| `web/components/chat/markdown.tsx` | `[n]` markers become citation buttons |
| `web/components/chat/composer.tsx` | Add files, Search Library sub-menu, file chips, Library pills, `onSend(text)` |
| `web/components/chat/message*.tsx` | file chips, "Searching …", Sources + passage panel, notices |
| `web/components/chat/app-sidebar.tsx` | Library link (Owner), paperclip on chats with files |
| `web/components/chat/chat-app.tsx` | draft chat id, file tray, collections per chat, drop routing, delete-with-undo purge, privacy line |
| `README.md`, `api/README.md`, `web/README.md` | docs (optional) |

# With voice mode

Files: `api/pyproject.toml` (4), `api/.env.example` (1), `api/.gitignore` (1), `api/Dockerfile` (1), `api/app/main.py` (5), `api/app/schemas.py` (1), `api/app/routes/chat.py` (3), `api/tests/conftest.py` (2), `docker-compose.yml` (2), `web/next.config.ts` (1), `web/lib/types.ts` (3), `web/lib/api.ts` (10), `web/hooks/use-chat.ts` (9), `web/components/ui/dropdown-menu.tsx` (2), `web/components/photos/drop-overlay.tsx` (3), `web/components/chat/markdown.tsx` (2), `web/components/chat/composer.tsx` (16), `web/components/chat/message.tsx` (13), `web/components/chat/message-list.tsx` (2), `web/components/chat/app-sidebar.tsx` (6), `web/components/chat/chat-app.tsx` (15), `README.md` (4), `api/README.md` (3), `web/README.md` (6)

## api/pyproject.toml

**Edit 1 of 4**

```diff
     "livekit-api>=1.2.1",
+    "google-genai>=2.26",
 ]
```

**Edit 2 of 4**

```diff
 dev = [
+    "pypdf>=6.19.0",
     "pytest>=9.1",
     "pytest-asyncio>=1.2",
+    "python-docx>=1.2.0",
     "ruff>=0.16",
```

**Edit 3 of 4**

```diff
 "tests/**" = ["PLR2004", "S101"]
+# Lazy imports keep optional engines (and dev-only parsers) out of normal startup.
+"app/library/__init__.py" = ["PLC0415"]
+"app/library/offline.py" = ["PLC0415", "PLW2901"]
+"app/library/citations.py" = ["PLW2901"]
 
```

**Edit 4 of 4**

```diff
 addopts = "-q"
+filterwarnings = [
+    # google-genai subclasses aiohttp.ClientSession; harmless, outside our code.
+    "ignore:Inheritance class AiohttpClientSession:DeprecationWarning",
+]
```

## api/.env.example

**Edit 1 of 1**

```diff
+
+# ---------- Files and the Library (RAG with citations) ----------
+# On when GEMINI_API_KEY (above) is set: files are indexed with Gemini File Search
+# and questions about them are answered by RAG_MODEL with citations.
+# RAG_ENGINE=offline uses a local keyword stand-in instead (testing without a key).
+RAG_ENGINE=
+RAG_MODEL=gemini-3.8-flash
+RAG_EMBEDDING_MODEL=
+RAG_CHUNK_TOKENS=400
+RAG_CHUNK_OVERLAP=40
+RAG_TOP_K=6
+RAG_STORE_NAME=assistant-library
+# Originals and the Library database (keep this folder in backups / a Docker volume).
+LIBRARY_DATA_DIR=data/library
+# Owner access to the Library pages. Required when ENVIRONMENT=production:
+#   python -c "import secrets; print(secrets.token_urlsafe(32))"
+LIBRARY_TOKEN=
+LIBRARY_FILE_MAX_BYTES=104857600
+CHAT_FILE_MAX_BYTES=26214400
+CHAT_FILES_PER_MESSAGE=10
+CHAT_FILE_RETENTION_DAYS=30
 
 # ---------- Photos ----------
```

## api/.gitignore

**Edit 1 of 1**

```diff
 .env
+
+# Library originals and database (LIBRARY_DATA_DIR)
+data/
```

## api/Dockerfile

**Edit 1 of 1**

```diff
 WORKDIR /app
-RUN useradd --create-home --uid 10001 appuser
+RUN useradd --create-home --uid 10001 appuser \
+ && mkdir -p /app/data/library && chown -R appuser /app/data
 COPY --from=build /app /app
```

## api/app/main.py

**Edit 1 of 5**

```diff
 from app.core.logging import configure_logging
+from app.library import LibrarySettings, RagEngine, mount_library
 from app.providers.registry import ProviderRegistry, build_providers
```

**Edit 2 of 5**

```diff
     voice_settings: VoiceSettings | None = None,
+    library_settings: LibrarySettings | None = None,
+    library_engine: RagEngine | None = None,
 ) -> FastAPI:
```

**Edit 3 of 5**

```diff
         )
-        yield
+        async with library_lifespan(app):
+            yield
         await app.state.registry.aclose()
```

**Edit 4 of 5**

```diff
         allow_origins=settings.cors_origins,
-        allow_methods=["GET", "POST", "OPTIONS"],
+        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
         allow_headers=["*"],
```

**Edit 5 of 5**

```diff
         app.include_router(router, prefix="/api")
+    # Files in chat + the Library (RAG with citations).
+    library_settings = library_settings or LibrarySettings()
+    app.add_middleware(
+        BodySizeLimit,
+        max_bytes=library_settings.chat_file_max_bytes + 1024 * 1024,
+        paths=("/api/files",),
+    )
+    app.add_middleware(
+        BodySizeLimit,
+        max_bytes=library_settings.library_file_max_bytes * 10 + 1024 * 1024,
+        paths=("/api/library/documents",),
+    )
+    library_lifespan = mount_library(
+        app,
+        settings=library_settings,
+        engine=library_engine,
+        production=settings.environment == "production",
+    )
     mount_voice(app, brain=chat_brain, settings=voice_settings)  # voice mode (LiveKit)
```

## api/app/schemas.py

**Edit 1 of 1**

```diff
+
+class RagScope(BaseModel):
+    """Answer from documents: Library collections and/or files added to this chat."""
+
+    collections: list[str] = Field(default_factory=list, max_length=20)
+    files: list[str] = Field(default_factory=list, max_length=50)
+    # The chat the files belong to; files from other chats are ignored.
+    chat_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
+
 
 class ChatRequest(BaseModel):
     messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_REQUEST_MESSAGES)
+    rag: RagScope | None = Field(
+        default=None, description="Search these collections/files and answer with citations"
+    )
     provider: str | None = Field(
```

## api/app/routes/chat.py

**Edit 1 of 3**

```diff
 from app.deps import ChatServiceDep, SettingsDep
+from app.library_chat import rag_chat_events
 from app.schemas import ChatRequest
```

**Edit 2 of 3**

```diff
     Events: `meta` (which provider/model answered), unnamed `data: {"delta": ...}`
-    chunks, then `done` or `error`.
+    chunks, then `done` or `error`. With `rag`, the Library answers and a `sources`
+    event (citations, and the text with [n] markers) comes before `done`.
     """
```

**Edit 3 of 3**

```diff
+
+    library = getattr(request.app.state, "library", None)
+    use_library = bool(body.rag and (body.rag.collections or body.rag.files))
+    stream = rag_chat_events(library, body) if use_library and library else service.stream(body)
 
     async def events() -> AsyncIterator[str]:
-        async for event in service.stream(body):
+        async for event in stream:
             if await request.is_disconnected():
```

## api/tests/conftest.py

**Edit 1 of 2**

```diff
 from app.core.config import Settings
+from app.library import LibrarySettings
 from app.main import create_app
```

**Edit 2 of 2**

```diff
 @pytest.fixture
-def make_client(settings: Settings) -> Iterator:
+def library_settings(tmp_path) -> LibrarySettings:
+    """Library off by default in tests; data in a temp folder."""
+    return LibrarySettings(
+        _env_file=None,
+        rag_engine="",
+        gemini_api_key=None,
+        library_token=None,
+        library_data_dir=tmp_path / "library",
+    )
+
+
+@pytest.fixture
+def make_client(settings: Settings, library_settings: LibrarySettings) -> Iterator:
     clients: list[TestClient] = []
 
-    def factory(*providers: Provider, **overrides) -> TestClient:
+    def factory(
+        *providers: Provider,
+        library: LibrarySettings | None = None,
+        library_engine=None,
+        **overrides,
+    ) -> TestClient:
         cfg = settings.model_copy(update=overrides)
         registry = ProviderRegistry(list(providers), cache_ttl=0, vision_patterns=cfg.vision_models)
-        client = TestClient(create_app(cfg, registry))
+        client = TestClient(
+            create_app(
+                cfg,
+                registry,
+                library_settings=library or library_settings,
+                library_engine=library_engine,
+            )
+        )
         client.__enter__()
```

## docker-compose.yml

**Edit 1 of 2**

```diff
       - "host.docker.internal:host-gateway"
+    volumes:
+      # Library and chat files (originals + index records) survive rebuilds
+      - library:/app/data/library
     ports:
       - "8000:8000"
```

**Edit 2 of 2**

```diff
 volumes:
   ollama:
+  library:
```

## web/next.config.ts

**Edit 1 of 1**

```diff
   compress: false,
+  experimental: {
+    // Uploads pass through the /api rewrite, which caps bodies at 10 MB by default.
+    // Library files are up to 100 MB and are sent one per request.
+    proxyClientMaxBodySize: "110mb",
+    // Big uploads and slow first answers need more than the 30 s default.
+    proxyTimeout: 120_000,
+  },
   async rewrites() {
```

## web/lib/types.ts

**Edit 1 of 3**

```diff
+
+/** A file added to a chat. The original and its index live on the API (Library). */
+export interface ChatFile {
+  id: string;
+  name: string;
+  ext: string;
+  size: number;
+}
+
+/** A Library collection searched for a message. */
+export interface CollectionRef {
+  id: string;
+  name: string;
+}
+
+/** A passage an answer was based on; `number` matches the [n] in the text. */
+export interface Citation {
+  number: number;
+  title: string;
+  text: string;
+  page: number | null;
+  cited: boolean;
+  document_id: string | null;
+  kind: "library" | "chat" | null;
+  collection: string | null;
+}
 
 export interface ChatMessage {
```

**Edit 2 of 3**

```diff
   images?: ChatImage[];
+  /** Files added with a user message (searched for this and later questions). */
+  files?: ChatFile[];
+  /** Library collections searched for this user message. */
+  collections?: CollectionRef[];
+  /** Assistant: passages the answer cites ([n] markers in `content`). */
+  sources?: Citation[];
 }
```

**Edit 3 of 3**

```diff
   messages: ChatMessage[];
+  /** Library collections this chat searches (the pill in the composer). */
+  collections?: CollectionRef[];
   createdAt: number;
```

## web/lib/api.ts

**Edit 1 of 10**

```diff
-import type { ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";
+import type { Citation, ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";
 
```

**Edit 2 of 10**

```diff
  */
-const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
+export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
 
```

**Edit 3 of 10**

```diff
 
-async function errorMessage(res: Response): Promise<string> {
+export async function errorMessage(res: Response): Promise<string> {
   try {
```

**Edit 4 of 10**

```diff
+
+export interface RagRequest {
+  collections: string[];
+  files: string[];
+  /** The chat the files belong to; the API ignores other chats' files. */
+  chat_id?: string;
+}
+
+export interface SourcesEvent {
+  cited_text: string;
+  grounded: boolean;
+  sources: Citation[];
+}
 
 export interface StreamChatOptions {
```

**Edit 5 of 10**

```diff
   selection: ModelSelection;
+  /** Search these Library collections / chat files and answer with citations. */
+  rag?: RagRequest | null;
   signal: AbortSignal;
```

**Edit 6 of 10**

```diff
   onDelta: (text: string) => void;
+  onSources?: (sources: SourcesEvent) => void;
 }
```

**Edit 7 of 10**

```diff
   selection,
+  rag,
   signal,
```

**Edit 8 of 10**

```diff
   onDelta,
+  onSources,
 }: StreamChatOptions): Promise<void> {
```

**Edit 9 of 10**

```diff
         model: selection?.model ?? null,
+        ...(rag && (rag.collections.length || rag.files.length) ? { rag } : {}),
       }),
```

**Edit 10 of 10**

```diff
+        break;
+      case "sources":
+        onSources?.(payload as unknown as SourcesEvent);
         break;
       case "error":
```

## web/hooks/use-chat.ts

**Edit 1 of 9**

```diff
 import { blobToBase64, photoLabel, textWithPhotoNote } from "@/lib/images";
-import type { ChatImage, ChatMessage, Conversation, ModelSelection } from "@/lib/types";
+import type {
+  ChatFile,
+  ChatImage,
+  ChatMessage,
+  CollectionRef,
+  Conversation,
+  ModelSelection,
+} from "@/lib/types";
 
```

**Edit 2 of 9**

```diff
 type Updater = (c: Conversation) => Conversation;
 
+/** Every file added anywhere in the chat: later questions still search them. */
+export const filesOf = (messages: ChatMessage[]): ChatFile[] =>
+  messages.flatMap((m) => (m.role === "user" ? (m.files ?? []) : []));
+
+/** What to search for this reply: the collections picked for the last question,
+ *  plus every file in the chat. Empty → an ordinary model reply. */
+function ragFor(history: ChatMessage[], chatId: string) {
+  const lastUser = [...history].reverse().find((m) => m.role === "user");
+  const collections = (lastUser?.collections ?? []).map((c) => c.id);
+  const files = [...new Set(filesOf(history).map((f) => f.id))];
+  return collections.length || files.length ? { collections, files, chat_id: chatId } : null;
+}
+
+export interface SendOptions {
+  images?: ChatImage[];
+  files?: ChatFile[];
+  collections?: CollectionRef[];
+  /** Id for a new chat (files are uploaded under it before the chat exists). */
+  newChatId?: string;
+}
+
```

**Edit 3 of 9**

```diff
           selection: selectionRef.current,
+          rag: ragFor(history, convId),
           signal: ctrl.signal,
```

**Edit 4 of 9**

```diff
             if (!frame) frame = requestAnimationFrame(flush);
           },
+          onSources: (s) => {
+            cancelAnimationFrame(frame);
+            frame = 0;
+            buffer = "";
+            // The final text carries [n] markers that link to these passages.
+            patchMessage(convId, reply.id, { content: s.cited_text, sources: s.sources });
+          },
```

**Edit 5 of 9**

```diff
   const send = useCallback(
-    (text: string, images: ChatImage[] = []) => {
+    (text: string, opts: SendOptions = {}) => {
+      const { images = [], files = [], collections = [] } = opts;
       const content = text.trim();
-      if ((!content && !images.length) || controller.current) return;
+      if ((!content && !images.length && !files.length) || controller.current) return;
       const userMsg: ChatMessage = {
```

**Edit 6 of 9**

```diff
         ...(images.length ? { images } : {}),
+        ...(files.length ? { files } : {}),
+        ...(collections.length ? { collections } : {}),
       };
```

**Edit 7 of 9**

```diff
       }
+      const fallbackTitle = files.length
+        ? files[0].name
+        : images.length > 1
+          ? `${images.length} photos`
+          : "Photo";
       const conv: Conversation = {
-        id: uid(),
-        title: makeTitle(content || (images.length > 1 ? `${images.length} photos` : "Photo")),
+        id: opts.newChatId ?? uid(),
+        title: makeTitle(content || fallbackTitle),
+        ...(collections.length ? { collections } : {}),
         messages: [],
```

**Edit 8 of 9**

```diff
     [activeId, patchMessage],
   );
+
+  /** The collections a chat searches (the Library pill). */
+  const setCollections = useCallback(
+    (id: string, collections: CollectionRef[]) =>
+      update(id, (c) => ({ ...c, collections })),
+    [update],
+  );
```

**Edit 9 of 9**

```diff
     setFeedback,
+    setCollections,
     newChat,
```

## web/components/ui/dropdown-menu.tsx

**Edit 1 of 2**

```diff
+
+function DropdownMenuCheckboxItem({
+  className,
+  children,
+  checked,
+  ...props
+}: React.ComponentProps<typeof DropdownMenuPrimitive.CheckboxItem>) {
+  return (
+    <DropdownMenuPrimitive.CheckboxItem
+      data-slot="dropdown-menu-checkbox-item"
+      className={cn(
+        "relative flex cursor-default items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-sm outline-hidden select-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
+        className,
+      )}
+      checked={checked}
+      {...props}
+    >
+      <span className="pointer-events-none absolute right-2 flex size-3.5 items-center justify-center">
+        <DropdownMenuPrimitive.ItemIndicator>
+          <CheckIcon className="size-4" />
+        </DropdownMenuPrimitive.ItemIndicator>
+      </span>
+      {children}
+    </DropdownMenuPrimitive.CheckboxItem>
+  );
+}
 
 function DropdownMenuLabel({
```

**Edit 2 of 2**

```diff
   DropdownMenuItem,
+  DropdownMenuCheckboxItem,
   DropdownMenuRadioGroup,
```

## web/components/photos/drop-overlay.tsx

**Edit 1 of 3**

```diff
   limitText,
+  title = "Drop photos to add them",
 }: {
```

**Edit 2 of 3**

```diff
   limitText: string;
+  title?: string;
 }) {
```

**Edit 3 of 3**

```diff
         <ImagePlusIcon className="size-8" />
-        <p className="text-base font-semibold">Drop photos to add them</p>
+        <p className="text-base font-semibold">{title}</p>
         <p className="text-sm text-muted-foreground">{limitText}</p>
```

## web/components/chat/markdown.tsx

**Edit 1 of 2**

```diff
 
-import { memo, useState } from "react";
+import { memo, useMemo, useState } from "react";
 import { CheckIcon, CopyIcon } from "lucide-react";
```

**Edit 2 of 2**

```diff
 
-export const Markdown = memo(function Markdown({ content }: { content: string }) {
+/** `[3]` → a link the citation renderer turns into a button (only for real source numbers). */
+function linkCitations(content: string, count: number): string {
+  return content.replace(/\[(\d{1,2})\](?!\()/g, (m, n: string) =>
+    Number(n) >= 1 && Number(n) <= count ? `[${n}](#cite-${n})` : m,
+  );
+}
+
+export const Markdown = memo(function Markdown({
+  content,
+  citations = 0,
+  onCite,
+}: {
+  content: string;
+  /** Number of sources; [n] markers up to this become buttons. */
+  citations?: number;
+  onCite?: (n: number) => void;
+}) {
+  const withCites = useMemo<Components>(
+    () => ({
+      ...components,
+      a: ({ href, children }) => {
+        const m = /^#cite-(\d+)$/.exec(href ?? "");
+        if (m && onCite) {
+          const n = Number(m[1]);
+          return (
+            <button
+              type="button"
+              onClick={() => onCite(n)}
+              aria-label={`Source ${n}`}
+              className="mx-px inline-grid h-[18px] min-w-[18px] translate-y-[-2px] place-items-center rounded-md border bg-muted px-1 align-middle font-mono text-[11px] leading-none text-muted-foreground no-underline hover:bg-foreground hover:text-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
+            >
+              {n}
+            </button>
+          );
+        }
+        return (
+          <a href={href} target="_blank" rel="noopener noreferrer">
+            {children}
+          </a>
+        );
+      },
+    }),
+    [onCite],
+  );
+  const text = citations && onCite ? linkCitations(content, citations) : content;
   return (
     <div className="prose-chat">
-      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
-        {content}
+      <ReactMarkdown remarkPlugins={[remarkGfm]} components={citations ? withCites : components}>
+        {text}
       </ReactMarkdown>
```

## web/components/chat/composer.tsx

**Edit 1 of 16**

```diff
 import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
-import { ArrowUpIcon, AudioLinesIcon, CameraIcon, ImageIcon, PlusIcon, SquareIcon } from "lucide-react";
+import {
+  ArrowUpIcon,
+  AudioLinesIcon,
+  CameraIcon,
+  ImageIcon,
+  LibraryIcon,
+  PaperclipIcon,
+  PlusIcon,
+  SquareIcon,
+  XIcon,
+} from "lucide-react";
 
+import { FileChip } from "@/components/files/file-chip";
 import { AttachmentTray } from "@/components/photos/attachment-tray";
```

**Edit 2 of 16**

```diff
   DropdownMenu,
+  DropdownMenuCheckboxItem,
   DropdownMenuContent,
   DropdownMenuItem,
+  DropdownMenuSeparator,
+  DropdownMenuSub,
+  DropdownMenuSubContent,
+  DropdownMenuSubTrigger,
   DropdownMenuTrigger,
```

**Edit 3 of 16**

```diff
 import type { UseAttachments } from "@/hooks/use-attachments";
+import type { PendingFile, UseChatFiles } from "@/hooks/use-chat-files";
 import { APP_CONFIG } from "@/lib/config";
 import { ACCEPT_ATTR } from "@/lib/images";
-import type { ChatImage } from "@/lib/types";
+import { formatSize, type CollectionInfo } from "@/lib/library";
+import type { CollectionRef } from "@/lib/types";
 import { cn } from "@/lib/utils";
 
+/** Files and the Library in the composer (only when the API has them on). */
+export interface ComposerFiles {
+  files: UseChatFiles;
+  onAdd: (files: File[]) => void;
+  accept: string;
+  perMessage: number;
+  maxBytes: number;
+  collections: CollectionInfo[];
+  selected: CollectionRef[];
+  onSelect: (collections: CollectionRef[]) => void;
+}
+
+function fileStatus(f: PendingFile): string {
+  switch (f.phase) {
+    case "uploading":
+      return `Uploading · ${Math.round(f.progress * 100)}%`;
+    case "indexing":
+      return "Reading the file…";
+    case "ready":
+      return `${formatSize(f.size)} · Ready`;
+    default:
+      return f.error ?? "Couldn't be added";
+  }
+}
+
```

**Edit 4 of 16**

```diff
   attachments,
+  library,
   photoLimit,
```

**Edit 5 of 16**

```diff
 }: {
-  onSend: (text: string, images: ChatImage[]) => void;
+  /** The parent takes the photos and files from the trays. */
+  onSend: (text: string) => void;
   onStop: () => void;
```

**Edit 6 of 16**

```diff
   attachments?: UseAttachments;
+  library?: ComposerFiles;
   photoLimit?: number;
```

**Edit 7 of 16**

```diff
   const fileInput = useRef<HTMLInputElement>(null);
+  const docInput = useRef<HTMLInputElement>(null);
   const cameraInput = useRef<HTMLInputElement>(null);
```

**Edit 8 of 16**

```diff
   const photoCount = attachments?.items.length ?? 0;
-  const processing = !!attachments?.processing;
-  const hasContent = !!value.trim() || photoCount > 0;
+  const files = library?.files.items ?? [];
+  const readyFiles = files.filter((f) => f.phase === "ready").length;
+  const filesBusy = !!library?.files.busy;
+  const processing = !!attachments?.processing || filesBusy;
+  const hasContent = !!value.trim() || photoCount > 0 || readyFiles > 0;
 
```

**Edit 9 of 16**

```diff
     if (!hasContent || disabled || processing || blocked) return;
-    onSend(value, attachments?.takeAll() ?? []);
+    onSend(value);
     setValue("");
```

**Edit 10 of 16**

```diff
   const canSend = streaming || (hasContent && !disabled && !processing && !blocked);
-  const showVoice = !!onVoice && !streaming && !hasContent;
+  const showVoice = !!onVoice && !streaming && !hasContent && files.length === 0;
   const sendLabel = streaming
     ? "Stop generating"
-    : processing
-      ? "Waiting for photos to be ready"
-      : "Send message";
+    : filesBusy
+      ? "Waiting for files to be ready"
+      : processing
+        ? "Waiting for photos to be ready"
+        : "Send message";
+  const selected = library?.selected ?? [];
+  const isSelected = (id: string) => selected.some((c) => c.id === id);
+  const toggle = (c: CollectionInfo) =>
+    library?.onSelect(
+      isSelected(c.id)
+        ? selected.filter((x) => x.id !== c.id)
+        : [...selected, { id: c.id, name: c.name }],
+    );
 
```

**Edit 11 of 16**

```diff
     if (e.target.files?.length) attachments?.add([...e.target.files]);
     e.target.value = "";
+  };
+  const onDocs = (e: React.ChangeEvent<HTMLInputElement>) => {
+    if (e.target.files?.length) library?.onAdd([...e.target.files]);
+    e.target.value = "";
```

**Edit 12 of 16**

```diff
       {attachments && <AttachmentTray attachments={attachments} />}
+      {files.length > 0 && (
+        <ul className="mb-2 flex gap-2.5 overflow-x-auto pt-1.5 pb-1" aria-label="Files to send">
+          {files.map((f) => (
+            <li key={f.key}>
+              <FileChip
+                name={f.name}
+                ext={f.ext}
+                sub={fileStatus(f)}
+                progress={f.phase === "uploading" ? f.progress : undefined}
+                tone={f.phase === "failed" ? "error" : "default"}
+                onRemove={() => library?.files.remove(f.key)}
+              />
+            </li>
+          ))}
+        </ul>
+      )}
+      {selected.length > 0 && (
+        <div className="mb-1.5 flex flex-wrap gap-1.5" aria-label="Library collections to search">
+          {selected.map((c) => (
+            <span
+              key={c.id}
+              className="inline-flex h-7 items-center gap-1.5 rounded-full border bg-muted/60 pr-1 pl-2.5 text-xs font-medium"
+            >
+              <LibraryIcon className="size-3.5 text-muted-foreground" />
+              Searching {c.name}
+              <button
+                type="button"
+                aria-label={`Stop searching ${c.name}`}
+                onClick={() => library?.onSelect(selected.filter((x) => x.id !== c.id))}
+                className="grid size-5 place-items-center rounded-full outline-none hover:bg-background focus-visible:ring-2 focus-visible:ring-ring"
+              >
+                <XIcon className="size-3" />
+              </button>
+            </span>
+          ))}
+        </div>
+      )}
       <label htmlFor="composer" className="sr-only">
```

**Edit 13 of 16**

```diff
                       size="icon"
-                      aria-label="Add photos"
+                      aria-label={library ? "Add photos and files" : "Add photos"}
                       disabled={disabled}
```

**Edit 14 of 16**

```diff
                 </TooltipTrigger>
-                <TooltipContent>Add photos</TooltipContent>
+                <TooltipContent>{library ? "Add photos and files" : "Add photos"}</TooltipContent>
               </Tooltip>
               <DropdownMenuContent align="start" side="top" className="w-72">
+                {library && (
+                  <>
+                    <DropdownMenuItem onSelect={() => pick(docInput.current)} className="items-start">
+                      <PaperclipIcon className="mt-0.5" />
+                      <span className="flex flex-col">
+                        <span>Add files</span>
+                        <span className="text-xs text-muted-foreground">
+                          PDF, Word, Excel, text, code · up to {library.perMessage},{" "}
+                          {formatSize(library.maxBytes)} each
+                        </span>
+                      </span>
+                    </DropdownMenuItem>
+                    <DropdownMenuSub>
+                      <DropdownMenuSubTrigger className="items-start">
+                        <LibraryIcon className="mt-0.5" />
+                        <span className="flex flex-col">
+                          <span>Search Library</span>
+                          <span className="text-xs text-muted-foreground">
+                            {library.collections.length
+                              ? "Answer from shared documents"
+                              : "No collections yet"}
+                          </span>
+                        </span>
+                      </DropdownMenuSubTrigger>
+                      <DropdownMenuSubContent className="w-64">
+                        {library.collections.length ? (
+                          library.collections.map((c) => (
+                            <DropdownMenuCheckboxItem
+                              key={c.id}
+                              checked={isSelected(c.id)}
+                              onCheckedChange={() => toggle(c)}
+                              onSelect={(e) => e.preventDefault()}
+                            >
+                              <span className="flex min-w-0 flex-col">
+                                <span className="truncate">{c.name}</span>
+                                <span className="text-xs text-muted-foreground">
+                                  {c.documents} {c.documents === 1 ? "document" : "documents"}
+                                </span>
+                              </span>
+                            </DropdownMenuCheckboxItem>
+                          ))
+                        ) : (
+                          <p className="px-2 py-2 text-xs text-muted-foreground">
+                            Library owners add collections on the Library page.
+                          </p>
+                        )}
+                      </DropdownMenuSubContent>
+                    </DropdownMenuSub>
+                    <DropdownMenuSeparator />
+                  </>
+                )}
                 <DropdownMenuItem onSelect={() => pick(fileInput.current)} className="items-start">
```

**Edit 15 of 16**

```diff
                 <p className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
-                  You can also paste or drop photos.
+                  {library ? "You can also paste photos or drop files." : "You can also paste or drop photos."}
                 </p>
```

**Edit 16 of 16**

```diff
             />
+            {library && (
+              <input
+                ref={docInput}
+                type="file"
+                accept={library.accept}
+                multiple
+                hidden
+                onChange={onDocs}
+                data-testid="file-input"
+              />
+            )}
             {photoCount > 0 && (
```

## web/components/chat/message.tsx

**Edit 1 of 13**

```diff
 
-import { useState } from "react";
+import { useCallback, useState } from "react";
 import {
```

**Edit 2 of 13**

```diff
   CloudIcon,
+  InfoIcon,
+  LibraryIcon,
   RefreshCwIcon,
```

**Edit 3 of 13**

```diff
 import { Markdown } from "@/components/chat/markdown";
+import { FileChip } from "@/components/files/file-chip";
+import { SourcePanel, SourcesList } from "@/components/files/sources";
+import { fileUrl, formatSize } from "@/lib/library";
 import { PhotoGallery } from "@/components/photos/photo-gallery";
```

**Edit 4 of 13**

```diff
+
+/** Waiting for a reply that searches files or the Library. */
+function Searching({ label }: { label: string }) {
+  return (
+    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
+      <LibraryIcon className="size-4" />
+      <span className="animate-pulse">{label}</span>
+    </span>
+  );
+}
+
+const stripCitations = (text: string) => text.replace(/\[\d{1,2}\]/g, "");
 
 export function Message({
```

**Edit 5 of 13**

```diff
   lookingIds,
+  searching,
   onRegenerate,
```

**Edit 6 of 13**

```diff
   lookingIds?: string[];
+  /** "Searching HR Policies…" while a reply that uses files hasn't started. */
+  searching?: string;
   onRegenerate: (id: string) => void;
```

**Edit 7 of 13**

```diff
 }) {
+  const [openSource, setOpenSource] = useState<number | null>(null);
+  const onCite = useCallback((n: number) => setOpenSource(n), []);
+
   if (message.role === "user") {
```

**Edit 8 of 13**

```diff
         {!!message.images?.length && <PhotoGallery images={message.images} />}
+        {!!message.files?.length && (
+          <ul className="flex max-w-[85%] flex-wrap justify-end gap-2" aria-label="Files">
+            {message.files.map((f) => (
+              <li key={f.id}>
+                <FileChip name={f.name} ext={f.ext} sub={formatSize(f.size)} href={fileUrl(f.id)} />
+              </li>
+            ))}
+          </ul>
+        )}
         {message.content && (
```

**Edit 9 of 13**

```diff
               Spoken
             </span>
+          )}
+          {!!message.collections?.length && (
+            <span className="flex items-center gap-1 px-1 text-xs text-muted-foreground">
+              <LibraryIcon className="size-3" />
+              Searching {message.collections.map((c) => c.name).join(", ")}
+            </span>
```

**Edit 10 of 13**

```diff
   const { meta } = message;
+  const sources = message.sources ?? [];
+  const active = sources.find((s) => s.number === openSource) ?? null;
   return (
```

**Edit 11 of 13**

```diff
+        )}
+        {!meta?.fallback && meta?.notice && (
+          <p className="mb-2 flex items-start gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground">
+            <InfoIcon className="mt-px size-3.5 shrink-0" />
+            <span>{meta.notice}</span>
+          </p>
         )}
 
         {message.content ? (
-          <Markdown content={message.content} />
+          <Markdown content={message.content} citations={sources.length} onCite={onCite} />
+        ) : message.pending && searching ? (
+          <Searching label={searching} />
         ) : message.pending && lookingIds?.length ? (
```

**Edit 12 of 13**

```diff
         ) : null}
 
+        {!message.pending && (
+          <SourcesList sources={sources} active={openSource} onOpen={onCite} />
+        )}
+        <SourcePanel source={active} total={sources.length} onClose={() => setOpenSource(null)} />
+
```

**Edit 13 of 13**

```diff
           >
-            <CopyAction text={message.content} />
+            <CopyAction text={sources.length ? stripCitations(message.content) : message.content} />
             <IconAction
```

## web/components/chat/message-list.tsx

**Edit 1 of 2**

```diff
 import { Button } from "@/components/ui/button";
-import type { Conversation } from "@/lib/types";
+import type { ChatMessage, Conversation } from "@/lib/types";
 
+/** What a pending reply is searching, when it uses files or the Library. */
+function searchLabel(messages: ChatMessage[], i: number): string | undefined {
+  const m = messages[i];
+  if (!m.pending || m.content) return undefined;
+  const asked = messages[i - 1];
+  const names = (asked?.collections ?? []).map((c) => c.name);
+  const hasFiles = messages.slice(0, i).some((x) => x.files?.length);
+  if (names.length) return `Searching ${names.join(", ")}${hasFiles ? " and your files" : ""}…`;
+  if (hasFiles) return "Reading your files…";
+  return undefined;
+}
+
```

**Edit 2 of 2**

```diff
               }
+              searching={searchLabel(conversation.messages, i)}
               onRegenerate={onRegenerate}
```

## web/components/chat/app-sidebar.tsx

**Edit 1 of 6**

```diff
   ImageIcon,
+  LibraryIcon,
+  PaperclipIcon,
   CheckIcon,
```

**Edit 2 of 6**

```diff
 } from "lucide-react";
+import Link from "next/link";
 import { useTheme } from "next-themes";
```

**Edit 3 of 6**

```diff
   apiOnline,
+  showLibrary,
 }: {
```

**Edit 4 of 6**

```diff
   apiOnline: boolean;
+  /** Link to the Library pages (when the API has files on). */
+  showLibrary?: boolean;
 }) {
```

**Edit 5 of 6**

```diff
         </div>
+        {showLibrary && (
+          <Button asChild variant="ghost" className="justify-start font-normal">
+            <Link href="/library">
+              <LibraryIcon />
+              Library
+              <span className="ml-auto rounded-full border px-1.5 py-px text-[10px] font-medium text-muted-foreground">
+                Owner
+              </span>
+            </Link>
+          </Button>
+        )}
       </div>
```

**Edit 6 of 6**

```diff
                           aria-label="Voice chat"
                           className="size-3.5 shrink-0 text-muted-foreground"
+                        />
+                      )}
+                      {c.messages.some((m) => m.files?.length || m.collections?.length) && (
+                        <PaperclipIcon
+                          aria-label="Uses files"
+                          className="size-3.5 shrink-0 text-muted-foreground"
```

## web/components/chat/chat-app.tsx

**Edit 1 of 15**

```diff
 import dynamic from "next/dynamic";
-import { CloudIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
+import { CloudIcon, LibraryIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
 import { toast } from "sonner";
```

**Edit 2 of 15**

```diff
 import { AppSidebar } from "@/components/chat/app-sidebar";
-import { Composer } from "@/components/chat/composer";
+import { Composer, type ComposerFiles } from "@/components/chat/composer";
 import { EmptyState, SuggestionGrid } from "@/components/chat/empty-state";
```

**Edit 3 of 15**

```diff
 import { useChat } from "@/hooks/use-chat";
+import { useChatFiles } from "@/hooks/use-chat-files";
+import { useLibraryConfig } from "@/hooks/use-library-config";
 import { useModels } from "@/hooks/use-models";
```

**Edit 4 of 15**

```diff
 import { APP_CONFIG } from "@/lib/config";
-import { DEFAULT_IMAGE_LIMITS, textWithPhotoNote } from "@/lib/images";
-import type { ChatMessage, ModelInfo } from "@/lib/types";
+import { uid } from "@/lib/helpers";
+import { DEFAULT_IMAGE_LIMITS, looksLikeImage, textWithPhotoNote } from "@/lib/images";
+import { deleteChatFile, formatSize } from "@/lib/library";
+import type { ChatMessage, CollectionRef, ModelInfo } from "@/lib/types";
 import { cn } from "@/lib/utils";
```

**Edit 5 of 15**

```diff
   const voiceEnabled = !!voiceSetup.config?.enabled && !noModels;
 
+  // ---- files and the Library ----
+  const library = useLibraryConfig();
+  const fileLimits = library.config?.limits ?? null;
+  const chatFiles = useChatFiles(library.enabled ? fileLimits : null);
+  // Files are uploaded before a new chat exists, under the id it will get.
+  const [draftId, setDraftId] = useState(uid);
+  const [draftCollections, setDraftCollections] = useState<CollectionRef[]>([]);
+  const chatId = chat.active?.id ?? draftId;
+  const collections = chat.active ? (chat.active.collections ?? []) : draftCollections;
+  const selectCollections = (next: CollectionRef[]) =>
+    chat.active ? chat.setCollections(chat.active.id, next) : setDraftCollections(next);
+  const addFiles = (files: File[]) => chatFiles.add(files, chatId);
+  const chatHasFiles = !!chat.active?.messages.some((m) => m.files?.length);
+  const usesLibrary =
+    library.enabled && (collections.length > 0 || chatFiles.items.length > 0 || chatHasFiles);
+
```

**Edit 6 of 15**

```diff
+      )
+    ) : usesLibrary ? (
+      library.config?.engine === "gemini" ? (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files are answered by <b className="font-medium">Gemini File Search</b>{" "}
+          (Google), only from the documents you picked.
+        </>
+      ) : library.config?.engine === "offline" ? (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files use offline test search on this server.
+        </>
+      ) : (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files are answered by <b className="font-medium">{library.config?.label}</b>
+          {library.config?.local ? " on your servers" : ""}, only from the documents you picked.
+        </>
       )
     ) : (
```

**Edit 7 of 15**

```diff
+
+  // Sends text with whatever photos and files are in the trays.
+  const send = (text: string) => {
+    const isNew = !chat.active;
+    chat.send(text, {
+      images: attachments.takeAll(),
+      files: chatFiles.takeReady(),
+      collections,
+      ...(isNew ? { newChatId: draftId } : {}),
+    });
+    if (isNew) {
+      setDraftId(uid());
+      setDraftCollections([]);
+    }
+  };
 
   // A suggestion is sent like typed text, with any photos in the tray.
   const sendSuggestion = (text: string) => {
-    if (blocked || attachments.processing || chat.streaming) return;
-    chat.send(text, attachments.takeAll());
+    if (blocked || attachments.processing || chatFiles.busy || chat.streaming) return;
+    send(text);
   };
```

**Edit 8 of 15**

```diff
   // ---- navigation (ends voice mode first) ----
+  // Files waiting in the composer belong to the chat they were added in.
+  const discardFiles = chatFiles.discard;
   const newChat = useCallback(() => {
     setVoice(null);
+    discardFiles();
     chat.newChat();
     setMobileOpen(false);
-  }, [chat]);
+  }, [chat, discardFiles]);
 
```

**Edit 9 of 15**

```diff
     if (voice && id !== voiceConversation.current) setVoice(null);
+    if (id !== chat.activeId) discardFiles();
     chat.openChat(id);
```

**Edit 10 of 15**

```diff
+
+  // Deleted chats take their files off the server once the undo window closes.
+  const deleteWithUndo = (message: string, ids: string[], undo: () => void) => {
+    let undone = false;
+    const purge = () => {
+      if (!undone) for (const fid of ids) void deleteChatFile(fid);
+    };
+    toast(message, {
+      action: {
+        label: "Undo",
+        onClick: () => {
+          undone = true;
+          undo();
+        },
+      },
+      onAutoClose: purge,
+      onDismiss: purge,
+    });
+  };
+  const fileIds = (ids: string[]) =>
+    chat.conversations
+      .filter((c) => ids.includes(c.id))
+      .flatMap((c) => c.messages.flatMap((m) => (m.files ?? []).map((f) => f.id)));
 
   const deleteChat = (id: string) => {
     if (voice && id === voiceConversation.current) setVoice(null);
-    const undo = chat.deleteChat(id);
-    toast("Chat deleted", { action: { label: "Undo", onClick: undo } });
+    const ids = fileIds([id]);
+    deleteWithUndo("Chat deleted", ids, chat.deleteChat(id));
   };
```

**Edit 11 of 15**

```diff
     setVoice(null);
-    const undo = chat.clearAll();
-    toast("All chats deleted", { action: { label: "Undo", onClick: undo } });
+    const ids = fileIds(chat.conversations.map((c) => c.id));
+    deleteWithUndo("All chats deleted", ids, chat.clearAll());
   };
 
+  // Dropped files: photos go to the photo tray, documents to the file tray.
+  const onDrop = (files: File[]) => {
+    const photos = files.filter(looksLikeImage);
+    const docs = files.filter((f) => !looksLikeImage(f));
+    if (photos.length) attachments.add(photos);
+    if (docs.length) {
+      if (library.enabled) addFiles(docs);
+      else attachments.add(docs); // shows "not a photo"
+    }
+  };
+
+  const composerFiles: ComposerFiles | undefined =
+    library.enabled && fileLimits
+      ? {
+          files: chatFiles,
+          onAdd: addFiles,
+          accept: fileLimits.extensions.join(","),
+          perMessage: fileLimits.chat_files_per_message,
+          maxBytes: fileLimits.chat_file_max_bytes,
+          collections: library.config?.collections ?? [],
+          selected: collections,
+          onSelect: selectCollections,
+        }
+      : undefined;
+
```

**Edit 12 of 15**

```diff
     apiOnline: !models.error,
+    showLibrary: library.enabled,
   };
```

**Edit 13 of 15**

```diff
     <Composer
-      onSend={chat.send}
+      onSend={send}
       onStop={chat.stop}
```

**Edit 14 of 15**

```diff
       attachments={attachments}
+      library={composerFiles}
       photoLimit={limits.per_message}
```

**Edit 15 of 15**

```diff
         enabled={!voice && !noModels}
-        onFiles={attachments.add}
-        limitText={`JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`}
+        onFiles={onDrop}
+        title={library.enabled ? "Drop photos or files to add them" : undefined}
+        limitText={
+          library.enabled && fileLimits
+            ? `Photos up to ${Math.round(limits.max_bytes / 1048576)} MB · files up to ${formatSize(fileLimits.chat_file_max_bytes)}`
+            : `JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`
+        }
       />
```

## README.md

**Edit 1 of 4**

```diff
 Grok, Meta Llama) when no local model is installed or a local model fails.
-An optional **voice mode** (LiveKit) lets users talk to the same assistant.
+An optional **voice mode** (LiveKit) lets users talk to the same assistant, and
+**files and the Library** answer questions from documents with citations
+(Gemini File Search today, a pluggable engine for a self-hosted pipeline next).
 
```

**Edit 2 of 4**

```diff
 ai-app/
-├── api/     FastAPI · Python 3.13 · uv · ruff · pytest · Ollama SDK · Anthropic / OpenAI SDKs · livekit-api
+├── api/     FastAPI · Python 3.13 · uv · ruff · pytest · Ollama SDK · Anthropic / OpenAI / Google GenAI SDKs · livekit-api
 ├── agent/   LiveKit Agents voice worker · Python 3.13 · uv · ruff · pytest   (optional)
```

**Edit 3 of 4**

```diff
+
+## Files and the Library
+
+People can ask about documents in two ways, both from the **+** menu:
+
+- **Add files**: attach a PDF, Word, Excel, PowerPoint, text, CSV, Markdown or
+  code file (up to 10 per message, 25 MB each). It's indexed in a few seconds;
+  later questions in that chat keep searching it. Chat files are deleted 30
+  days after they were last cited, and when the chat is deleted.
+- **Search Library**: pick one or more shared collections. Owners manage them
+  at **/library** (sidebar → Library): Overview, Documents (upload, re-index,
+  move, delete), Collections, a Retrieval test, Storage and Index settings.
+
+Answers come only from the chosen documents, with numbered citations; clicking
+one shows the passage and opens the original. If the documents don't cover the
+question, the answer says so instead of guessing.
+
+```bash
+# api/.env — Gemini File Search (the same key the Gemini chat provider uses)
+GEMINI_API_KEY=...
+# or, to try everything without a key (keyword search, for development and tests):
+RAG_ENGINE=offline
+```
+
+Library owner access: open on your own computer; in production set
+`LIBRARY_TOKEN` (the Library pages ask for it). Without it the Library pages are
+locked in production, while chat files still work. Originals are stored under
+`api/data/library` (a Docker volume in Compose). Questions about files are sent
+to Google when the Gemini engine is used; the line under the input says so.
+
+The search engine sits behind one interface (`api/app/library/engine.py`), so a
+self-hosted pipeline (LangChain/LangGraph with Ollama models and pgvector or
+Qdrant) can replace Gemini File Search without changing the app; documents are
+re-indexed automatically when the engine changes. See `api/README.md`.
 
 ## How model selection works
```

**Edit 4 of 4**

```diff
   add user accounts.
+- Library: set `LIBRARY_TOKEN`. Every collection with documents can be searched
+  (and its cited originals opened) by anyone who can use the chat, so keep
+  confidential documents out until you add sign-in and per-collection access.
+  Chat files are reachable only by their random id. Back up the `library`
+  volume; the index can be rebuilt from it by re-indexing.
 - Voice: anyone who can reach `/api/voice/session` can start a (billed) voice
```

## api/README.md

**Edit 1 of 3**

```diff
 | POST | `/api/voice/chat` | Called by the voice agent; same stream as `/api/chat`, adds the chosen model and earlier chat |
+| GET | `/api/library/config` | Files on/off, limits, allowed types, and the collections chat can search |
+| POST | `/api/files` | Add a file to a chat (multipart `file`, `chat_id`); indexed in the background |
+| GET/DELETE | `/api/files/{id}` | A chat file's status (poll until `indexed`) / delete it |
+| GET | `/api/files/{id}/content` | The original (PDF and plain text inline, everything else as a download) |
+| — | `/api/library/*` | Owner API: overview, collections, documents (upload, re-index, bulk), test, storage, settings |
 
 `POST /api/chat` body:
```

**Edit 2 of 3**

```diff
 data: {}                  data: {"message":"..."}
 ```
 
+To answer from documents, add `rag` to the chat body. The reply streams as
+usual, then a `sources` event carries the text with `[n]` citation markers and
+the passages:
+
+```json
+{ "messages": [...], "rag": { "collections": ["<collection id>"], "files": ["<file id>"], "chat_id": "<chat id>" } }
+```
+
+```
+event: sources
+data: {"cited_text":"Up to 5 days carry over.[1]","grounded":true,"sources":[{"number":1,"title":"Handbook.pdf","text":"...","page":2,"cited":true,"document_id":"...","kind":"library","collection":"HR"}]}
+```
+
+## Files and the Library (RAG)
+
+- **Engine.** `app/library/engine.py` defines `RagEngine`: `ensure_store`,
+  `store_info`, `add_document`, `delete_document`, `purge`, and `stream` (text
+  deltas, then one `Answer` with sources). `gemini.py` implements it with
+  Gemini File Search (`google-genai`); `RAG_ENGINE=offline` uses a local
+  keyword-search stand-in with the same SDK types, for development and tests.
+  A self-hosted engine (LangChain/LangGraph + Ollama + pgvector/Qdrant)
+  implements the same protocol and is chosen in `build_engine`. Documents
+  indexed by a different engine are re-indexed on start.
+- **Isolation.** One index ("store") for the app. Every document carries
+  metadata `scope` (`c:<collection>` or `chat:<chat id>`) and `doc` (its id),
+  and the server builds the filter from ids it has looked up, never from
+  client text. Files must belong to the request's `chat_id`; ids of deleted or
+  expired files are skipped with a note, so an old file never breaks a chat.
+- **Indexing** runs in a background queue (`RAG_INDEX_CONCURRENCY`), resumes
+  after a restart, and removes any copy an interrupted or timed-out upload left
+  in the index (`purge`, matched by `doc` metadata).
+- **Storage.** Originals and a SQLite database live in `LIBRARY_DATA_DIR`
+  (`data/library`). Gemini deletes raw uploads after 48 hours but keeps the
+  index; the originals are what "Open original" and re-indexing use.
+- **Limits.** Library files up to 100 MB (File Search's maximum), chat files
+  25 MB, 10 per message; chat files are kept `CHAT_FILE_RETENTION_DAYS` (30)
+  after they were last cited. Supported: PDF, Word, Excel, PowerPoint, ODT,
+  text, CSV, Markdown, HTML, JSON and common code files. Photos go through
+  Add photos instead.
+- **Owner access.** `LIBRARY_TOKEN` (Bearer) protects `/api/library/*` except
+  `config`. Unset: open in development, locked (403) in production.
+- **Answering.** Gemini answers only from the File Search results and says
+  "I couldn't find that in the documents." otherwise; `RAG_MODEL`,
+  `RAG_TOP_K`, `RAG_CHUNK_TOKENS` and `RAG_CHUNK_OVERLAP` tune it. Searching
+  files always uses the RAG model, and the reply says so if another model was
+  picked.
+
 ## How fallback works
```

**Edit 3 of 3**

```diff
                        /api/voice/* routes); mount_voice(app, brain=...) plugs it in
   voice_brain.py       adapts ChatService to the voice package's Brain contract
+  library/             files + Library: engine protocol, Gemini File Search engine,
+                       offline engine, citations, SQLite records, service, routes;
+                       mount_library(app, ...) plugs it in
+  library_chat.py      turns a chat request with `rag` into the chat event stream
 tests/                 pytest suite with fake providers (no network needed)
```

## web/README.md

**Edit 1 of 6**

```diff
   page.tsx              renders <ChatApp />
+  library/              owner pages: overview, documents, collections, test, storage, settings
   globals.css           Tailwind 4 + shadcn theme tokens (light/dark) + chat typography
```

**Edit 2 of 6**

```diff
     message.tsx         bubbles, actions, model badge, fallback notice
-    markdown.tsx        GFM markdown with copyable code blocks
-    composer.tsx        auto-growing input, + menu (add/take photos), send/stop/voice
+    markdown.tsx        GFM markdown with copyable code blocks and [n] citation buttons
+    composer.tsx        auto-growing input, + menu (photos, Add files, Search Library),
+                        file chips, Library pills, send/stop/voice
     empty-state.tsx     greeting + suggestions
```

**Edit 3 of 6**

```diff
     vision-notice.tsx   "can't see images" / "Auto will answer with …" notice
+  files/
+    file-chip.tsx       file type badge + chip (upload progress, reading, errors)
+    sources.tsx         Sources list and the passage side panel
+  library/              Library owner UI: shell (owner sign-in, nav), overview,
+                        documents (table, drawer, upload, bulk), collections, retrieval
+                        test, storage, settings, confirm dialog
   voice/
```

**Edit 4 of 6**

```diff
   use-models.ts         loads /api/models, remembers the chosen model
-  use-chat.ts           conversations, streaming, stop/regenerate, local persistence
+  use-chat.ts           conversations, streaming, stop/regenerate, local persistence,
+                        files/collections per message and citations
+  use-chat-files.ts     upload chat files with progress, poll until indexed
+  use-library-config.ts /api/library/config: on/off, limits, collections
 lib/
```

**Edit 5 of 6**

```diff
   voice.ts              voice API calls + agent attribute names
+  library.ts            files/Library API calls, owner token (this tab only), helpers
+  library-admin.ts      owner API for the /library pages
   types.ts              shared types (mirror the API schemas)
```

**Edit 6 of 6**

```diff
+
+- `/api/*` is forwarded to the API by a Next.js rewrite. `next.config.ts` raises
+  the rewrite's body limit to 110 MB (Library files are up to 100 MB, sent one
+  per request) and its timeout to 120 s.
 
 - Chat history is stored in the browser (localStorage) and photos in IndexedDB;
```

# Without voice mode

Files: `api/pyproject.toml` (4), `api/.env.example` (1), `api/.gitignore` (1), `api/Dockerfile` (1), `api/app/main.py` (5), `api/app/schemas.py` (1), `api/app/routes/chat.py` (3), `api/tests/conftest.py` (2), `docker-compose.yml` (2), `web/next.config.ts` (1), `web/lib/types.ts` (3), `web/lib/api.ts` (10), `web/hooks/use-chat.ts` (9), `web/components/ui/dropdown-menu.tsx` (2), `web/components/photos/drop-overlay.tsx` (3), `web/components/chat/markdown.tsx` (2), `web/components/chat/composer.tsx` (16), `web/components/chat/message.tsx` (13), `web/components/chat/message-list.tsx` (2), `web/components/chat/app-sidebar.tsx` (6), `web/components/chat/chat-app.tsx` (11), `README.md` (4), `api/README.md` (3), `web/README.md` (6)

## api/pyproject.toml

**Edit 1 of 4**

```diff
     "livekit-api>=1.2.1",
+    "google-genai>=2.26",
 ]
```

**Edit 2 of 4**

```diff
 dev = [
+    "pypdf>=6.19.0",
     "pytest>=9.1",
     "pytest-asyncio>=1.2",
+    "python-docx>=1.2.0",
     "ruff>=0.16",
```

**Edit 3 of 4**

```diff
 "tests/**" = ["PLR2004", "S101"]
+# Lazy imports keep optional engines (and dev-only parsers) out of normal startup.
+"app/library/__init__.py" = ["PLC0415"]
+"app/library/offline.py" = ["PLC0415", "PLW2901"]
+"app/library/citations.py" = ["PLW2901"]
 
```

**Edit 4 of 4**

```diff
 addopts = "-q"
+filterwarnings = [
+    # google-genai subclasses aiohttp.ClientSession; harmless, outside our code.
+    "ignore:Inheritance class AiohttpClientSession:DeprecationWarning",
+]
```

## api/.env.example

**Edit 1 of 1**

```diff
+
+# ---------- Files and the Library (RAG with citations) ----------
+# On when GEMINI_API_KEY (above) is set: files are indexed with Gemini File Search
+# and questions about them are answered by RAG_MODEL with citations.
+# RAG_ENGINE=offline uses a local keyword stand-in instead (testing without a key).
+RAG_ENGINE=
+RAG_MODEL=gemini-3.8-flash
+RAG_EMBEDDING_MODEL=
+RAG_CHUNK_TOKENS=400
+RAG_CHUNK_OVERLAP=40
+RAG_TOP_K=6
+RAG_STORE_NAME=assistant-library
+# Originals and the Library database (keep this folder in backups / a Docker volume).
+LIBRARY_DATA_DIR=data/library
+# Owner access to the Library pages. Required when ENVIRONMENT=production:
+#   python -c "import secrets; print(secrets.token_urlsafe(32))"
+LIBRARY_TOKEN=
+LIBRARY_FILE_MAX_BYTES=104857600
+CHAT_FILE_MAX_BYTES=26214400
+CHAT_FILES_PER_MESSAGE=10
+CHAT_FILE_RETENTION_DAYS=30
 
 # ---------- Photos ----------
```

## api/.gitignore

**Edit 1 of 1**

```diff
 .env
+
+# Library originals and database (LIBRARY_DATA_DIR)
+data/
```

## api/Dockerfile

**Edit 1 of 1**

```diff
 WORKDIR /app
-RUN useradd --create-home --uid 10001 appuser
+RUN useradd --create-home --uid 10001 appuser \
+ && mkdir -p /app/data/library && chown -R appuser /app/data
 COPY --from=build /app /app
```

## api/app/main.py

**Edit 1 of 5**

```diff
 from app.core.logging import configure_logging
+from app.library import LibrarySettings, RagEngine, mount_library
 from app.providers.registry import ProviderRegistry, build_providers
```

**Edit 2 of 5**

```diff
 def create_app(
-    settings: Settings | None = None, registry: ProviderRegistry | None = None
+    settings: Settings | None = None,
+    registry: ProviderRegistry | None = None,
+    library_settings: LibrarySettings | None = None,
+    library_engine: RagEngine | None = None,
 ) -> FastAPI:
```

**Edit 3 of 5**

```diff
         )
-        yield
+        async with library_lifespan(app):
+            yield
         await app.state.registry.aclose()
```

**Edit 4 of 5**

```diff
         allow_origins=settings.cors_origins,
-        allow_methods=["GET", "POST", "OPTIONS"],
+        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
         allow_headers=["*"],
```

**Edit 5 of 5**

```diff
         app.include_router(router, prefix="/api")
+    # Files in chat + the Library (RAG with citations).
+    library_settings = library_settings or LibrarySettings()
+    app.add_middleware(
+        BodySizeLimit,
+        max_bytes=library_settings.chat_file_max_bytes + 1024 * 1024,
+        paths=("/api/files",),
+    )
+    app.add_middleware(
+        BodySizeLimit,
+        max_bytes=library_settings.library_file_max_bytes * 10 + 1024 * 1024,
+        paths=("/api/library/documents",),
+    )
+    library_lifespan = mount_library(
+        app,
+        settings=library_settings,
+        engine=library_engine,
+        production=settings.environment == "production",
+    )
     return app
```

## api/app/schemas.py

**Edit 1 of 1**

```diff
+
+class RagScope(BaseModel):
+    """Answer from documents: Library collections and/or files added to this chat."""
+
+    collections: list[str] = Field(default_factory=list, max_length=20)
+    files: list[str] = Field(default_factory=list, max_length=50)
+    # The chat the files belong to; files from other chats are ignored.
+    chat_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
+
 
 class ChatRequest(BaseModel):
     messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_REQUEST_MESSAGES)
+    rag: RagScope | None = Field(
+        default=None, description="Search these collections/files and answer with citations"
+    )
     provider: str | None = Field(
```

## api/app/routes/chat.py

**Edit 1 of 3**

```diff
 from app.deps import ChatServiceDep, SettingsDep
+from app.library_chat import rag_chat_events
 from app.schemas import ChatRequest
```

**Edit 2 of 3**

```diff
     Events: `meta` (which provider/model answered), unnamed `data: {"delta": ...}`
-    chunks, then `done` or `error`.
+    chunks, then `done` or `error`. With `rag`, the Library answers and a `sources`
+    event (citations, and the text with [n] markers) comes before `done`.
     """
```

**Edit 3 of 3**

```diff
+
+    library = getattr(request.app.state, "library", None)
+    use_library = bool(body.rag and (body.rag.collections or body.rag.files))
+    stream = rag_chat_events(library, body) if use_library and library else service.stream(body)
 
     async def events() -> AsyncIterator[str]:
-        async for event in service.stream(body):
+        async for event in stream:
             if await request.is_disconnected():
```

## api/tests/conftest.py

**Edit 1 of 2**

```diff
 from app.core.config import Settings
+from app.library import LibrarySettings
 from app.main import create_app
```

**Edit 2 of 2**

```diff
 @pytest.fixture
-def make_client(settings: Settings) -> Iterator:
+def library_settings(tmp_path) -> LibrarySettings:
+    """Library off by default in tests; data in a temp folder."""
+    return LibrarySettings(
+        _env_file=None,
+        rag_engine="",
+        gemini_api_key=None,
+        library_token=None,
+        library_data_dir=tmp_path / "library",
+    )
+
+
+@pytest.fixture
+def make_client(settings: Settings, library_settings: LibrarySettings) -> Iterator:
     clients: list[TestClient] = []
 
-    def factory(*providers: Provider, **overrides) -> TestClient:
+    def factory(
+        *providers: Provider,
+        library: LibrarySettings | None = None,
+        library_engine=None,
+        **overrides,
+    ) -> TestClient:
         cfg = settings.model_copy(update=overrides)
         registry = ProviderRegistry(list(providers), cache_ttl=0, vision_patterns=cfg.vision_models)
-        client = TestClient(create_app(cfg, registry))
+        client = TestClient(
+            create_app(
+                cfg,
+                registry,
+                library_settings=library or library_settings,
+                library_engine=library_engine,
+            )
+        )
         client.__enter__()
```

## docker-compose.yml

**Edit 1 of 2**

```diff
       - "host.docker.internal:host-gateway"
+    volumes:
+      # Library and chat files (originals + index records) survive rebuilds
+      - library:/app/data/library
     ports:
       - "8000:8000"
```

**Edit 2 of 2**

```diff
 volumes:
   ollama:
+  library:
```

## web/next.config.ts

**Edit 1 of 1**

```diff
   compress: false,
+  experimental: {
+    // Uploads pass through the /api rewrite, which caps bodies at 10 MB by default.
+    // Library files are up to 100 MB and are sent one per request.
+    proxyClientMaxBodySize: "110mb",
+    // Big uploads and slow first answers need more than the 30 s default.
+    proxyTimeout: 120_000,
+  },
   async rewrites() {
```

## web/lib/types.ts

**Edit 1 of 3**

```diff
+
+/** A file added to a chat. The original and its index live on the API (Library). */
+export interface ChatFile {
+  id: string;
+  name: string;
+  ext: string;
+  size: number;
+}
+
+/** A Library collection searched for a message. */
+export interface CollectionRef {
+  id: string;
+  name: string;
+}
+
+/** A passage an answer was based on; `number` matches the [n] in the text. */
+export interface Citation {
+  number: number;
+  title: string;
+  text: string;
+  page: number | null;
+  cited: boolean;
+  document_id: string | null;
+  kind: "library" | "chat" | null;
+  collection: string | null;
+}
 
 export interface ChatMessage {
```

**Edit 2 of 3**

```diff
   images?: ChatImage[];
+  /** Files added with a user message (searched for this and later questions). */
+  files?: ChatFile[];
+  /** Library collections searched for this user message. */
+  collections?: CollectionRef[];
+  /** Assistant: passages the answer cites ([n] markers in `content`). */
+  sources?: Citation[];
 }
```

**Edit 3 of 3**

```diff
   messages: ChatMessage[];
+  /** Library collections this chat searches (the pill in the composer). */
+  collections?: CollectionRef[];
   createdAt: number;
```

## web/lib/api.ts

**Edit 1 of 10**

```diff
-import type { ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";
+import type { Citation, ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";
 
```

**Edit 2 of 10**

```diff
  */
-const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
+export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
 
```

**Edit 3 of 10**

```diff
 
-async function errorMessage(res: Response): Promise<string> {
+export async function errorMessage(res: Response): Promise<string> {
   try {
```

**Edit 4 of 10**

```diff
+
+export interface RagRequest {
+  collections: string[];
+  files: string[];
+  /** The chat the files belong to; the API ignores other chats' files. */
+  chat_id?: string;
+}
+
+export interface SourcesEvent {
+  cited_text: string;
+  grounded: boolean;
+  sources: Citation[];
+}
 
 export interface StreamChatOptions {
```

**Edit 5 of 10**

```diff
   selection: ModelSelection;
+  /** Search these Library collections / chat files and answer with citations. */
+  rag?: RagRequest | null;
   signal: AbortSignal;
```

**Edit 6 of 10**

```diff
   onDelta: (text: string) => void;
+  onSources?: (sources: SourcesEvent) => void;
 }
```

**Edit 7 of 10**

```diff
   selection,
+  rag,
   signal,
```

**Edit 8 of 10**

```diff
   onDelta,
+  onSources,
 }: StreamChatOptions): Promise<void> {
```

**Edit 9 of 10**

```diff
         model: selection?.model ?? null,
+        ...(rag && (rag.collections.length || rag.files.length) ? { rag } : {}),
       }),
```

**Edit 10 of 10**

```diff
+        break;
+      case "sources":
+        onSources?.(payload as unknown as SourcesEvent);
         break;
       case "error":
```

## web/hooks/use-chat.ts

**Edit 1 of 9**

```diff
 import { blobToBase64, photoLabel, textWithPhotoNote } from "@/lib/images";
-import type { ChatImage, ChatMessage, Conversation, ModelSelection } from "@/lib/types";
+import type {
+  ChatFile,
+  ChatImage,
+  ChatMessage,
+  CollectionRef,
+  Conversation,
+  ModelSelection,
+} from "@/lib/types";
 
```

**Edit 2 of 9**

```diff
 type Updater = (c: Conversation) => Conversation;
 
+/** Every file added anywhere in the chat: later questions still search them. */
+export const filesOf = (messages: ChatMessage[]): ChatFile[] =>
+  messages.flatMap((m) => (m.role === "user" ? (m.files ?? []) : []));
+
+/** What to search for this reply: the collections picked for the last question,
+ *  plus every file in the chat. Empty → an ordinary model reply. */
+function ragFor(history: ChatMessage[], chatId: string) {
+  const lastUser = [...history].reverse().find((m) => m.role === "user");
+  const collections = (lastUser?.collections ?? []).map((c) => c.id);
+  const files = [...new Set(filesOf(history).map((f) => f.id))];
+  return collections.length || files.length ? { collections, files, chat_id: chatId } : null;
+}
+
+export interface SendOptions {
+  images?: ChatImage[];
+  files?: ChatFile[];
+  collections?: CollectionRef[];
+  /** Id for a new chat (files are uploaded under it before the chat exists). */
+  newChatId?: string;
+}
+
```

**Edit 3 of 9**

```diff
           selection: selectionRef.current,
+          rag: ragFor(history, convId),
           signal: ctrl.signal,
```

**Edit 4 of 9**

```diff
             if (!frame) frame = requestAnimationFrame(flush);
           },
+          onSources: (s) => {
+            cancelAnimationFrame(frame);
+            frame = 0;
+            buffer = "";
+            // The final text carries [n] markers that link to these passages.
+            patchMessage(convId, reply.id, { content: s.cited_text, sources: s.sources });
+          },
```

**Edit 5 of 9**

```diff
   const send = useCallback(
-    (text: string, images: ChatImage[] = []) => {
+    (text: string, opts: SendOptions = {}) => {
+      const { images = [], files = [], collections = [] } = opts;
       const content = text.trim();
-      if ((!content && !images.length) || controller.current) return;
+      if ((!content && !images.length && !files.length) || controller.current) return;
       const userMsg: ChatMessage = {
```

**Edit 6 of 9**

```diff
         ...(images.length ? { images } : {}),
+        ...(files.length ? { files } : {}),
+        ...(collections.length ? { collections } : {}),
       };
```

**Edit 7 of 9**

```diff
       }
+      const fallbackTitle = files.length
+        ? files[0].name
+        : images.length > 1
+          ? `${images.length} photos`
+          : "Photo";
       const conv: Conversation = {
-        id: uid(),
-        title: makeTitle(content || (images.length > 1 ? `${images.length} photos` : "Photo")),
+        id: opts.newChatId ?? uid(),
+        title: makeTitle(content || fallbackTitle),
+        ...(collections.length ? { collections } : {}),
         messages: [],
```

**Edit 8 of 9**

```diff
     [activeId, patchMessage],
   );
+
+  /** The collections a chat searches (the Library pill). */
+  const setCollections = useCallback(
+    (id: string, collections: CollectionRef[]) =>
+      update(id, (c) => ({ ...c, collections })),
+    [update],
+  );
```

**Edit 9 of 9**

```diff
     setFeedback,
+    setCollections,
     newChat,
```

## web/components/ui/dropdown-menu.tsx

**Edit 1 of 2**

```diff
+
+function DropdownMenuCheckboxItem({
+  className,
+  children,
+  checked,
+  ...props
+}: React.ComponentProps<typeof DropdownMenuPrimitive.CheckboxItem>) {
+  return (
+    <DropdownMenuPrimitive.CheckboxItem
+      data-slot="dropdown-menu-checkbox-item"
+      className={cn(
+        "relative flex cursor-default items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-sm outline-hidden select-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
+        className,
+      )}
+      checked={checked}
+      {...props}
+    >
+      <span className="pointer-events-none absolute right-2 flex size-3.5 items-center justify-center">
+        <DropdownMenuPrimitive.ItemIndicator>
+          <CheckIcon className="size-4" />
+        </DropdownMenuPrimitive.ItemIndicator>
+      </span>
+      {children}
+    </DropdownMenuPrimitive.CheckboxItem>
+  );
+}
 
 function DropdownMenuLabel({
```

**Edit 2 of 2**

```diff
   DropdownMenuItem,
+  DropdownMenuCheckboxItem,
   DropdownMenuRadioGroup,
```

## web/components/photos/drop-overlay.tsx

**Edit 1 of 3**

```diff
   limitText,
+  title = "Drop photos to add them",
 }: {
```

**Edit 2 of 3**

```diff
   limitText: string;
+  title?: string;
 }) {
```

**Edit 3 of 3**

```diff
         <ImagePlusIcon className="size-8" />
-        <p className="text-base font-semibold">Drop photos to add them</p>
+        <p className="text-base font-semibold">{title}</p>
         <p className="text-sm text-muted-foreground">{limitText}</p>
```

## web/components/chat/markdown.tsx

**Edit 1 of 2**

```diff
 
-import { memo, useState } from "react";
+import { memo, useMemo, useState } from "react";
 import { CheckIcon, CopyIcon } from "lucide-react";
```

**Edit 2 of 2**

```diff
 
-export const Markdown = memo(function Markdown({ content }: { content: string }) {
+/** `[3]` → a link the citation renderer turns into a button (only for real source numbers). */
+function linkCitations(content: string, count: number): string {
+  return content.replace(/\[(\d{1,2})\](?!\()/g, (m, n: string) =>
+    Number(n) >= 1 && Number(n) <= count ? `[${n}](#cite-${n})` : m,
+  );
+}
+
+export const Markdown = memo(function Markdown({
+  content,
+  citations = 0,
+  onCite,
+}: {
+  content: string;
+  /** Number of sources; [n] markers up to this become buttons. */
+  citations?: number;
+  onCite?: (n: number) => void;
+}) {
+  const withCites = useMemo<Components>(
+    () => ({
+      ...components,
+      a: ({ href, children }) => {
+        const m = /^#cite-(\d+)$/.exec(href ?? "");
+        if (m && onCite) {
+          const n = Number(m[1]);
+          return (
+            <button
+              type="button"
+              onClick={() => onCite(n)}
+              aria-label={`Source ${n}`}
+              className="mx-px inline-grid h-[18px] min-w-[18px] translate-y-[-2px] place-items-center rounded-md border bg-muted px-1 align-middle font-mono text-[11px] leading-none text-muted-foreground no-underline hover:bg-foreground hover:text-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
+            >
+              {n}
+            </button>
+          );
+        }
+        return (
+          <a href={href} target="_blank" rel="noopener noreferrer">
+            {children}
+          </a>
+        );
+      },
+    }),
+    [onCite],
+  );
+  const text = citations && onCite ? linkCitations(content, citations) : content;
   return (
     <div className="prose-chat">
-      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
-        {content}
+      <ReactMarkdown remarkPlugins={[remarkGfm]} components={citations ? withCites : components}>
+        {text}
       </ReactMarkdown>
```

## web/components/chat/composer.tsx

**Edit 1 of 16**

```diff
 import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
-import { ArrowUpIcon, CameraIcon, ImageIcon, PlusIcon, SquareIcon } from "lucide-react";
+import {
+  ArrowUpIcon,
+  CameraIcon,
+  ImageIcon,
+  LibraryIcon,
+  PaperclipIcon,
+  PlusIcon,
+  SquareIcon,
+  XIcon,
+} from "lucide-react";
 
+import { FileChip } from "@/components/files/file-chip";
 import { AttachmentTray } from "@/components/photos/attachment-tray";
```

**Edit 2 of 16**

```diff
   DropdownMenu,
+  DropdownMenuCheckboxItem,
   DropdownMenuContent,
   DropdownMenuItem,
+  DropdownMenuSeparator,
+  DropdownMenuSub,
+  DropdownMenuSubContent,
+  DropdownMenuSubTrigger,
   DropdownMenuTrigger,
```

**Edit 3 of 16**

```diff
 import type { UseAttachments } from "@/hooks/use-attachments";
+import type { PendingFile, UseChatFiles } from "@/hooks/use-chat-files";
 import { APP_CONFIG } from "@/lib/config";
 import { ACCEPT_ATTR } from "@/lib/images";
-import type { ChatImage } from "@/lib/types";
+import { formatSize, type CollectionInfo } from "@/lib/library";
+import type { CollectionRef } from "@/lib/types";
 import { cn } from "@/lib/utils";
 
+/** Files and the Library in the composer (only when the API has them on). */
+export interface ComposerFiles {
+  files: UseChatFiles;
+  onAdd: (files: File[]) => void;
+  accept: string;
+  perMessage: number;
+  maxBytes: number;
+  collections: CollectionInfo[];
+  selected: CollectionRef[];
+  onSelect: (collections: CollectionRef[]) => void;
+}
+
+function fileStatus(f: PendingFile): string {
+  switch (f.phase) {
+    case "uploading":
+      return `Uploading · ${Math.round(f.progress * 100)}%`;
+    case "indexing":
+      return "Reading the file…";
+    case "ready":
+      return `${formatSize(f.size)} · Ready`;
+    default:
+      return f.error ?? "Couldn't be added";
+  }
+}
+
```

**Edit 4 of 16**

```diff
   attachments,
+  library,
   photoLimit,
```

**Edit 5 of 16**

```diff
 }: {
-  onSend: (text: string, images: ChatImage[]) => void;
+  /** The parent takes the photos and files from the trays. */
+  onSend: (text: string) => void;
   onStop: () => void;
```

**Edit 6 of 16**

```diff
   attachments?: UseAttachments;
+  library?: ComposerFiles;
   photoLimit?: number;
```

**Edit 7 of 16**

```diff
   const fileInput = useRef<HTMLInputElement>(null);
+  const docInput = useRef<HTMLInputElement>(null);
   const cameraInput = useRef<HTMLInputElement>(null);
```

**Edit 8 of 16**

```diff
   const photoCount = attachments?.items.length ?? 0;
-  const processing = !!attachments?.processing;
-  const hasContent = !!value.trim() || photoCount > 0;
+  const files = library?.files.items ?? [];
+  const readyFiles = files.filter((f) => f.phase === "ready").length;
+  const filesBusy = !!library?.files.busy;
+  const processing = !!attachments?.processing || filesBusy;
+  const hasContent = !!value.trim() || photoCount > 0 || readyFiles > 0;
 
```

**Edit 9 of 16**

```diff
     if (!hasContent || disabled || processing || blocked) return;
-    onSend(value, attachments?.takeAll() ?? []);
+    onSend(value);
     setValue("");
```

**Edit 10 of 16**

```diff
     ? "Stop generating"
-    : processing
-      ? "Waiting for photos to be ready"
-      : "Send message";
+    : filesBusy
+      ? "Waiting for files to be ready"
+      : processing
+        ? "Waiting for photos to be ready"
+        : "Send message";
+  const selected = library?.selected ?? [];
+  const isSelected = (id: string) => selected.some((c) => c.id === id);
+  const toggle = (c: CollectionInfo) =>
+    library?.onSelect(
+      isSelected(c.id)
+        ? selected.filter((x) => x.id !== c.id)
+        : [...selected, { id: c.id, name: c.name }],
+    );
 
```

**Edit 11 of 16**

```diff
     if (e.target.files?.length) attachments?.add([...e.target.files]);
     e.target.value = "";
+  };
+  const onDocs = (e: React.ChangeEvent<HTMLInputElement>) => {
+    if (e.target.files?.length) library?.onAdd([...e.target.files]);
+    e.target.value = "";
```

**Edit 12 of 16**

```diff
       {attachments && <AttachmentTray attachments={attachments} />}
+      {files.length > 0 && (
+        <ul className="mb-2 flex gap-2.5 overflow-x-auto pt-1.5 pb-1" aria-label="Files to send">
+          {files.map((f) => (
+            <li key={f.key}>
+              <FileChip
+                name={f.name}
+                ext={f.ext}
+                sub={fileStatus(f)}
+                progress={f.phase === "uploading" ? f.progress : undefined}
+                tone={f.phase === "failed" ? "error" : "default"}
+                onRemove={() => library?.files.remove(f.key)}
+              />
+            </li>
+          ))}
+        </ul>
+      )}
+      {selected.length > 0 && (
+        <div className="mb-1.5 flex flex-wrap gap-1.5" aria-label="Library collections to search">
+          {selected.map((c) => (
+            <span
+              key={c.id}
+              className="inline-flex h-7 items-center gap-1.5 rounded-full border bg-muted/60 pr-1 pl-2.5 text-xs font-medium"
+            >
+              <LibraryIcon className="size-3.5 text-muted-foreground" />
+              Searching {c.name}
+              <button
+                type="button"
+                aria-label={`Stop searching ${c.name}`}
+                onClick={() => library?.onSelect(selected.filter((x) => x.id !== c.id))}
+                className="grid size-5 place-items-center rounded-full outline-none hover:bg-background focus-visible:ring-2 focus-visible:ring-ring"
+              >
+                <XIcon className="size-3" />
+              </button>
+            </span>
+          ))}
+        </div>
+      )}
       <label htmlFor="composer" className="sr-only">
```

**Edit 13 of 16**

```diff
                       size="icon"
-                      aria-label="Add photos"
+                      aria-label={library ? "Add photos and files" : "Add photos"}
                       disabled={disabled}
```

**Edit 14 of 16**

```diff
                 </TooltipTrigger>
-                <TooltipContent>Add photos</TooltipContent>
+                <TooltipContent>{library ? "Add photos and files" : "Add photos"}</TooltipContent>
               </Tooltip>
               <DropdownMenuContent align="start" side="top" className="w-72">
+                {library && (
+                  <>
+                    <DropdownMenuItem onSelect={() => pick(docInput.current)} className="items-start">
+                      <PaperclipIcon className="mt-0.5" />
+                      <span className="flex flex-col">
+                        <span>Add files</span>
+                        <span className="text-xs text-muted-foreground">
+                          PDF, Word, Excel, text, code · up to {library.perMessage},{" "}
+                          {formatSize(library.maxBytes)} each
+                        </span>
+                      </span>
+                    </DropdownMenuItem>
+                    <DropdownMenuSub>
+                      <DropdownMenuSubTrigger className="items-start">
+                        <LibraryIcon className="mt-0.5" />
+                        <span className="flex flex-col">
+                          <span>Search Library</span>
+                          <span className="text-xs text-muted-foreground">
+                            {library.collections.length
+                              ? "Answer from shared documents"
+                              : "No collections yet"}
+                          </span>
+                        </span>
+                      </DropdownMenuSubTrigger>
+                      <DropdownMenuSubContent className="w-64">
+                        {library.collections.length ? (
+                          library.collections.map((c) => (
+                            <DropdownMenuCheckboxItem
+                              key={c.id}
+                              checked={isSelected(c.id)}
+                              onCheckedChange={() => toggle(c)}
+                              onSelect={(e) => e.preventDefault()}
+                            >
+                              <span className="flex min-w-0 flex-col">
+                                <span className="truncate">{c.name}</span>
+                                <span className="text-xs text-muted-foreground">
+                                  {c.documents} {c.documents === 1 ? "document" : "documents"}
+                                </span>
+                              </span>
+                            </DropdownMenuCheckboxItem>
+                          ))
+                        ) : (
+                          <p className="px-2 py-2 text-xs text-muted-foreground">
+                            Library owners add collections on the Library page.
+                          </p>
+                        )}
+                      </DropdownMenuSubContent>
+                    </DropdownMenuSub>
+                    <DropdownMenuSeparator />
+                  </>
+                )}
                 <DropdownMenuItem onSelect={() => pick(fileInput.current)} className="items-start">
```

**Edit 15 of 16**

```diff
                 <p className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
-                  You can also paste or drop photos.
+                  {library ? "You can also paste photos or drop files." : "You can also paste or drop photos."}
                 </p>
```

**Edit 16 of 16**

```diff
             />
+            {library && (
+              <input
+                ref={docInput}
+                type="file"
+                accept={library.accept}
+                multiple
+                hidden
+                onChange={onDocs}
+                data-testid="file-input"
+              />
+            )}
             {photoCount > 0 && (
```

## web/components/chat/message.tsx

**Edit 1 of 13**

```diff
 
-import { useState } from "react";
+import { useCallback, useState } from "react";
 import {
```

**Edit 2 of 13**

```diff
   CloudIcon,
+  InfoIcon,
+  LibraryIcon,
   RefreshCwIcon,
```

**Edit 3 of 13**

```diff
 import { Markdown } from "@/components/chat/markdown";
+import { FileChip } from "@/components/files/file-chip";
+import { SourcePanel, SourcesList } from "@/components/files/sources";
+import { fileUrl, formatSize } from "@/lib/library";
 import { PhotoGallery } from "@/components/photos/photo-gallery";
```

**Edit 4 of 13**

```diff
+
+/** Waiting for a reply that searches files or the Library. */
+function Searching({ label }: { label: string }) {
+  return (
+    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
+      <LibraryIcon className="size-4" />
+      <span className="animate-pulse">{label}</span>
+    </span>
+  );
+}
+
+const stripCitations = (text: string) => text.replace(/\[\d{1,2}\]/g, "");
 
 export function Message({
```

**Edit 5 of 13**

```diff
   lookingIds,
+  searching,
   onRegenerate,
```

**Edit 6 of 13**

```diff
   lookingIds?: string[];
+  /** "Searching HR Policies…" while a reply that uses files hasn't started. */
+  searching?: string;
   onRegenerate: (id: string) => void;
```

**Edit 7 of 13**

```diff
 }) {
+  const [openSource, setOpenSource] = useState<number | null>(null);
+  const onCite = useCallback((n: number) => setOpenSource(n), []);
+
   if (message.role === "user") {
```

**Edit 8 of 13**

```diff
         {!!message.images?.length && <PhotoGallery images={message.images} />}
+        {!!message.files?.length && (
+          <ul className="flex max-w-[85%] flex-wrap justify-end gap-2" aria-label="Files">
+            {message.files.map((f) => (
+              <li key={f.id}>
+                <FileChip name={f.name} ext={f.ext} sub={formatSize(f.size)} href={fileUrl(f.id)} />
+              </li>
+            ))}
+          </ul>
+        )}
         {message.content && (
```

**Edit 9 of 13**

```diff
         <div className="flex items-center gap-1">
+          {!!message.collections?.length && (
+            <span className="flex items-center gap-1 px-1 text-xs text-muted-foreground">
+              <LibraryIcon className="size-3" />
+              Searching {message.collections.map((c) => c.name).join(", ")}
+            </span>
+          )}
           {!!message.images?.length && !message.content && (
```

**Edit 10 of 13**

```diff
   const { meta } = message;
+  const sources = message.sources ?? [];
+  const active = sources.find((s) => s.number === openSource) ?? null;
   return (
```

**Edit 11 of 13**

```diff
+        )}
+        {!meta?.fallback && meta?.notice && (
+          <p className="mb-2 flex items-start gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground">
+            <InfoIcon className="mt-px size-3.5 shrink-0" />
+            <span>{meta.notice}</span>
+          </p>
         )}
 
         {message.content ? (
-          <Markdown content={message.content} />
+          <Markdown content={message.content} citations={sources.length} onCite={onCite} />
+        ) : message.pending && searching ? (
+          <Searching label={searching} />
         ) : message.pending && lookingIds?.length ? (
```

**Edit 12 of 13**

```diff
         ) : null}
 
+        {!message.pending && (
+          <SourcesList sources={sources} active={openSource} onOpen={onCite} />
+        )}
+        <SourcePanel source={active} total={sources.length} onClose={() => setOpenSource(null)} />
+
```

**Edit 13 of 13**

```diff
           >
-            <CopyAction text={message.content} />
+            <CopyAction text={sources.length ? stripCitations(message.content) : message.content} />
             <IconAction
```

## web/components/chat/message-list.tsx

**Edit 1 of 2**

```diff
 import { Button } from "@/components/ui/button";
-import type { Conversation } from "@/lib/types";
+import type { ChatMessage, Conversation } from "@/lib/types";
 
+/** What a pending reply is searching, when it uses files or the Library. */
+function searchLabel(messages: ChatMessage[], i: number): string | undefined {
+  const m = messages[i];
+  if (!m.pending || m.content) return undefined;
+  const asked = messages[i - 1];
+  const names = (asked?.collections ?? []).map((c) => c.name);
+  const hasFiles = messages.slice(0, i).some((x) => x.files?.length);
+  if (names.length) return `Searching ${names.join(", ")}${hasFiles ? " and your files" : ""}…`;
+  if (hasFiles) return "Reading your files…";
+  return undefined;
+}
+
```

**Edit 2 of 2**

```diff
               }
+              searching={searchLabel(conversation.messages, i)}
               onRegenerate={onRegenerate}
```

## web/components/chat/app-sidebar.tsx

**Edit 1 of 6**

```diff
   ImageIcon,
+  LibraryIcon,
+  PaperclipIcon,
   CheckIcon,
```

**Edit 2 of 6**

```diff
 } from "lucide-react";
+import Link from "next/link";
 import { useTheme } from "next-themes";
```

**Edit 3 of 6**

```diff
   apiOnline,
+  showLibrary,
 }: {
```

**Edit 4 of 6**

```diff
   apiOnline: boolean;
+  /** Link to the Library pages (when the API has files on). */
+  showLibrary?: boolean;
 }) {
```

**Edit 5 of 6**

```diff
         </div>
+        {showLibrary && (
+          <Button asChild variant="ghost" className="justify-start font-normal">
+            <Link href="/library">
+              <LibraryIcon />
+              Library
+              <span className="ml-auto rounded-full border px-1.5 py-px text-[10px] font-medium text-muted-foreground">
+                Owner
+              </span>
+            </Link>
+          </Button>
+        )}
       </div>
```

**Edit 6 of 6**

```diff
                     >
+                      {c.messages.some((m) => m.files?.length || m.collections?.length) && (
+                        <PaperclipIcon
+                          aria-label="Uses files"
+                          className="size-3.5 shrink-0 text-muted-foreground"
+                        />
+                      )}
                       {c.messages.some((m) => m.images?.length) && (
```

## web/components/chat/chat-app.tsx

**Edit 1 of 11**

```diff
 import { useCallback, useEffect, useMemo, useState } from "react";
-import { CloudIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
+import { CloudIcon, LibraryIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
 import { toast } from "sonner";
```

**Edit 2 of 11**

```diff
 import { AppSidebar } from "@/components/chat/app-sidebar";
-import { Composer } from "@/components/chat/composer";
+import { Composer, type ComposerFiles } from "@/components/chat/composer";
 import { EmptyState, SuggestionGrid } from "@/components/chat/empty-state";
```

**Edit 3 of 11**

```diff
 import { useChat } from "@/hooks/use-chat";
+import { useChatFiles } from "@/hooks/use-chat-files";
+import { useLibraryConfig } from "@/hooks/use-library-config";
 import { useModels } from "@/hooks/use-models";
-import { DEFAULT_IMAGE_LIMITS } from "@/lib/images";
-import type { ModelInfo } from "@/lib/types";
+import { uid } from "@/lib/helpers";
+import { DEFAULT_IMAGE_LIMITS, looksLikeImage } from "@/lib/images";
+import { deleteChatFile, formatSize } from "@/lib/library";
+import type { CollectionRef, ModelInfo } from "@/lib/types";
 import { cn } from "@/lib/utils";
```

**Edit 4 of 11**

```diff
   const noModels = !models.loading && !models.effective;
 
+  // ---- files and the Library ----
+  const library = useLibraryConfig();
+  const fileLimits = library.config?.limits ?? null;
+  const chatFiles = useChatFiles(library.enabled ? fileLimits : null);
+  // Files are uploaded before a new chat exists, under the id it will get.
+  const [draftId, setDraftId] = useState(uid);
+  const [draftCollections, setDraftCollections] = useState<CollectionRef[]>([]);
+  const chatId = chat.active?.id ?? draftId;
+  const collections = chat.active ? (chat.active.collections ?? []) : draftCollections;
+  const selectCollections = (next: CollectionRef[]) =>
+    chat.active ? chat.setCollections(chat.active.id, next) : setDraftCollections(next);
+  const addFiles = (files: File[]) => chatFiles.add(files, chatId);
+  const chatHasFiles = !!chat.active?.messages.some((m) => m.files?.length);
+  const usesLibrary =
+    library.enabled && (collections.length > 0 || chatFiles.items.length > 0 || chatHasFiles);
+
```

**Edit 5 of 11**

```diff
+      )
+    ) : usesLibrary ? (
+      library.config?.engine === "gemini" ? (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files are answered by <b className="font-medium">Gemini File Search</b>{" "}
+          (Google), only from the documents you picked.
+        </>
+      ) : library.config?.engine === "offline" ? (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files use offline test search on this server.
+        </>
+      ) : (
+        <>
+          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
+          Questions about files are answered by <b className="font-medium">{library.config?.label}</b>
+          {library.config?.local ? " on your servers" : ""}, only from the documents you picked.
+        </>
       )
     ) : (
```

**Edit 6 of 11**

```diff
+
+  // Sends text with whatever photos and files are in the trays.
+  const send = (text: string) => {
+    const isNew = !chat.active;
+    chat.send(text, {
+      images: attachments.takeAll(),
+      files: chatFiles.takeReady(),
+      collections,
+      ...(isNew ? { newChatId: draftId } : {}),
+    });
+    if (isNew) {
+      setDraftId(uid());
+      setDraftCollections([]);
+    }
+  };
 
   // A suggestion is sent like typed text, with any photos in the tray.
   const sendSuggestion = (text: string) => {
-    if (blocked || attachments.processing || chat.streaming) return;
-    chat.send(text, attachments.takeAll());
+    if (blocked || attachments.processing || chatFiles.busy || chat.streaming) return;
+    send(text);
   };
 
+  // Files waiting in the composer belong to the chat they were added in.
+  const discardFiles = chatFiles.discard;
   const newChat = useCallback(() => {
+    discardFiles();
     chat.newChat();
     setMobileOpen(false);
-  }, [chat]);
+  }, [chat, discardFiles]);
 
   const openChat = (id: string) => {
+    if (id !== chat.activeId) discardFiles();
     chat.openChat(id);
```

**Edit 7 of 11**

```diff
+
+  // Deleted chats take their files off the server once the undo window closes.
+  const deleteWithUndo = (message: string, ids: string[], undo: () => void) => {
+    let undone = false;
+    const purge = () => {
+      if (!undone) for (const fid of ids) void deleteChatFile(fid);
+    };
+    toast(message, {
+      action: {
+        label: "Undo",
+        onClick: () => {
+          undone = true;
+          undo();
+        },
+      },
+      onAutoClose: purge,
+      onDismiss: purge,
+    });
+  };
+  const fileIds = (ids: string[]) =>
+    chat.conversations
+      .filter((c) => ids.includes(c.id))
+      .flatMap((c) => c.messages.flatMap((m) => (m.files ?? []).map((f) => f.id)));
 
   const deleteChat = (id: string) => {
-    const undo = chat.deleteChat(id);
-    toast("Chat deleted", { action: { label: "Undo", onClick: undo } });
+    const ids = fileIds([id]);
+    deleteWithUndo("Chat deleted", ids, chat.deleteChat(id));
   };
```

**Edit 8 of 11**

```diff
   const clearAll = () => {
-    const undo = chat.clearAll();
-    toast("All chats deleted", { action: { label: "Undo", onClick: undo } });
+    const ids = fileIds(chat.conversations.map((c) => c.id));
+    deleteWithUndo("All chats deleted", ids, chat.clearAll());
   };
 
+  // Dropped files: photos go to the photo tray, documents to the file tray.
+  const onDrop = (files: File[]) => {
+    const photos = files.filter(looksLikeImage);
+    const docs = files.filter((f) => !looksLikeImage(f));
+    if (photos.length) attachments.add(photos);
+    if (docs.length) {
+      if (library.enabled) addFiles(docs);
+      else attachments.add(docs); // shows "not a photo"
+    }
+  };
+
+  const composerFiles: ComposerFiles | undefined =
+    library.enabled && fileLimits
+      ? {
+          files: chatFiles,
+          onAdd: addFiles,
+          accept: fileLimits.extensions.join(","),
+          perMessage: fileLimits.chat_files_per_message,
+          maxBytes: fileLimits.chat_file_max_bytes,
+          collections: library.config?.collections ?? [],
+          selected: collections,
+          onSelect: selectCollections,
+        }
+      : undefined;
+
```

**Edit 9 of 11**

```diff
     apiOnline: !models.error,
+    showLibrary: library.enabled,
   };
```

**Edit 10 of 11**

```diff
     <Composer
-      onSend={chat.send}
+      onSend={send}
       onStop={chat.stop}
       attachments={attachments}
+      library={composerFiles}
       photoLimit={limits.per_message}
```

**Edit 11 of 11**

```diff
         enabled={!noModels}
-        onFiles={attachments.add}
-        limitText={`JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`}
+        onFiles={onDrop}
+        title={library.enabled ? "Drop photos or files to add them" : undefined}
+        limitText={
+          library.enabled && fileLimits
+            ? `Photos up to ${Math.round(limits.max_bytes / 1048576)} MB · files up to ${formatSize(fileLimits.chat_file_max_bytes)}`
+            : `JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`
+        }
       />
```

## README.md

**Edit 1 of 4**

```diff
 Grok, Meta Llama) when no local model is installed or a local model fails.
-An optional **voice mode** (LiveKit) lets users talk to the same assistant.
+An optional **voice mode** (LiveKit) lets users talk to the same assistant, and
+**files and the Library** answer questions from documents with citations
+(Gemini File Search today, a pluggable engine for a self-hosted pipeline next).
 
```

**Edit 2 of 4**

```diff
 ai-app/
-├── api/     FastAPI · Python 3.13 · uv · ruff · pytest · Ollama SDK · Anthropic / OpenAI SDKs · livekit-api
+├── api/     FastAPI · Python 3.13 · uv · ruff · pytest · Ollama SDK · Anthropic / OpenAI / Google GenAI SDKs · livekit-api
 ├── agent/   LiveKit Agents voice worker · Python 3.13 · uv · ruff · pytest   (optional)
```

**Edit 3 of 4**

```diff
+
+## Files and the Library
+
+People can ask about documents in two ways, both from the **+** menu:
+
+- **Add files**: attach a PDF, Word, Excel, PowerPoint, text, CSV, Markdown or
+  code file (up to 10 per message, 25 MB each). It's indexed in a few seconds;
+  later questions in that chat keep searching it. Chat files are deleted 30
+  days after they were last cited, and when the chat is deleted.
+- **Search Library**: pick one or more shared collections. Owners manage them
+  at **/library** (sidebar → Library): Overview, Documents (upload, re-index,
+  move, delete), Collections, a Retrieval test, Storage and Index settings.
+
+Answers come only from the chosen documents, with numbered citations; clicking
+one shows the passage and opens the original. If the documents don't cover the
+question, the answer says so instead of guessing.
+
+```bash
+# api/.env — Gemini File Search (the same key the Gemini chat provider uses)
+GEMINI_API_KEY=...
+# or, to try everything without a key (keyword search, for development and tests):
+RAG_ENGINE=offline
+```
+
+Library owner access: open on your own computer; in production set
+`LIBRARY_TOKEN` (the Library pages ask for it). Without it the Library pages are
+locked in production, while chat files still work. Originals are stored under
+`api/data/library` (a Docker volume in Compose). Questions about files are sent
+to Google when the Gemini engine is used; the line under the input says so.
+
+The search engine sits behind one interface (`api/app/library/engine.py`), so a
+self-hosted pipeline (LangChain/LangGraph with Ollama models and pgvector or
+Qdrant) can replace Gemini File Search without changing the app; documents are
+re-indexed automatically when the engine changes. See `api/README.md`.
 
 ## How model selection works
```

**Edit 4 of 4**

```diff
   add user accounts.
+- Library: set `LIBRARY_TOKEN`. Every collection with documents can be searched
+  (and its cited originals opened) by anyone who can use the chat, so keep
+  confidential documents out until you add sign-in and per-collection access.
+  Chat files are reachable only by their random id. Back up the `library`
+  volume; the index can be rebuilt from it by re-indexing.
 - Voice: anyone who can reach `/api/voice/session` can start a (billed) voice
```

## api/README.md

**Edit 1 of 3**

```diff
 | POST | `/api/voice/chat` | Called by the voice agent; same stream as `/api/chat`, adds the chosen model and earlier chat |
+| GET | `/api/library/config` | Files on/off, limits, allowed types, and the collections chat can search |
+| POST | `/api/files` | Add a file to a chat (multipart `file`, `chat_id`); indexed in the background |
+| GET/DELETE | `/api/files/{id}` | A chat file's status (poll until `indexed`) / delete it |
+| GET | `/api/files/{id}/content` | The original (PDF and plain text inline, everything else as a download) |
+| — | `/api/library/*` | Owner API: overview, collections, documents (upload, re-index, bulk), test, storage, settings |
 
 `POST /api/chat` body:
```

**Edit 2 of 3**

```diff
 data: {}                  data: {"message":"..."}
 ```
 
+To answer from documents, add `rag` to the chat body. The reply streams as
+usual, then a `sources` event carries the text with `[n]` citation markers and
+the passages:
+
+```json
+{ "messages": [...], "rag": { "collections": ["<collection id>"], "files": ["<file id>"], "chat_id": "<chat id>" } }
+```
+
+```
+event: sources
+data: {"cited_text":"Up to 5 days carry over.[1]","grounded":true,"sources":[{"number":1,"title":"Handbook.pdf","text":"...","page":2,"cited":true,"document_id":"...","kind":"library","collection":"HR"}]}
+```
+
+## Files and the Library (RAG)
+
+- **Engine.** `app/library/engine.py` defines `RagEngine`: `ensure_store`,
+  `store_info`, `add_document`, `delete_document`, `purge`, and `stream` (text
+  deltas, then one `Answer` with sources). `gemini.py` implements it with
+  Gemini File Search (`google-genai`); `RAG_ENGINE=offline` uses a local
+  keyword-search stand-in with the same SDK types, for development and tests.
+  A self-hosted engine (LangChain/LangGraph + Ollama + pgvector/Qdrant)
+  implements the same protocol and is chosen in `build_engine`. Documents
+  indexed by a different engine are re-indexed on start.
+- **Isolation.** One index ("store") for the app. Every document carries
+  metadata `scope` (`c:<collection>` or `chat:<chat id>`) and `doc` (its id),
+  and the server builds the filter from ids it has looked up, never from
+  client text. Files must belong to the request's `chat_id`; ids of deleted or
+  expired files are skipped with a note, so an old file never breaks a chat.
+- **Indexing** runs in a background queue (`RAG_INDEX_CONCURRENCY`), resumes
+  after a restart, and removes any copy an interrupted or timed-out upload left
+  in the index (`purge`, matched by `doc` metadata).
+- **Storage.** Originals and a SQLite database live in `LIBRARY_DATA_DIR`
+  (`data/library`). Gemini deletes raw uploads after 48 hours but keeps the
+  index; the originals are what "Open original" and re-indexing use.
+- **Limits.** Library files up to 100 MB (File Search's maximum), chat files
+  25 MB, 10 per message; chat files are kept `CHAT_FILE_RETENTION_DAYS` (30)
+  after they were last cited. Supported: PDF, Word, Excel, PowerPoint, ODT,
+  text, CSV, Markdown, HTML, JSON and common code files. Photos go through
+  Add photos instead.
+- **Owner access.** `LIBRARY_TOKEN` (Bearer) protects `/api/library/*` except
+  `config`. Unset: open in development, locked (403) in production.
+- **Answering.** Gemini answers only from the File Search results and says
+  "I couldn't find that in the documents." otherwise; `RAG_MODEL`,
+  `RAG_TOP_K`, `RAG_CHUNK_TOKENS` and `RAG_CHUNK_OVERLAP` tune it. Searching
+  files always uses the RAG model, and the reply says so if another model was
+  picked.
+
 ## How fallback works
```

**Edit 3 of 3**

```diff
                        /api/voice/* routes); mount_voice(app, brain=...) plugs it in
   voice_brain.py       adapts ChatService to the voice package's Brain contract
+  library/             files + Library: engine protocol, Gemini File Search engine,
+                       offline engine, citations, SQLite records, service, routes;
+                       mount_library(app, ...) plugs it in
+  library_chat.py      turns a chat request with `rag` into the chat event stream
 tests/                 pytest suite with fake providers (no network needed)
```

## web/README.md

**Edit 1 of 6**

```diff
   page.tsx              renders <ChatApp />
+  library/              owner pages: overview, documents, collections, test, storage, settings
   globals.css           Tailwind 4 + shadcn theme tokens (light/dark) + chat typography
```

**Edit 2 of 6**

```diff
     message.tsx         bubbles, actions, model badge, fallback notice
-    markdown.tsx        GFM markdown with copyable code blocks
-    composer.tsx        auto-growing input, + menu (add/take photos), send/stop/voice
+    markdown.tsx        GFM markdown with copyable code blocks and [n] citation buttons
+    composer.tsx        auto-growing input, + menu (photos, Add files, Search Library),
+                        file chips, Library pills, send/stop/voice
     empty-state.tsx     greeting + suggestions
```

**Edit 3 of 6**

```diff
     vision-notice.tsx   "can't see images" / "Auto will answer with …" notice
+  files/
+    file-chip.tsx       file type badge + chip (upload progress, reading, errors)
+    sources.tsx         Sources list and the passage side panel
+  library/              Library owner UI: shell (owner sign-in, nav), overview,
+                        documents (table, drawer, upload, bulk), collections, retrieval
+                        test, storage, settings, confirm dialog
   voice/
```

**Edit 4 of 6**

```diff
   use-models.ts         loads /api/models, remembers the chosen model
-  use-chat.ts           conversations, streaming, stop/regenerate, local persistence
+  use-chat.ts           conversations, streaming, stop/regenerate, local persistence,
+                        files/collections per message and citations
+  use-chat-files.ts     upload chat files with progress, poll until indexed
+  use-library-config.ts /api/library/config: on/off, limits, collections
 lib/
```

**Edit 5 of 6**

```diff
   voice.ts              voice API calls + agent attribute names
+  library.ts            files/Library API calls, owner token (this tab only), helpers
+  library-admin.ts      owner API for the /library pages
   types.ts              shared types (mirror the API schemas)
```

**Edit 6 of 6**

```diff
+
+- `/api/*` is forwarded to the API by a Next.js rewrite. `next.config.ts` raises
+  the rewrite's body limit to 110 MB (Library files are up to 100 MB, sent one
+  per request) and its timeout to 120 s.
 
 - Chat history is stored in the browser (localStorage) and photos in IndexedDB;
```
