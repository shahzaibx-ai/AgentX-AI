import type { ChatMessage, ImageLimits } from "@/lib/types";

/** Used until /api/models says otherwise (these match the API defaults). */
export const DEFAULT_IMAGE_LIMITS: ImageLimits = {
  per_message: 5,
  per_request: 20,
  max_bytes: 10 * 1024 * 1024,
};

/** Photos are scaled down so the long edge is at most this. Vision models downscale anyway. */
export const MAX_EDGE = 2048;

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"] as const;
export const ACCEPT_ATTR = ACCEPTED_TYPES.join(",");

export const HEIC_MESSAGE =
  "HEIC photos aren't supported yet. On iPhone, share it as JPEG (or set Camera → Formats → Most Compatible).";
export const TYPE_MESSAGE = "Only JPEG, PNG, WebP and GIF photos can be added.";
export const UNREADABLE_MESSAGE = "This file couldn't be read as an image.";

export function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

const limitLabel = (bytes: number) => `${Math.round(bytes / (1024 * 1024))} MB`;

export const tooLargeMessage = (size: number, limit: number) =>
  `${formatSize(size)} is over the ${limitLabel(limit)} limit. Export a smaller copy.`;

export const tooManyMessage = (limit: number) =>
  `Up to ${limit} photo${limit === 1 ? "" : "s"} per message.`;

export function isHeic(file: File): boolean {
  return /hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name);
}

/** Files worth trying from a paste or drop (other files are ignored silently). */
export function looksLikeImage(file: File): boolean {
  return file.type.startsWith("image/") || isHeic(file);
}

/** A reason the file can't be added before reading it, or null. */
export function precheck(file: File, limits: ImageLimits): string | null {
  if (isHeic(file)) return HEIC_MESSAGE;
  if (!(ACCEPTED_TYPES as readonly string[]).includes(file.type)) return TYPE_MESSAGE;
  if (file.size > limits.max_bytes) return tooLargeMessage(file.size, limits.max_bytes);
  return null;
}

/**
 * What is sent stays under 5 MB (Anthropic's per-image limit) even when the
 * API allows larger files. A 2048 px photo is usually well under 1 MB.
 */
export const SEND_MAX_BYTES = 5 * 1024 * 1024;

export interface PreparedImage {
  blob: Blob;
  mediaType: "image/jpeg" | "image/png";
  width: number;
  height: number;
  resizedFrom?: string;
}

function decode(file: Blob): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.decoding = "async";
  img.src = url;
  return img
    .decode()
    .then(() => img)
    .finally(() => URL.revokeObjectURL(url));
}

function encode(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(UNREADABLE_MESSAGE))), type, quality),
  );
}

/**
 * Redraws the photo so the long edge is at most MAX_EDGE, as PNG (for PNG
 * screenshots) or JPEG (everything else). Redrawing also applies the camera's
 * rotation, drops metadata such as GPS location, and turns WebP/GIF into
 * formats every provider accepts (a GIF keeps its first frame). Throws a
 * user-facing message when the photo can't be used.
 */
export async function prepareImage(file: File, limits: ImageLimits): Promise<PreparedImage> {
  let img: HTMLImageElement;
  try {
    img = await decode(file);
  } catch {
    throw new Error(UNREADABLE_MESSAGE);
  }
  const width = img.naturalWidth;
  const height = img.naturalHeight;
  if (!width || !height) throw new Error(UNREADABLE_MESSAGE);

  const scale = Math.min(1, MAX_EDGE / Math.max(width, height));
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error(UNREADABLE_MESSAGE);

  const draw = (background: boolean) => {
    ctx.clearRect(0, 0, w, h);
    if (background) {
      // JPEG has no transparency; use white rather than black behind it.
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
    }
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, 0, 0, w, h);
  };

  const cap = Math.min(limits.max_bytes, SEND_MAX_BYTES);
  let mediaType: PreparedImage["mediaType"] = file.type === "image/png" ? "image/png" : "image/jpeg";
  draw(mediaType === "image/jpeg");
  let blob = await encode(canvas, mediaType, mediaType === "image/jpeg" ? 0.9 : undefined);
  if (blob.size > cap && mediaType === "image/png") {
    mediaType = "image/jpeg";
    draw(true);
    blob = await encode(canvas, mediaType, 0.9);
  }
  for (const quality of [0.8, 0.7]) {
    if (blob.size <= cap) break;
    blob = await encode(canvas, mediaType, quality);
  }
  if (blob.size > cap) throw new Error(tooLargeMessage(blob.size, cap));

  return {
    blob,
    mediaType,
    width: w,
    height: h,
    ...(scale < 1 ? { resizedFrom: `${width}×${height}` } : {}),
  };
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Couldn't read the photo."));
    reader.readAsDataURL(blob);
  });
}

export function photoLabel(count: number): string {
  return count === 1 ? "a photo" : `${count} photos`;
}

/** The message as plain text, noting its photos (for text-only models and voice). */
export function textWithPhotoNote(message: Pick<ChatMessage, "content" | "images">): string {
  const n = message.images?.length ?? 0;
  if (!n) return message.content;
  const note = `[Shared ${photoLabel(n)}]`;
  return message.content.trim() ? `${note}\n${message.content}` : note;
}
