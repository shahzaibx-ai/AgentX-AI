"use client";

import { useCallback, useState } from "react";
import {
  CheckIcon,
  CopyIcon,
  HardDriveIcon,
  CloudIcon,
  InfoIcon,
  LibraryIcon,
  RefreshCwIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  TriangleAlertIcon,
  QuoteIcon,
} from "lucide-react";

import { Markdown } from "@/components/chat/markdown";
import { FileChip } from "@/components/files/file-chip";
import { SourcePanel, SourcesList } from "@/components/files/sources";
import { fileUrl, formatSize } from "@/lib/library";
import { PhotoGallery } from "@/components/photos/photo-gallery";
import { useImageUrl } from "@/hooks/use-image-url";
import { photoLabel } from "@/lib/images";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

function IconAction({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={label}
          aria-pressed={active}
          onClick={onClick}
          className={cn("text-muted-foreground hover:text-foreground", active && "text-foreground")}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function CopyAction({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <IconAction
      label={copied ? "Copied" : "Copy"}
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </IconAction>
  );
}

function Typing() {
  return (
    <span className="inline-flex gap-1 py-2" aria-label="Assistant is typing">
      {[0, 150, 300].map((d) => (
        <i
          key={d}
          className="size-1.5 rounded-full bg-muted-foreground"
          style={{ animation: `blink 1.2s ${d}ms infinite ease-in-out` }}
        />
      ))}
    </span>
  );
}

function MiniThumb({ id }: { id: string }) {
  const url = useImageUrl(id);
  return (
    <span className="-ml-1.5 size-6 overflow-hidden rounded-md border-2 border-background bg-muted first:ml-0">
      {/* eslint-disable-next-line @next/next/no-img-element -- local object URL */}
      {url && <img src={url} alt="" className="size-full object-cover" />}
    </span>
  );
}

/** Waiting for a reply to a message with photos. */
function Looking({ ids }: { ids: string[] }) {
  return (
    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
      <span className="flex">
        {ids.slice(0, 3).map((id) => (
          <MiniThumb key={id} id={id} />
        ))}
      </span>
      <span className="animate-pulse">Looking at {ids.length > 1 ? `${ids.length} photos` : "the photo"}…</span>
    </span>
  );
}

/** Waiting for a reply that searches files or the Library. */
function Searching({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 py-1 text-sm text-muted-foreground" role="status">
      <LibraryIcon className="size-4" />
      <span className="animate-pulse">{label}</span>
    </span>
  );
}

const stripCitations = (text: string) => text.replace(/\[\d{1,2}\]/g, "");

export function Message({
  message,
  isLast,
  lookingIds,
  searching,
  onRegenerate,
  onFeedback,
  onQuote,
}: {
  message: ChatMessage;
  isLast: boolean;
  /** Photos in the message being answered, while the reply hasn't started. */
  lookingIds?: string[];
  /** "Searching HR Policies…" while a reply that uses files hasn't started. */
  searching?: string;
  onRegenerate: (id: string) => void;
  onFeedback: (id: string, value: "up" | "down") => void;
  onQuote: (text: string) => void;
}) {
  const [openSource, setOpenSource] = useState<number | null>(null);
  const onCite = useCallback((n: number) => setOpenSource(n), []);

  if (message.role === "user") {
    return (
      <div className="group flex flex-col items-end gap-1">
        {!!message.images?.length && <PhotoGallery images={message.images} />}
        {!!message.files?.length && (
          <ul className="flex max-w-[85%] flex-wrap justify-end gap-2" aria-label="Files">
            {message.files.map((f) => (
              <li key={f.id}>
                <FileChip name={f.name} ext={f.ext} sub={formatSize(f.size)} href={fileUrl(f.id)} />
              </li>
            ))}
          </ul>
        )}
        {message.content && (
          <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
            {message.content}
          </div>
        )}
        <div className="flex items-center gap-1">
          {!!message.collections?.length && (
            <span className="flex items-center gap-1 px-1 text-xs text-muted-foreground">
              <LibraryIcon className="size-3" />
              Searching {message.collections.map((c) => c.name).join(", ")}
            </span>
          )}
          {!!message.images?.length && !message.content && (
            <span className="px-1 text-xs text-muted-foreground">
              Sent {photoLabel(message.images.length)}
            </span>
          )}
          {message.content && (
            <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
              <CopyAction text={message.content} />
              <IconAction
                label="Quote message"
                onClick={() => onQuote(message.content)}
              >
                <QuoteIcon />
              </IconAction>
            </div>
          )}
        </div>
      </div>
    );
  }

  const { meta } = message;
  const sources = message.sources ?? [];
  const active = sources.find((s) => s.number === openSource) ?? null;
  return (
    <div className="group flex gap-4">
      <div className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg border bg-background">
        <span className="size-2.5 rounded-sm bg-foreground" />
      </div>
      <div className="min-w-0 flex-1">
        {meta?.fallback && meta.notice && (
          <p className="mb-2 flex items-start gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground">
            <TriangleAlertIcon className="mt-px size-3.5 shrink-0" />
            <span>
              Switched to {meta.provider_label} because the selected model was unavailable (
              {meta.notice}).
            </span>
          </p>
        )}
        {!meta?.fallback && meta?.notice && (
          <p className="mb-2 flex items-start gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-xs text-muted-foreground">
            <InfoIcon className="mt-px size-3.5 shrink-0" />
            <span>{meta.notice}</span>
          </p>
        )}

        {message.content ? (
          <Markdown content={message.content} citations={sources.length} onCite={onCite} />
        ) : message.pending && searching ? (
          <Searching label={searching} />
        ) : message.pending && lookingIds?.length ? (
          <Looking ids={lookingIds} />
        ) : message.pending ? (
          <Typing />
        ) : null}

        {!message.pending && (
          <SourcesList sources={sources} active={openSource} onOpen={onCite} />
        )}
        <SourcePanel source={active} total={sources.length} onClose={() => setOpenSource(null)} />

        {message.error && (
          <div className="mt-2 flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <span className="flex-1">{message.error}</span>
            <Button size="sm" variant="outline" onClick={() => onRegenerate(message.id)}>
              <RefreshCwIcon />
              Try again
            </Button>
          </div>
        )}

        {!message.pending && !message.error && (
          <div
            className={cn(
              "mt-1.5 flex items-center gap-0.5 transition-opacity [@media(hover:none)]:opacity-100",
              isLast ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-within:opacity-100",
            )}
          >
            <CopyAction text={sources.length ? stripCitations(message.content) : message.content} />
            <IconAction
              label="Quote message"
              onClick={() => onQuote(message.content)}
            >
              <QuoteIcon />
            </IconAction>
            <IconAction
              label="Good response"
              active={message.feedback === "up"}
              onClick={() => onFeedback(message.id, "up")}
            >
              <ThumbsUpIcon />
            </IconAction>
            <IconAction
              label="Bad response"
              active={message.feedback === "down"}
              onClick={() => onFeedback(message.id, "down")}
            >
              <ThumbsDownIcon />
            </IconAction>
            {isLast && (
              <IconAction label="Regenerate" onClick={() => onRegenerate(message.id)}>
                <RefreshCwIcon />
              </IconAction>
            )}
            {meta && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                {meta.local ? (
                  <HardDriveIcon className="size-3" />
                ) : (
                  <CloudIcon className="size-3" />
                )}
                {meta.model}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
