"use client";

import { useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon, ImageOffIcon, XIcon } from "lucide-react";
import { Dialog } from "radix-ui";

import { Button } from "@/components/ui/button";
import { useImageUrl } from "@/hooks/use-image-url";
import { formatSize } from "@/lib/images";
import type { ChatImage } from "@/lib/types";

/** A photo to show: stored ones load by id; a tray photo passes its preview URL. */
export type ViewerPhoto = ChatImage & { url?: string };

function ViewerImage({ photo }: { photo: ViewerPhoto }) {
  const stored = useImageUrl(photo.id);
  const url = photo.url ?? stored;
  if (url === null) {
    return (
      <div className="flex flex-col items-center gap-2 text-sm text-white/70">
        <ImageOffIcon className="size-8" />
        This photo is no longer stored in this browser.
      </div>
    );
  }
  if (!url) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- local object URL
    <img
      src={url}
      alt={photo.name}
      className="max-h-full max-w-full rounded-md object-contain shadow-2xl select-none"
      draggable={false}
    />
  );
}

export function PhotoViewer({
  photos,
  index,
  onClose,
}: {
  photos: ViewerPhoto[];
  /** Which photo is open; null when closed. */
  index: number | null;
  onClose: () => void;
}) {
  const [i, setI] = useState(index ?? 0);
  // Follow a newly opened photo in the same render (no frame of the old one).
  const [openedAt, setOpenedAt] = useState(index);
  if (index !== openedAt) {
    setOpenedAt(index);
    if (index !== null) setI(index);
  }

  const open = index !== null && photos.length > 0;
  const shown = Math.max(0, Math.min(i, photos.length - 1));
  const current = photos[shown];
  const prev = () => setI((n) => Math.max(0, n - 1));
  const next = () => setI((n) => Math.min(photos.length - 1, n + 1));

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/95 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed inset-0 z-50 flex flex-col text-white outline-none"
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") prev();
            if (e.key === "ArrowRight") next();
          }}
        >
          {current && (
            <>
              <div className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <Dialog.Title className="truncate text-sm font-medium">{current.name}</Dialog.Title>
                  <Dialog.Description className="text-xs text-white/60">
                    {current.width}×{current.height} · {formatSize(current.size)}
                    {current.resizedFrom && ` · resized from ${current.resizedFrom}`}
                  </Dialog.Description>
                </div>
                {photos.length > 1 && (
                  <span className="text-xs text-white/60 tabular-nums">
                    {shown + 1} of {photos.length}
                  </span>
                )}
                <Dialog.Close asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Close"
                    className="text-white hover:bg-white/10 hover:text-white"
                  >
                    <XIcon />
                  </Button>
                </Dialog.Close>
              </div>
              <div
                className="relative flex min-h-0 flex-1 items-center justify-center px-4 pb-6 sm:px-16"
                onClick={(e) => e.target === e.currentTarget && onClose()}
              >
                <ViewerImage key={current.id} photo={current} />
                {photos.length > 1 && (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Previous photo"
                      disabled={shown === 0}
                      onClick={prev}
                      className="absolute top-1/2 left-2 -translate-y-1/2 rounded-full bg-white/10 text-white hover:bg-white/20 hover:text-white disabled:opacity-30"
                    >
                      <ChevronLeftIcon />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Next photo"
                      disabled={shown === photos.length - 1}
                      onClick={next}
                      className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full bg-white/10 text-white hover:bg-white/20 hover:text-white disabled:opacity-30"
                    >
                      <ChevronRightIcon />
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
