"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { uid } from "@/lib/helpers";
import { deleteImage, rememberUrl, saveImage } from "@/lib/image-store";
import { precheck, prepareImage, tooManyMessage } from "@/lib/images";
import type { ChatImage, ImageLimits } from "@/lib/types";

/** A photo in the composer, before it's sent. */
export interface Attachment {
  id: string;
  name: string;
  /** Local preview; revoked when the attachment is removed or sent. */
  previewUrl?: string;
  /** Set once the photo is read, scaled and stored. */
  image?: ChatImage;
}

/** A file that couldn't be added, shown until dismissed. */
export interface AttachmentProblem {
  id: string;
  name: string;
  reason: string;
}

export interface UseAttachments {
  items: Attachment[];
  problems: AttachmentProblem[];
  /** True while any photo is still being read. */
  processing: boolean;
  ready: ChatImage[];
  add: (files: Iterable<File>) => void;
  remove: (id: string) => void;
  dismiss: (id: string) => void;
  /** Empties the tray after sending: the stored photos now belong to the message. */
  takeAll: () => ChatImage[];
}

export function useAttachments(limits: ImageLimits): UseAttachments {
  const [items, setItems] = useState<Attachment[]>([]);
  const [problems, setProblems] = useState<AttachmentProblem[]>([]);
  // Mirrors `items` synchronously, so several quick adds count correctly.
  const current = useRef<Attachment[]>([]);
  const limitsRef = useRef(limits);
  useEffect(() => {
    limitsRef.current = limits;
  });

  const commit = useCallback((next: Attachment[]) => {
    current.current = next;
    setItems(next);
  }, []);

  const problem = useCallback((name: string, reason: string) => {
    setProblems((list) => [...list, { id: uid(), name, reason }]);
  }, []);

  const release = (a: Attachment) => {
    if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
  };

  const add = useCallback(
    (files: Iterable<File>) => {
      const skipped: string[] = [];
      for (const file of files) {
        const lim = limitsRef.current;
        const reason = precheck(file, lim);
        if (reason) {
          problem(file.name, reason);
          continue;
        }
        if (current.current.length >= lim.per_message) {
          skipped.push(file.name);
          continue;
        }
        const attachment: Attachment = { id: uid(), name: file.name };
        commit([...current.current, attachment]);

        void (async () => {
          try {
            const prepared = await prepareImage(file, lim);
            const image: ChatImage = {
              id: attachment.id,
              name: file.name,
              mediaType: prepared.mediaType,
              width: prepared.width,
              height: prepared.height,
              size: prepared.blob.size,
              ...(prepared.resizedFrom ? { resizedFrom: prepared.resizedFrom } : {}),
            };
            // Removed while it was being read: nothing to keep.
            if (!current.current.some((a) => a.id === attachment.id)) return;
            await saveImage(attachment.id, prepared.blob);
            const previewUrl = URL.createObjectURL(prepared.blob);
            if (!current.current.some((a) => a.id === attachment.id)) {
              URL.revokeObjectURL(previewUrl);
              void deleteImage(attachment.id);
              return;
            }
            commit(
              current.current.map((a) => (a.id === attachment.id ? { ...a, image, previewUrl } : a)),
            );
          } catch (err) {
            if (!current.current.some((a) => a.id === attachment.id)) return; // removed meanwhile
            commit(current.current.filter((a) => a.id !== attachment.id));
            problem(file.name, (err as Error).message);
          }
        })();
      }
      if (skipped.length) {
        const limit = limitsRef.current.per_message;
        toast(tooManyMessage(limit), {
          description:
            skipped.length === 1 ? `${skipped[0]} wasn't added.` : `${skipped.length} photos weren't added.`,
        });
      }
    },
    [commit, problem],
  );

  const remove = useCallback(
    (id: string) => {
      const found = current.current.find((a) => a.id === id);
      if (!found) return;
      release(found);
      commit(current.current.filter((a) => a.id !== id));
      void deleteImage(id);
    },
    [commit],
  );

  const dismiss = useCallback((id: string) => {
    setProblems((list) => list.filter((p) => p.id !== id));
  }, []);

  const takeAll = useCallback(() => {
    const images = current.current.flatMap((a) => (a.image ? [a.image] : []));
    for (const a of current.current) {
      if (a.image && a.previewUrl) rememberUrl(a.id, a.previewUrl);
      else release(a);
    }
    commit([]);
    setProblems([]);
    return images;
  }, [commit]);

  // Previews are object URLs; free them when the page goes away.
  useEffect(() => () => current.current.forEach(release), []);

  return {
    items,
    problems,
    processing: items.some((a) => !a.image),
    ready: items.flatMap((a) => (a.image ? [a.image] : [])),
    add,
    remove,
    dismiss,
    takeAll,
  };
}
