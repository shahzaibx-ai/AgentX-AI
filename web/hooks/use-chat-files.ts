"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { uid } from "@/lib/helpers";
import {
  deleteChatFile,
  extOf,
  formatSize,
  getChatFile,
  type LibraryLimits,
  PHOTO_EXT,
  uploadChatFile,
} from "@/lib/library";
import type { ChatFile } from "@/lib/types";

export type FilePhase = "uploading" | "indexing" | "ready" | "failed";

/** A file in the composer, before it's sent. */
export interface PendingFile {
  key: string;
  name: string;
  ext: string;
  size: number;
  phase: FilePhase;
  progress: number; // 0..1 while uploading
  id?: string; // server id once uploaded
  /** The chat already had this file: never delete it from here (an earlier message uses it). */
  reused?: boolean;
  error?: string;
}

/** Deletes an uploaded file that wasn't sent, unless an earlier message uses it. */
const dropUploaded = (f: Pick<PendingFile, "id" | "reused">) => {
  if (f.id && !f.reused) void deleteChatFile(f.id);
};

export interface UseChatFiles {
  items: PendingFile[];
  busy: boolean; // something is uploading or indexing
  add: (files: File[], chatId: string) => void;
  remove: (key: string) => void;
  /** Ready files for the message being sent; clears the tray (failed ones are dropped). */
  takeReady: () => ChatFile[];
  /** Clears the tray and deletes uploaded files that were never sent. */
  discard: () => void;
}

const POLL_MS = 900;

export function fileProblem(file: File, limits: LibraryLimits): string | null {
  const ext = extOf(file.name);
  if (PHOTO_EXT.test(file.name)) return "This is a photo. Use Add photos for images.";
  if (!limits.extensions.includes(ext)) {
    return `${ext ? `${ext} files` : "Files without a type"} can't be read. Use PDF, Word, Excel, PowerPoint, text, CSV, Markdown or code.`;
  }
  if (file.size === 0) return "The file is empty.";
  if (file.size > limits.chat_file_max_bytes) {
    return `${formatSize(file.size)} is over the ${formatSize(limits.chat_file_max_bytes)} limit. Split it, or ask a Library owner to add it to a collection.`;
  }
  return null;
}

export function useChatFiles(limits: LibraryLimits | null): UseChatFiles {
  const [items, setItems] = useState<PendingFile[]>([]);
  const current = useRef<PendingFile[]>([]);
  const aborts = useRef(new Map<string, () => void>());
  const limitsRef = useRef(limits);
  useEffect(() => {
    limitsRef.current = limits;
  });

  const commit = useCallback((next: PendingFile[]) => {
    current.current = next;
    setItems(next);
  }, []);
  const patch = useCallback(
    (key: string, p: Partial<PendingFile>) =>
      commit(current.current.map((f) => (f.key === key ? { ...f, ...p } : f))),
    [commit],
  );
  const alive = (key: string) => current.current.some((f) => f.key === key);

  const poll = useCallback(
    async (key: string, id: string) => {
      while (alive(key)) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        if (!alive(key)) return;
        try {
          const doc = await getChatFile(id);
          if (doc.status === "indexed") return patch(key, { phase: "ready" });
          if (doc.status === "failed") {
            return patch(key, { phase: "failed", error: doc.error || "Couldn't be read." });
          }
        } catch (err) {
          return patch(key, { phase: "failed", error: (err as Error).message });
        }
      }
    },
    [patch],
  );

  const add = useCallback(
    (files: File[], chatId: string) => {
      const lim = limitsRef.current;
      if (!lim) return;
      const skipped: string[] = [];
      for (const file of files) {
        if (current.current.length >= lim.chat_files_per_message) {
          skipped.push(file.name);
          continue;
        }
        const key = uid();
        const problem = fileProblem(file, lim);
        const item: PendingFile = {
          key,
          name: file.name,
          ext: extOf(file.name),
          size: file.size,
          phase: problem ? "failed" : "uploading",
          progress: 0,
          ...(problem ? { error: problem } : {}),
        };
        commit([...current.current, item]);
        if (problem) continue;

        const { promise, abort } = uploadChatFile(file, chatId, (p) => patch(key, { progress: p }));
        aborts.current.set(key, abort);
        promise.then(
          (doc) => {
            aborts.current.delete(key);
            if (!alive(key)) return dropUploaded(doc); // removed while uploading
            patch(key, {
              id: doc.id,
              reused: !!doc.reused,
              progress: 1,
              phase: doc.status === "indexed" ? "ready" : doc.status === "failed" ? "failed" : "indexing",
              ...(doc.status === "failed" ? { error: doc.error } : {}),
            });
            if (doc.status === "queued" || doc.status === "processing") void poll(key, doc.id);
          },
          (err: Error) => {
            aborts.current.delete(key);
            if (err.name === "AbortError" || !alive(key)) return;
            patch(key, { phase: "failed", error: err.message });
          },
        );
      }
      if (skipped.length) {
        toast(`Up to ${lim.chat_files_per_message} files per message.`, {
          description:
            skipped.length === 1 ? `${skipped[0]} wasn't added.` : `${skipped.length} files weren't added.`,
        });
      }
    },
    [commit, patch, poll],
  );

  const remove = useCallback(
    (key: string) => {
      const f = current.current.find((x) => x.key === key);
      if (!f) return;
      aborts.current.get(key)?.();
      aborts.current.delete(key);
      commit(current.current.filter((x) => x.key !== key));
      dropUploaded(f);
    },
    [commit],
  );

  const takeReady = useCallback(() => {
    const ready = current.current
      .filter((f) => f.phase === "ready" && f.id)
      .map((f) => ({ id: f.id!, name: f.name, ext: f.ext, size: f.size }));
    for (const f of current.current) if (f.phase === "failed") dropUploaded(f);
    commit([]);
    return ready;
  }, [commit]);

  const discard = useCallback(() => {
    for (const f of current.current) {
      aborts.current.get(f.key)?.();
      dropUploaded(f);
    }
    aborts.current.clear();
    commit([]);
  }, [commit]);

  return {
    items,
    busy: items.some((f) => f.phase === "uploading" || f.phase === "indexing"),
    add,
    remove,
    takeReady,
    discard,
  };
}
