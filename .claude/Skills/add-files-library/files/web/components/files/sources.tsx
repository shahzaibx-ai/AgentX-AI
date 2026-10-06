"use client";

import { BookOpenIcon, ExternalLinkIcon, LibraryIcon, PaperclipIcon } from "lucide-react";

import { TypeBadge } from "@/components/files/file-chip";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { extOf, fileUrl } from "@/lib/library";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

const where = (c: Citation) => (c.page ? `Page ${c.page}` : null);

/** The numbered passages an answer is based on. */
export function SourcesList({
  sources,
  active,
  onOpen,
}: {
  sources: Citation[];
  active?: number | null;
  onOpen: (number: number) => void;
}) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 overflow-hidden rounded-2xl border">
      <p className="flex items-center gap-1.5 border-b px-3 py-2 text-xs font-medium text-muted-foreground">
        <BookOpenIcon className="size-3.5" />
        Sources
      </p>
      <ul>
        {sources.map((s) => (
          <li key={s.number} className="border-t first:border-t-0">
            <button
              type="button"
              onClick={() => onOpen(s.number)}
              aria-pressed={active === s.number}
              className={cn(
                "flex w-full items-center gap-2.5 px-3 py-2 text-left text-[13px] outline-none hover:bg-muted focus-visible:bg-muted",
                active === s.number && "bg-muted",
              )}
            >
              <span className="w-4 shrink-0 font-mono text-[11px] text-muted-foreground">{s.number}</span>
              <TypeBadge ext={extOf(s.title)} small />
              <span className="flex min-w-0 flex-1 flex-col leading-snug">
                <span className="truncate font-medium">{s.title}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {[where(s), s.text.replace(/\s+/g, " ")].filter(Boolean).join(" · ")}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Side panel with the passage an answer cited. */
export function SourcePanel({
  source,
  total,
  onClose,
}: {
  source: Citation | null;
  total: number;
  onClose: () => void;
}) {
  return (
    <Sheet open={!!source} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
        {source && (
          <>
            <div className="flex items-start gap-3 border-b p-4 pr-12">
              <TypeBadge ext={extOf(source.title)} />
              <div className="min-w-0">
                <SheetTitle className="text-[15px] break-words">{source.title}</SheetTitle>
                <SheetDescription className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs">
                  {source.kind === "chat" ? (
                    <span className="inline-flex items-center gap-1">
                      <PaperclipIcon className="size-3" /> File in this chat
                    </span>
                  ) : source.collection ? (
                    <span className="inline-flex items-center gap-1">
                      <LibraryIcon className="size-3" /> {source.collection}
                    </span>
                  ) : null}
                  {where(source) && <span>· {where(source)}</span>}
                  <span>
                    · source {source.number} of {total}
                  </span>
                </SheetDescription>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <p className="mb-1.5 font-mono text-[11px] text-muted-foreground uppercase">
                {where(source) ?? "Passage"}
              </p>
              <blockquote className="rounded-xl border bg-muted/40 p-4 text-sm leading-6 whitespace-pre-wrap">
                {source.text}
              </blockquote>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                {source.cited
                  ? "The answer used this passage. Check the original for the full context."
                  : "This passage was found by the search; the answer didn't link it to a sentence."}
              </p>
            </div>
            {source.document_id && (
              <div className="flex gap-2 border-t p-3">
                <Button asChild variant="outline" size="sm">
                  <a href={fileUrl(source.document_id)} target="_blank" rel="noopener noreferrer">
                    <ExternalLinkIcon />
                    Open original
                  </a>
                </Button>
              </div>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
