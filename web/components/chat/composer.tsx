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
import { ArrowUpIcon, CameraIcon, ImageIcon, MicIcon, PlusIcon, SquareIcon, XIcon, CheckIcon, LoaderCircleIcon } from "lucide-react";
import { toast } from "sonner";

import { AttachmentTray } from "@/components/photos/attachment-tray";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { UseAttachments } from "@/hooks/use-attachments";
import { APP_CONFIG } from "@/lib/config";
import { ACCEPT_ATTR } from "@/lib/images";
import type { ChatImage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useRecorder } from "@/hooks/use-recorder";

export const Composer = forwardRef(({
  onSend,
  onStop,
  attachments,
  photoLimit,
  notice,
  blocked,
  streaming,
  disabled,
  placeholder = `Message ${APP_CONFIG.appName}…`,
  autoFocus,
}: {
  onSend: (text: string, images: ChatImage[]) => void;
  onStop: () => void;
  attachments?: UseAttachments;
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
  const processing = !!attachments?.processing;
  const hasContent = !!value.trim() || photoCount > 0;

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (streaming) return onStop();
    if (recState !== "idle") {
      cancelRef.current();
    }
    if (!hasContent || disabled || processing || blocked) return;
    onSend(value, attachments?.takeAll() ?? []);
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
    : processing
      ? "Waiting for photos to be ready"
      : "Send message";

  const voiceDisabled = disabled || streaming || blocked;

  const pick = (input: HTMLInputElement | null) => {
    requestAnimationFrame(() => input?.click());
  };
  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) attachments?.add([...e.target.files]);
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
                      aria-label="Add photos"
                      disabled={disabled}
                      className="-ml-2 rounded-full text-muted-foreground hover:text-foreground"
                    >
                      <PlusIcon />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>Add photos</TooltipContent>
              </Tooltip>
              <DropdownMenuContent align="start" side="top" className="w-72">
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
                  You can also paste or drop photos.
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
