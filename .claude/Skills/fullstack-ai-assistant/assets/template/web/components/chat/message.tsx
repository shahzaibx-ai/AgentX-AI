"use client";

import { useState } from "react";
import {
  CheckIcon,
  CopyIcon,
  HardDriveIcon,
  CloudIcon,
  RefreshCwIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  TriangleAlertIcon,
} from "lucide-react";

import { Markdown } from "@/components/chat/markdown";
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

export function Message({
  message,
  isLast,
  onRegenerate,
  onFeedback,
}: {
  message: ChatMessage;
  isLast: boolean;
  onRegenerate: (id: string) => void;
  onFeedback: (id: string, value: "up" | "down") => void;
}) {
  if (message.role === "user") {
    return (
      <div className="group flex flex-col items-end gap-1">
        <div className="max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap">
          {message.content}
        </div>
        <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
          <CopyAction text={message.content} />
        </div>
      </div>
    );
  }

  const { meta } = message;
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

        {message.content ? (
          <Markdown content={message.content} />
        ) : message.pending ? (
          <Typing />
        ) : null}

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
            <CopyAction text={message.content} />
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
