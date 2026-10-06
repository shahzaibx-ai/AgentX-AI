"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CloudIcon, LibraryIcon, LockIcon, PanelLeftIcon, SquarePenIcon } from "lucide-react";
import { toast } from "sonner";
import dynamic from "next/dynamic";

import { AppSidebar } from "@/components/chat/app-sidebar";
import { Composer, type ComposerFiles } from "@/components/chat/composer";
import { EmptyState, SuggestionGrid } from "@/components/chat/empty-state";
import { MessageList } from "@/components/chat/message-list";
import { ModelPicker } from "@/components/chat/model-picker";
import { PhotoDropZone } from "@/components/photos/drop-overlay";
import { VisionNotice } from "@/components/photos/vision-notice";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAttachments } from "@/hooks/use-attachments";
import { useChat } from "@/hooks/use-chat";
import { useChatFiles } from "@/hooks/use-chat-files";
import { useLibraryConfig } from "@/hooks/use-library-config";
import { useModels } from "@/hooks/use-models";
import { uid } from "@/lib/helpers";
import { DEFAULT_IMAGE_LIMITS, looksLikeImage } from "@/lib/images";
import { deleteChatFile, formatSize } from "@/lib/library";
import { APP_CONFIG } from "@/lib/config";
import type { CollectionRef, ModelInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

const Code = ({ children }: { children: React.ReactNode }) => (
  <code className="rounded bg-background/70 px-1 font-mono text-[12px]">{children}</code>
);

const VoiceSession = dynamic(
  () => import("@/components/voice/voice-session").then((m) => m.VoiceSession),
  { ssr: false },
);

export function ChatApp() {
  const models = useModels();
  const limits = models.data?.image_limits ?? DEFAULT_IMAGE_LIMITS;
  const attachments = useAttachments(limits);
  const composerRef = useRef<{ quote: (text: string) => void }>(null);

  // ---- photos: which model will look at them ----
  const chosen: ModelInfo | null = models.selection ? models.effective : null; // null = Auto
  const visionDefault = models.data?.default_vision ?? null;
  const canSee = chosen ? !!chosen.vision : !!visionDefault;
  const imagePolicy = useMemo(
    // Before the model list loads, send photos and let the API decide.
    () => ({
      send: models.data ? canSee : true,
      perRequest: limits.per_request,
      perMessage: limits.per_message,
      maxBytes: limits.max_bytes,
    }),
    [models.data, canSee, limits.per_request, limits.per_message, limits.max_bytes],
  );
  const chat = useChat(models.selection, imagePolicy);
  const [sidebarOpen, setSidebarOpen] = useState(true); // desktop
  const [mobileOpen, setMobileOpen] = useState(false); // mobile sheet
  const [voiceOpen, setVoiceOpen] = useState(false); // voice mode active

  const empty = !chat.active || chat.active.messages.length === 0;
  const noModels = !models.loading && !models.effective;

  // ---- files and the Library ----
  const library = useLibraryConfig();
  const fileLimits = library.config?.limits ?? null;
  const chatFiles = useChatFiles(library.enabled ? fileLimits : null);
  // Files are uploaded before a new chat exists, under the id it will get.
  const [draftId, setDraftId] = useState(uid);
  const [draftCollections, setDraftCollections] = useState<CollectionRef[]>([]);
  const chatId = chat.active?.id ?? draftId;
  const collections = chat.active ? (chat.active.collections ?? []) : draftCollections;
  const selectCollections = (next: CollectionRef[]) =>
    chat.active ? chat.setCollections(chat.active.id, next) : setDraftCollections(next);
  const addFiles = (files: File[]) => chatFiles.add(files, chatId);
  const chatHasFiles = !!chat.active?.messages.some((m) => m.files?.length);
  const usesLibrary =
    library.enabled && (collections.length > 0 || chatFiles.items.length > 0 || chatHasFiles);

  const pendingPhotos = attachments.items.length > 0;
  const chatHasPhotos = !!chat.active?.messages.some((m) => m.images?.length);
  const providerLabel = (id: string) => models.data?.providers.find((p) => p.id === id)?.label ?? id;
  const cloudCanSee = !!models.data?.providers.some(
    (p) => !p.local && p.available && p.models.some((m) => m.vision),
  );

  const switchToVision = useCallback(() => {
    if (!visionDefault) return;
    models.select({ provider: visionDefault.provider, model: visionDefault.id });
    toast(`Switched to ${visionDefault.name}. It can see images.`);
  }, [models, visionDefault]);

  const switchAction = visionDefault
    ? { label: `Use ${visionDefault.name}`, onClick: switchToVision }
    : undefined;
  const pullHint = (
    <>
      Run <Code>ollama pull gemma3</Code> or add a cloud API key, then refresh the model list.
    </>
  );

  let notice: React.ReactNode = null;
  let blocked = false;
  if (pendingPhotos && models.data) {
    if (chosen && !chosen.vision) {
      blocked = true;
      notice = (
        <VisionNotice tone="warning" action={switchAction}>
          <b className="font-medium">{chosen.name}</b> can&apos;t see images.{" "}
          {visionDefault ? "Switch to a model that can, or remove the photos." : pullHint}
        </VisionNotice>
      );
    } else if (!chosen && !visionDefault) {
      blocked = true;
      notice = (
        <VisionNotice tone="warning">
          No model that can see images is available. {pullHint}
        </VisionNotice>
      );
    } else if (!chosen && visionDefault) {
      notice = (
        <VisionNotice tone="info">
          Auto will answer with <b className="font-medium">{visionDefault.name}</b>,{" "}
          {visionDefault.local ? "a local model" : `a ${providerLabel(visionDefault.provider)} model`}{" "}
          that can see images.
        </VisionNotice>
      );
    }
  } else if (chatHasPhotos && chosen && !chosen.vision) {
    notice = (
      <VisionNotice tone="info" action={switchAction}>
        <b className="font-medium">{chosen.name}</b> can&apos;t see images, so it only gets a note that
        this chat has photos.
      </VisionNotice>
    );
  }

  const handleQuote = useCallback((text: string) => {
    composerRef.current?.quote(text);
  }, []);

  // Where photos go: shown while photos are attached, and in a chat that has
  // photos, since earlier photos are sent again with each message.
  const photoTarget = chosen?.vision ? chosen : !chosen ? visionDefault : null;
  const disclaimer =
    (pendingPhotos || chatHasPhotos) && photoTarget ? (
      photoTarget.local ? (
        <>
          <LockIcon className="mr-1 inline size-3 align-[-1px]" />
          Photos stay on this computer: <b className="font-medium">{photoTarget.name}</b> runs
          locally.{cloudCanSee && " If it fails, a cloud model may answer instead."}
        </>
      ) : (
        <>
          <CloudIcon className="mr-1 inline size-3 align-[-1px]" />
          Photos are sent to <b className="font-medium">{providerLabel(photoTarget.provider)}</b> to
          answer.
        </>
      )
    ) : usesLibrary ? (
      library.config?.engine === "gemini" ? (
        <>
          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
          Questions about files are answered by <b className="font-medium">Gemini File Search</b>{" "}
          (Google), only from the documents you picked.
        </>
      ) : library.config?.engine === "offline" ? (
        <>
          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
          Questions about files use offline test search on this server.
        </>
      ) : (
        <>
          <LibraryIcon className="mr-1 inline size-3 align-[-1px]" />
          Questions about files are answered by <b className="font-medium">{library.config?.label}</b>
          {library.config?.local ? " on your servers" : ""}, only from the documents you picked.
        </>
      )
    ) : (
      "AI can make mistakes. Check important information."
    );

  // Sends text with whatever photos and files are in the trays.
  const send = (text: string) => {
    const isNew = !chat.active;
    chat.send(text, {
      images: attachments.takeAll(),
      files: chatFiles.takeReady(),
      collections,
      ...(isNew ? { newChatId: draftId } : {}),
    });
    if (isNew) {
      setDraftId(uid());
      setDraftCollections([]);
    }
  };

  // A suggestion is sent like typed text, with any photos in the tray.
  const sendSuggestion = (text: string) => {
    if (blocked || attachments.processing || chatFiles.busy || chat.streaming) return;
    send(text);
  };

  // Files waiting in the composer belong to the chat they were added in.
  const discardFiles = chatFiles.discard;
  const newChat = useCallback(() => {
    discardFiles();
    chat.newChat();
    setMobileOpen(false);
  }, [chat, discardFiles]);

  const openChat = (id: string) => {
    if (id !== chat.activeId) discardFiles();
    chat.openChat(id);
    setMobileOpen(false);
  };

  // Deleted chats take their files off the server once the undo window closes.
  const deleteWithUndo = (message: string, ids: string[], undo: () => void) => {
    let undone = false;
    const purge = () => {
      if (!undone) for (const fid of ids) void deleteChatFile(fid);
    };
    toast(message, {
      action: {
        label: "Undo",
        onClick: () => {
          undone = true;
          undo();
        },
      },
      onAutoClose: purge,
      onDismiss: purge,
    });
  };
  const fileIds = (ids: string[]) =>
    chat.conversations
      .filter((c) => ids.includes(c.id))
      .flatMap((c) => c.messages.flatMap((m) => (m.files ?? []).map((f) => f.id)));

  const deleteChat = (id: string) => {
    const ids = fileIds([id]);
    deleteWithUndo("Chat deleted", ids, chat.deleteChat(id));
  };

  const clearAll = () => {
    const ids = fileIds(chat.conversations.map((c) => c.id));
    deleteWithUndo("All chats deleted", ids, chat.clearAll());
  };

  // Dropped files: photos go to the photo tray, documents to the file tray.
  const onDrop = (files: File[]) => {
    const photos = files.filter(looksLikeImage);
    const docs = files.filter((f) => !looksLikeImage(f));
    if (photos.length) attachments.add(photos);
    if (docs.length) {
      if (library.enabled) addFiles(docs);
      else attachments.add(docs); // shows "not a photo"
    }
  };

  const composerFiles: ComposerFiles | undefined =
    library.enabled && fileLimits
      ? {
          files: chatFiles,
          onAdd: addFiles,
          accept: fileLimits.extensions.join(","),
          perMessage: fileLimits.chat_files_per_message,
          maxBytes: fileLimits.chat_file_max_bytes,
          collections: library.config?.collections ?? [],
          selected: collections,
          onSelect: selectCollections,
        }
      : undefined;

  const toggleVoice = useCallback(() => {
    setVoiceOpen((prev) => !prev);
  }, []);

  // Global shortcuts: new chat, search, stop.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        newChat();
      } else if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSidebarOpen(true);
        setMobileOpen(true);
        requestAnimationFrame(() => document.getElementById("chat-search")?.focus());
      } else if (e.key === "Escape" && chat.streaming) {
        chat.stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chat, newChat]);

  const sidebarProps = {
    conversations: chat.conversations,
    activeId: chat.activeId,
    onNewChat: newChat,
    onOpen: openChat,
    onDelete: deleteChat,
    onClearAll: clearAll,
    apiOnline: !models.error,
    showLibrary: library.enabled,
    onVoiceToggle: toggleVoice,
    voiceEnabled: voiceOpen,
  };

  const composer = (
    <Composer
      ref={composerRef}
      onSend={send}
      onStop={chat.stop}
      attachments={attachments}
      library={composerFiles}
      photoLimit={limits.per_message}
      notice={notice}
      blocked={blocked}
      streaming={chat.streaming}
      disabled={noModels}
      autoFocus
      placeholder={noModels ? "No AI model available — see the model menu" : undefined}
    />
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden shrink-0 border-r transition-[margin] duration-200 md:block md:w-72",
          !sidebarOpen && "md:-ml-72",
        )}
        aria-hidden={!sidebarOpen}
        inert={!sidebarOpen}
      >
        <AppSidebar {...sidebarProps} onCollapse={() => setSidebarOpen(false)} />
      </aside>

      {/* Mobile sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" showClose={false} className="w-72 p-0 md:hidden">
          <SheetTitle className="sr-only">Conversations</SheetTitle>
          <SheetDescription className="sr-only">Your chat history</SheetDescription>
          <AppSidebar {...sidebarProps} onCollapse={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        {voiceOpen ? (
          <VoiceSession
            selection={models.selection}
            participantName={APP_CONFIG.user.name}
            history={chat.active?.messages ?? []}
            voices={[]}
            voice={null}
            captions={true}
            onPrefsChange={() => {}}
            onTranscripts={(transcripts) => {
              // We will implement the transcript saving logic in the next step
            }}
            onEnd={() => setVoiceOpen(false)}
            onRetry={() => {}}
            onClose={() => setVoiceOpen(false)}
          />
        ) : (
          <>
            <header className="flex h-14 shrink-0 items-center gap-1 px-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Open sidebar"
                    className={cn(sidebarOpen && "md:hidden")}
                    onClick={() => {
                      setSidebarOpen(true);
                      setMobileOpen(true);
                    }}
                  >
                    <PanelLeftIcon />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Open sidebar</TooltipContent>
              </Tooltip>
              <ModelPicker models={models} forPhotos={pendingPhotos || chatHasPhotos} />
              <div className="flex-1" />
              {!empty && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="New chat"
                      className={cn(sidebarOpen && "md:hidden")}
                      onClick={newChat}
                    >
                      <SquarePenIcon />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>New chat</TooltipContent>
                </Tooltip>
              )}
            </header>

            {empty ? (
              <div className="flex flex-1 flex-col justify-center overflow-y-auto px-3 pb-[8vh] sm:px-6">
                <EmptyState />
                {composer}
                <SuggestionGrid onPick={sendSuggestion} />
              </div>
            ) : (
              <>
                <MessageList
                  conversation={chat.active!}
                  streaming={chat.streaming}
                  onRegenerate={chat.regenerate}
                  onFeedback={chat.setFeedback}
                  onQuote={handleQuote}
                />
                <div className="shrink-0 px-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] sm:px-6">
                  {composer}
                </div>
              </>
            )}
            <p className="shrink-0 px-4 pb-2 text-center text-xs text-muted-foreground" aria-live="polite">
              {disclaimer}
            </p>
          </>
        )}
      </main>
      <PhotoDropZone
        enabled={!noModels}
        onFiles={onDrop}
        title={library.enabled ? "Drop photos or files to add them" : undefined}
        limitText={
          library.enabled && fileLimits
            ? `Photos up to ${Math.round(limits.max_bytes / 1048576)} MB · files up to ${formatSize(fileLimits.chat_file_max_bytes)}`
            : `JPEG, PNG, WebP or GIF · up to ${limits.per_message} photos, ${Math.round(limits.max_bytes / 1048576)} MB each`
        }
      />
    </div>
  );
}
