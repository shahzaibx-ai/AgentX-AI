"use client";

import { XIcon } from "lucide-react";

import { formatSize, typeLabel } from "@/lib/library";
import { cn } from "@/lib/utils";

export function TypeBadge({ ext, small }: { ext: string; small?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative grid shrink-0 place-items-center rounded-md border bg-muted font-mono font-semibold tracking-wide text-muted-foreground",
        small ? "h-7 w-6 text-[7px]" : "h-10 w-8 text-[8.5px]",
      )}
    >
      {typeLabel(ext)}
    </span>
  );
}

/** One file: name, a status line, optional progress and remove button. */
export function FileChip({
  name,
  ext,
  sub,
  progress,
  tone = "default",
  onRemove,
  removeLabel,
  href,
}: {
  name: string;
  ext: string;
  sub: string;
  /** 0..1 shows a bar; undefined hides it. */
  progress?: number;
  tone?: "default" | "error";
  onRemove?: () => void;
  removeLabel?: string;
  href?: string;
}) {
  const body = (
    <>
      <TypeBadge ext={ext} />
      <span className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="truncate text-[13px] font-medium">{name}</span>
        <span
          className={cn(
            "truncate text-xs",
            tone === "error" ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {sub}
        </span>
        {progress !== undefined && (
          <span className="mt-1.5 h-[3px] overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-foreground transition-[width] duration-200"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </span>
        )}
      </span>
    </>
  );
  return (
    <div
      className={cn(
        "group/chip relative flex w-56 shrink-0 items-center gap-2.5 rounded-2xl border bg-card py-2 pr-2.5 pl-2 text-left",
        tone === "error" && "border-destructive/40 bg-destructive/5",
      )}
      title={`${name}${sub ? ` · ${sub}` : ""}`}
    >
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className="flex min-w-0 flex-1 items-center gap-2.5 outline-none focus-visible:underline">
          {body}
        </a>
      ) : (
        body
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={removeLabel ?? `Remove ${name}`}
          className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full border bg-background shadow-sm outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          <XIcon className="size-3" />
        </button>
      )}
    </div>
  );
}

export const fileSize = formatSize;
