"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { streamChat, type ApiMessage } from "@/lib/api";
import { makeTitle, readStorage, uid, writeStorage } from "@/lib/helpers";
import { collectGarbage, loadImage } from "@/lib/image-store";
import { blobToBase64, photoLabel, textWithPhotoNote } from "@/lib/images";
import type {
  ChatFile,
  ChatImage,
  ChatMessage,
  CollectionRef,
  Conversation,
  ModelSelection,
} from "@/lib/types";

const KEY = "assistant.conversations.v1";
const MAX_SAVED = 200;
const GC_GRACE_MS = 24 * 60 * 60 * 1000;

type Updater = (c: Conversation) => Conversation;

/** Every file added anywhere in the chat: later questions still search them. */
export const filesOf = (messages: ChatMessage[]): ChatFile[] =>
  messages.flatMap((m) => (m.role === "user" ? (m.files ?? []) : []));

/** What to search for this reply: the collections picked for the last question,
 *  plus every file in the chat. Empty → an ordinary model reply. */
function ragFor(history: ChatMessage[], chatId: string) {
  const lastUser = [...history].reverse().find((m) => m.role === "user");
  const collections = (lastUser?.collections ?? []).map((c) => c.id);
  const files = [...new Set(filesOf(history).map((f) => f.id))];
  return collections.length || files.length ? { collections, files, chat_id: chatId } : null;
}

export interface SendOptions {
  images?: ChatImage[];
  files?: ChatFile[];
  collections?: CollectionRef[];
  /** Id for a new chat (files are uploaded under it before the chat exists). */
  newChatId?: string;
}

export interface ImagePolicy {
  /** False when the chosen model is text-only: photos are described as text instead. */
  send: boolean;
  /** Most photos sent in one request; the newest are kept. */
  perRequest: number;
  /** The API's current limits; older photos beyond them become a note. */
  perMessage: number;
  maxBytes: number;
}

/**
 * The request body for a history: the newest photos (up to the limit) are
 * attached as base64; older or unsendable photos become a short text note so
 * the model still knows they were there.
 */
async function toApiMessages(history: ChatMessage[], policy: ImagePolicy): Promise<ApiMessage[]> {
  let budget = policy.send ? policy.perRequest : 0;
  const out: ApiMessage[] = [];
  for (let i = history.length - 1; i >= 0; i--) {
    const m = history[i];
    const images = m.images ?? [];
    // An empty user turn (e.g. a voice transcript with no words) adds nothing.
    if (m.role === "user" && !m.content.trim() && !images.length) continue;
    if (!images.length || m.role !== "user") {
      out.push({ role: m.role, content: m.content });
      continue;
    }
    const allowed = Math.min(budget, policy.perMessage);
    const chosen = allowed > 0 ? images.filter((img) => img.size <= policy.maxBytes).slice(-allowed) : [];
    budget -= chosen.length;
    const loaded = await Promise.all(
      chosen.map(async (img) => {
        const blob = await loadImage(img.id);
        return blob ? { media_type: img.mediaType, data: await blobToBase64(blob) } : null;
      }),
    );
    const sent = loaded.filter((x) => x !== null);
    if (sent.length === images.length) {
      out.push({ role: m.role, content: m.content, images: sent });
    } else {
      const left = images.length - sent.length;
      const note = sent.length
        ? `[${photoLabel(left)} more not included]\n${m.content}`.trim()
        : textWithPhotoNote(m);
      out.push({ role: m.role, content: note, ...(sent.length ? { images: sent } : {}) });
    }
  }
  return out.reverse();
}

export function useChat(
  selection: ModelSelection,
  imagePolicy: ImagePolicy = { send: true, perRequest: 20, perMessage: 5, maxBytes: 10 * 1024 * 1024 },
  onFinish?: () => void,
) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const controller = useRef<AbortController | null>(null);
  const selectionRef = useRef(selection);
  const onFinishRef = useRef(onFinish);
  const imagePolicyRef = useRef(imagePolicy);
  useEffect(() => {
    selectionRef.current = selection;
    onFinishRef.current = onFinish;
    imagePolicyRef.current = imagePolicy;
  });

  // Load once on the client (localStorage is not available during SSR), then
  // delete stored photos that no saved chat uses any more.
  useEffect(() => {
    const startedAt = Date.now();
    const saved = readStorage<Conversation[]>(KEY, []);
    setConversations(saved);
    setHydrated(true);
    const keep = new Set(saved.flatMap((c) => c.messages.flatMap((m) => m.images ?? []).map((i) => i.id)));
    // A day's grace: another tab may be sending photos its chats haven't saved yet.
    void collectGarbage(keep, startedAt - GC_GRACE_MS).catch(() => {});
  }, []);

  // Persist whenever we're not mid-stream (avoids writing on every token).
  useEffect(() => {
    if (!hydrated || streaming) return;
    writeStorage(
      KEY,
      conversations
        .slice(0, MAX_SAVED)
        .map((c) => ({ ...c, messages: c.messages.filter((m) => !m.pending) })),
    );
  }, [conversations, hydrated, streaming]);

  const update = useCallback((id: string, fn: Updater) => {
    setConversations((list) => list.map((c) => (c.id === id ? fn(c) : c)));
  }, []);

  const patchMessage = useCallback(
    (convId: string, msgId: string, patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) =>
      update(convId, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === msgId ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m,
        ),
      })),
    [update],
  );

  const generate = useCallback(
    async (convId: string, history: ChatMessage[]) => {
      const reply: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: "",
        pending: true,
        createdAt: Date.now(),
      };
      update(convId, (c) => ({ ...c, messages: [...history, reply], updatedAt: Date.now() }));

      const ctrl = new AbortController();
      controller.current = ctrl;
      setStreaming(true);

      // Batch token updates to one render per animation frame.
      let buffer = "";
      let frame = 0;
      const flush = () => {
        frame = 0;
        if (!buffer) return;
        const chunk = buffer;
        buffer = "";
        patchMessage(convId, reply.id, (m) => ({ content: m.content + chunk }));
      };

      try {
        const messages = await toApiMessages(
          history.filter((m) => !m.error),
          imagePolicyRef.current,
        );
        if (ctrl.signal.aborted) throw new DOMException("Aborted", "AbortError");
        await streamChat({
          messages,
          selection: selectionRef.current,
          rag: ragFor(history, convId),
          signal: ctrl.signal,
          onMeta: (meta) => patchMessage(convId, reply.id, { meta }),
          onDelta: (text) => {
            buffer += text;
            if (!frame) frame = requestAnimationFrame(flush);
          },
          onSources: (s) => {
            cancelAnimationFrame(frame);
            frame = 0;
            buffer = "";
            // The final text carries [n] markers that link to these passages.
            patchMessage(convId, reply.id, { content: s.cited_text, sources: s.sources });
          },
        });
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          patchMessage(convId, reply.id, { error: (err as Error).message });
        }
      } finally {
        cancelAnimationFrame(frame);
        flush();
        update(convId, (c) => ({
          ...c,
          updatedAt: Date.now(),
          messages: c.messages
            .map((m) => (m.id === reply.id ? { ...m, pending: false } : m))
            // Drop an empty reply that was stopped before any text arrived.
            .filter((m) => m.id !== reply.id || m.content || m.error),
        }));
        if (controller.current === ctrl) controller.current = null;
        setStreaming(false);
        onFinishRef.current?.();
      }
    },
    [patchMessage, update],
  );

  const send = useCallback(
    (text: string, opts: SendOptions = {}) => {
      const { images = [], files = [], collections = [] } = opts;
      const content = text.trim();
      if ((!content && !images.length && !files.length) || controller.current) return;
      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content,
        createdAt: Date.now(),
        ...(images.length ? { images } : {}),
        ...(files.length ? { files } : {}),
        ...(collections.length ? { collections } : {}),
      };
      const existing = conversations.find((c) => c.id === activeId);
      if (existing) {
        void generate(existing.id, [...existing.messages.filter((m) => !m.error), userMsg]);
        return;
      }
      const fallbackTitle = files.length
        ? files[0].name
        : images.length > 1
          ? `${images.length} photos`
          : "Photo";
      const conv: Conversation = {
        id: opts.newChatId ?? uid(),
        title: makeTitle(content || fallbackTitle),
        ...(collections.length ? { collections } : {}),
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setConversations((list) => [conv, ...list]);
      setActiveId(conv.id);
      void generate(conv.id, [userMsg]);
    },
    [activeId, conversations, generate],
  );

  const stop = useCallback(() => controller.current?.abort(), []);

  /** Re-run the assistant reply at `messageId` (drops it and everything after). */
  const regenerate = useCallback(
    (messageId: string) => {
      const conv = conversations.find((c) => c.id === activeId);
      if (!conv || controller.current) return;
      const idx = conv.messages.findIndex((m) => m.id === messageId);
      if (idx < 1) return;
      void generate(conv.id, conv.messages.slice(0, idx));
    },
    [activeId, conversations, generate],
  );

  const setFeedback = useCallback(
    (messageId: string, value: "up" | "down") => {
      if (!activeId) return;
      patchMessage(activeId, messageId, (m) => ({ feedback: m.feedback === value ? null : value }));
    },
    [activeId, patchMessage],
  );

  /** The collections a chat searches (the Library pill). */
  const setCollections = useCallback(
    (id: string, collections: CollectionRef[]) =>
      update(id, (c) => ({ ...c, collections })),
    [update],
  );

  const newChat = useCallback(() => {
    controller.current?.abort();
    setActiveId(null);
  }, []);

  const openChat = useCallback(
    (id: string) => {
      if (id !== activeId) controller.current?.abort();
      setActiveId(id);
    },
    [activeId],
  );

  /** Deletes a chat and returns a function that restores it. */
  const deleteChat = useCallback(
    (id: string) => {
      const index = conversations.findIndex((c) => c.id === id);
      const removed = conversations[index];
      if (!removed) return () => {};
      if (id === activeId) {
        controller.current?.abort();
        setActiveId(null);
      }
      setConversations((list) => list.filter((c) => c.id !== id));
      return () =>
        setConversations((list) => {
          const next = [...list];
          next.splice(Math.min(index, next.length), 0, removed);
          return next;
        });
    },
    [activeId, conversations],
  );

  /**
   * Saves voice transcripts. A message whose id is already in the chat is
   * updated (late words); others are appended. With no conversation yet,
   * creates one (titled from the first spoken user message), opens it, and
   * returns its id so later transcripts from the same session land there.
   */
  const appendVoiceMessages = useCallback(
    (conversationId: string | null, messages: ChatMessage[]): string => {
      const now = Date.now();
      if (conversationId) {
        update(conversationId, (c) => {
          const byId = new Map(messages.map((m) => [m.id, m]));
          const updated = c.messages.map((m) => {
            const next = byId.get(m.id);
            if (!next) return m;
            byId.delete(m.id);
            return { ...m, content: next.content, meta: next.meta ?? m.meta };
          });
          return { ...c, messages: [...updated, ...byId.values()], updatedAt: now };
        });
        return conversationId;
      }
      const id = uid();
      const firstUser = messages.find((m) => m.role === "user");
      setConversations((list) => [
        {
          id,
          title: makeTitle(firstUser?.content ?? "Voice chat"),
          messages,
          createdAt: now,
          updatedAt: now,
        },
        ...list,
      ]);
      setActiveId(id);
      return id;
    },
    [update],
  );

  const clearAll = useCallback(() => {
    controller.current?.abort();
    const backup = conversations;
    setConversations([]);
    setActiveId(null);
    return () => setConversations(backup);
  }, [conversations]);

  return {
    conversations,
    active: conversations.find((c) => c.id === activeId) ?? null,
    activeId,
    streaming,
    hydrated,
    send,
    stop,
    regenerate,
    setFeedback,
    setCollections,
    newChat,
    openChat,
    deleteChat,
    clearAll,
    appendVoiceMessages,
  };
}
