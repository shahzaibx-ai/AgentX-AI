"use client";

import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  ArrowUpIcon,
  AudioLinesIcon,
  CameraIcon,
  ImageIcon,
  LibraryIcon,
  MicIcon,
  PaperclipIcon,
  PlusIcon,
  SquareIcon,
  XIcon,
  CheckIcon,
  LoaderCircleIcon,
} from "lucide-react";
import { toast } from "sonner";

import { AttachmentTray } from "@/components/photos/attachment-tray";
import { FileChip } from "@/components/files/file-chip";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { UseAttachments } from "@/hooks/use-attachments";
import type { PendingFile, UseChatFiles } from "@/hooks/use-chat-files";
import { APP_CONFIG } from "@/lib/config";
import { ACCEPT_ATTR } from "@/lib/images";
import { formatSize, type CollectionInfo } from "@/lib/library";
import type { CollectionRef, ChatImage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useRecorder } from "@/hooks/use-recorder";

/** Files and the Library in the composer (only when the API has them on). */
export interface ComposerFiles {
  files: UseChatFiles;
  onAdd: (files: File[]) => void;
  accept: string;
  perMessage: number;
  maxBytes: number;
  collections: CollectionInfo[];
  selected: CollectionRef[];
  onSelect: (collections: CollectionRef[]) => void;
}

function fileStatus(f: PendingFile): string {
  switch (f.phase) {
    case "uploading":
      return `Uploading · ${Math.round(f.progress * 100)}%`;
    case "indexing":
      return "Reading the file…";
    case "ready":
      return `${formatSize(f.size)} · Ready`;
    default:
      return f.error ?? "Couldn't be added";
  }
}

export const Composer = forwardRef(({
  onSend,
  onStop,
  attachments,
  library,
  photoLimit,
  notice,
  blocked,
  streaming,
  disabled,
  placeholder = `Message ${APP_CONFIG.appName}…`,
  autoFocus,
}: {
  /** The parent takes the photos and files from the trays. */
  onSend: (text: string) => void;
  onStop: () => void;
  attachments?: UseAttachments;
  library?: ComposerFiles;
  photoLimit?: number;
  notice?: ReactNode;
  blocked?: boolean;
  streaming: boolean;
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}, ref: any) => {
  const [value, setValue] = useState("");
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [coarse, setCoarse] = useState(false);
  const { state: recState, levels, seconds, start, stop, cancel } = useRecorder();
  const dictationBaseRef = useRef<string>("");
  const cancelRef = useRef(cancel);

  useEffect(() => {
    cancelRef.current = cancel;
  }, [cancel]);

  useEffect(() => {
    return () => {
      cancelRef.current();
    };
  }, []);

  const handleToggleMic = async () => {
    if (recState === "idle") {
      dictationBaseRef.current = value;
      start();
    } else {
      const text = await stop();
      if (text) {
        setValue((prev) => {
          const base = dictationBaseRef.current;
          return base && text ? `${base} ${text}` : base || text;
        });
        internalRef.current?.focus();
      }
    }
  };

  const photoCount = attachments?.items.length ?? 0;
  const files = library?.files.items ?? [];
  const readyFiles = files.filter((f) => f.phase === "ready").length;
  const filesBusy = !!library?.files.busy;
  const processing = !!attachments?.processing || filesBusy;
  const hasContent = !!value.trim() || photoCount > 0 || readyFiles > 0;

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (streaming) return onStop();
    if (recState !== "idle") {
      cancelRef.current();
    }
    if (!hasContent || disabled || processing || blocked) return;
    onSend(value);
    setValue("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const touch = window.matchMedia("(hover: none)").matches;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !touch) {
      e.preventDefault();
      submit();
    }
  };

  const canSend = streaming || (hasContent && !disabled && !processing && !blocked);
  const sendLabel = streaming
    ? "Stop generating"
    : filesBusy
      ? "Waiting for files to be ready"
      : processing
        ? "Waiting for photos to be ready"
        : "Send message";
  const selected = library?.selected ?? [];
  const isSelected = (id: string) => selected.some((c) => c.id === id);
  const toggle = (c: CollectionInfo) =>
    library?.onSelect(
      isSelected(c.id)
        ? selected.filter((x) => x.id !== c.id)
        : [...selected, { id: c.id, name: c.name }],
    );

  const voiceDisabled = disabled || streaming || blocked;

  const pick = (input: HTMLInputElement | null) => {
    requestAnimationFrame(() => input?.click());
  };
  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) attachments?.add([...e.target.files]);
    e.target.value = "";
  };
  const onDocs = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) library?.onAdd([...e.target.files]);
    e.target.value = "";
  };

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <form
      onSubmit={submit}
      className="mx-auto w-full max-w-3xl rounded-3xl border bg-card p-2.5 pl-4 shadow-sm transition-colors focus-within:border-ring"
    >
      {notice}
      {attachments && <AttachmentTray attachments={attachments} />}
      {files.length > 0 && (
        <ul className="mb-2 flex gap-2.5 overflow-x-auto pt-1.5 pb-1" aria-label="Files to send">
          {files.map((f) => (
            <li key={f.key}>
              <FileChip
                name={f.name}
                ext={f.ext}
                sub={fileStatus(f)}
                progress={f.phase === "uploading" ? f.progress : undefined}
                tone={f.phase === "failed" ? "error" : "default"}
                onRemove={() => library?.files.remove(f.key)}
              />
            </li>
          ))}
        </ul>
      )}
      {selected.length > 0 && (
        <div className="mb-1.5 flex flex-wrap gap-1.5" aria-label="Library collections to search">
          {selected.map((c) => (
            <span
              key={c.id}
              className="inline-flex h-7 items-center gap-1.5 rounded-full border bg-muted/60 pr-1 pl-2.5 text-xs font-medium"
            >
              <LibraryIcon className="size-3.5 text-muted-foreground" />
              Searching {c.name}
              <button
                type="button"
                aria-label={`Stop searching ${c.name}`}
                onClick={() => library?.onSelect(selected.filter((x) => x.id !== c.id))}
                className="grid size-5 place-items-center rounded-full outline-none hover:bg-background focus-visible:ring-2 focus-visible:ring-ring"
              >
                <XIcon className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <label htmlFor="composer" className="sr-only">
        Message
      </label>

      {recState === "idle" ? (
        <textarea
          id="composer"
          ref={internalRef}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          enterKeyHint="send"
          className="field-sizing-content max-h-52 min-h-7 w-full resize-none bg-transparent py-1.5 text-[15px] leading-6 outline-none placeholder:text-muted-foreground"
        />
      ) : (
        <div className="flex items-center gap-3 py-2 px-1">
          <Button type="button" variant="ghost" size="icon" className="size-8 rounded-full" onClick={cancel}>
            <XIcon className="size-4" />
          </Button>
          <div className="flex-1 flex items-center gap-1 h-6">
            {recState === "recording" ? (
              <div className="flex items-center gap-[2px] h-full">
                {levels.map((l, i) => (
                  <div
                    key={i}
                    className="w-[3px] rounded-full bg-foreground transition-[height] duration-75"
                    style={{ height: `${4 + l * 24}px` }}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoaderCircleIcon className="size-4 animate-spin" />
                <span>Transcribing…</span>
              </div>
            )}
          </div>
          <div className="text-xs tabular-nums text-muted-foreground w-10 text-right">
            {formatTime(seconds)}
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 rounded-full"
            onClick={handleToggleMic}
            disabled={recState === "transcribing"}
          >
            <CheckIcon className="size-4" />
          </Button>
        </div>
      )}

      <div className="mt-1 flex items-center gap-2">
        {attachments && (
          <>
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={library ? "Add photos and files" : "Add photos"}
                      disabled={disabled}
                      className="-ml-2 rounded-full text-muted-foreground hover:text-foreground"
                    >
                      <PlusIcon />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>{library ? "Add photos and files" : "Add photos"}</TooltipContent>
              </Tooltip>
              <DropdownMenuContent align="start" side="top" className="w-72">
                {library && (
                  <>
                    <DropdownMenuItem onSelect={() => pick(docInput.current)} className="items-start">
                      <PaperclipIcon className="mt-0.5" />
                      <span className="flex flex-col">
                        <span>Add files</span>
                        <span className="text-xs text-muted-foreground">
                          PDF, Word, Excel, text, code · up to {library.perMessage},{" "}
                          {formatSize(library.maxBytes)} each
                        </span>
                      </span>
                    </DropdownMenuItem>
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger className="items-start">
                        <LibraryIcon className="mt-0.5" />
                        <span className="flex flex-col">
                          <span>Search Library</span>
                          <span className="text-xs text-muted-foreground">
                            {library.collections.length
                              ? "Answer from shared documents"
                              : "No collections yet"}
                          </span>
                        </span>
                      </DropdownMenuSubTrigger>
                      <DropdownMenuSubContent className="w-64">
                        {library.collections.length ? (
                          library.collections.map((c) => (
                            <DropdownMenuCheckboxItem
                              key={c.id}
                              checked={isSelected(c.id)}
                              onCheckedChange={() => toggle(c)}
                              onSelect={(e) => e.preventDefault()}
                            >
                              <span className="flex min-w-0 flex-col">
                                <span className="truncate">{c.name}</span>
                                <span className="text-xs text-muted-foreground">
                                  {c.documents} {c.documents === 1 ? "document" : "documents"}
                                </span>
                              </span>
                            </DropdownMenuCheckboxItem>
                          ))
                        ) : (
                          <p className="px-2 py-2 text-xs text-muted-foreground">
                            Library owners add collections on the Library page.
                          </p>
                        )}
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                    <DropdownMenuSeparator />
                  </>
                )}
                 <DropdownMenuItem onSelect={() => pick(fileInput.current)} className="items-start">
                  <ImageIcon className="mt-0.5" />
                  <span className="flex flex-col">
                    <span>Add photos</span>
                    <span className="text-xs text-muted-foreground">
                      JPEG, PNG, WebP or GIF · up to {photoLimit ?? 5}
                    </span>
                  </span>
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => pick(cameraInput.current)} className="items-start">
                  <CameraIcon className="mt-0.5" />
                  <span className="flex flex-col">
                    <span>Take a photo</span>
                    <span className="text-xs text-muted-foreground">Saves photos to your library</span>
                  </span>
                </DropdownMenuItem>
                <p className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
                  {library ? "You can also paste photos or drop files." : "You can also paste or drop photos."}
                </p>
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT_ATTR}
              multiple
              hidden
              onChange={onFiles}
              data-testid="photo-input"
            />
            {library && (
              <input
                ref={docInput}
                type="file"
                accept={library.accept}
                multiple
                hidden
                onChange={onDocs}
                data-testid="file-input"
              />
            )}
            <input
              ref={cameraInput}
              type="file"
              accept="image/*"
              capture="environment"
              hidden
              onChange={onFiles}
            />
            {photoCount > 0 && (
              <span className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
                {photoCount} of {photoLimit ?? 5} photos
              </span>
            )}
          </>
        )}
        <div className="flex-1" />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Voice prompt"
              disabled={voiceDisabled}
              onClick={handleToggleMic}
              className={cn("rounded-full transition-colors", recState === "recording" && "text-destructive bg-destructive/10")}
            >
              {recState === "recording" ? <MicIcon className="size-4 animate-pulse" /> : <MicIcon className="size-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{recState === "recording" ? "Stop dictation" : "Voice prompt"}</TooltipContent>
        </Tooltip>
        <Button
          type="submit"
          size="icon"
          disabled={!canSend}
          aria-label={sendLabel}
          className={cn("rounded-full", !canSend && "opacity-30")}
        >
          {streaming ? <SquareIcon className="size-3.5 fill-current" /> : <ArrowUpIcon />}
        </Button>
      </div>
    </form>
  );
});
