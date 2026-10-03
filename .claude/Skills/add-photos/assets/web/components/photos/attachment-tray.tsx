"use client";

import { useState } from "react";
import { FileXIcon, TriangleAlertIcon, XIcon } from "lucide-react";

import { PhotoViewer, type ViewerPhoto } from "@/components/photos/photo-viewer";
import type { UseAttachments } from "@/hooks/use-attachments";

function Spinner() {
  return (
    <span className="absolute inset-0 grid place-items-center bg-background/60" role="status" aria-label="Preparing photo">
      <svg viewBox="0 0 30 30" className="size-7 animate-spin">
        <circle cx="15" cy="15" r="12" fill="none" strokeWidth="3" className="stroke-foreground/15" />
        <circle
          cx="15"
          cy="15"
          r="12"
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="75.4"
          strokeDashoffset="52"
          className="stroke-foreground"
        />
      </svg>
    </span>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full border bg-background text-foreground shadow-sm outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
    >
      <XIcon className="size-3" />
    </button>
  );
}

/** Photos waiting to be sent, and files that couldn't be added. */
export function AttachmentTray({ attachments }: { attachments: UseAttachments }) {
  const { items, problems, remove, dismiss } = attachments;
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length && !problems.length) return null;

  const viewable: ViewerPhoto[] = items.flatMap((a) =>
    a.image && a.previewUrl ? [{ ...a.image, url: a.previewUrl }] : [],
  );

  return (
    <div className="mb-2">
      <ul className="flex flex-wrap gap-2.5 pt-1.5" aria-label="Photos to send">
        {items.map((a) => {
          const title = a.image
            ? `${a.name} · ${a.image.width}×${a.image.height}${a.image.resizedFrom ? ` (resized from ${a.image.resizedFrom})` : ""}`
            : a.name;
          return (
            <li key={a.id} className="relative size-16" title={title}>
              <button
                type="button"
                disabled={!a.image}
                onClick={() => setOpen(viewable.findIndex((v) => v.id === a.id))}
                aria-label={`View ${a.name}`}
                className="size-full overflow-hidden rounded-xl border bg-muted outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {a.previewUrl && (
                  // eslint-disable-next-line @next/next/no-img-element -- local object URL
                  <img src={a.previewUrl} alt="" className="size-full object-cover" draggable={false} />
                )}
              </button>
              {!a.image && <Spinner />}
              {a.image?.resizedFrom && (
                <span className="pointer-events-none absolute bottom-1 left-1 rounded bg-black/60 px-1 text-[10px] leading-4 font-medium text-white">
                  {Math.max(a.image.width, a.image.height)}px
                </span>
              )}
              <RemoveButton label={`Remove ${a.name}`} onClick={() => remove(a.id)} />
            </li>
          );
        })}
        {problems.map((p) => (
          <li
            key={p.id}
            className="relative flex size-16 flex-col items-center justify-center gap-1 rounded-xl border border-destructive/40 bg-destructive/5 px-1 text-destructive"
            title={`${p.name}: ${p.reason}`}
          >
            <FileXIcon className="size-4" />
            <span className="w-full truncate text-center text-[10px] leading-3">{p.name}</span>
            <RemoveButton label={`Dismiss ${p.name}`} onClick={() => dismiss(p.id)} />
          </li>
        ))}
      </ul>
      {problems.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {problems.map((p) => (
            <p key={p.id} role="alert" className="flex items-start gap-1.5 text-xs leading-5 text-destructive">
              <TriangleAlertIcon className="mt-0.5 size-3.5 shrink-0" />
              <span>
                <b className="font-medium">{p.name}</b> · {p.reason}
              </span>
            </p>
          ))}
        </div>
      )}
      <PhotoViewer photos={viewable} index={open !== null && open >= 0 ? open : null} onClose={() => setOpen(null)} />
    </div>
  );
}
