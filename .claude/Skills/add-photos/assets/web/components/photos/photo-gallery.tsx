"use client";

import { useState } from "react";
import { ImageOffIcon } from "lucide-react";

import { PhotoViewer } from "@/components/photos/photo-viewer";
import { useImageUrl } from "@/hooks/use-image-url";
import type { ChatImage } from "@/lib/types";
import { cn } from "@/lib/utils";

function Tile({ image, single, onOpen }: { image: ChatImage; single: boolean; onOpen: () => void }) {
  const url = useImageUrl(image.id);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`View ${image.name}`}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-muted outline-none focus-visible:ring-2 focus-visible:ring-ring",
        single ? "max-h-80 max-w-full" : "aspect-square w-full",
      )}
      style={single ? { aspectRatio: `${image.width} / ${image.height}`, width: Math.min(320, image.width) } : undefined}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element -- local object URL
        <img src={url} alt={image.name} className="size-full object-cover" draggable={false} />
      ) : url === null ? (
        <span className="absolute inset-0 grid place-items-center text-muted-foreground" title="Photo no longer stored in this browser">
          <ImageOffIcon className="size-5" />
        </span>
      ) : null}
    </button>
  );
}

/** Photos in a sent message; click to open the viewer. */
export function PhotoGallery({ images }: { images: ChatImage[] }) {
  const [open, setOpen] = useState<number | null>(null);
  const single = images.length === 1;
  return (
    <>
      <div
        className={cn(
          "grid max-w-[85%] gap-1.5",
          single ? "grid-cols-1 justify-items-end" : images.length === 2 || images.length === 4 ? "w-72 grid-cols-2" : "w-80 grid-cols-3",
        )}
      >
        {images.map((img, i) => (
          <Tile key={img.id} image={img} single={single} onOpen={() => setOpen(i)} />
        ))}
      </div>
      <PhotoViewer photos={images} index={open} onClose={() => setOpen(null)} />
    </>
  );
}
