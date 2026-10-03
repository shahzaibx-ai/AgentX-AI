"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { streamChat } from "@/lib/api";
import { makeTitle, readStorage, uid, writeStorage } from "@/lib/helpers";
import type { ChatMessage, Conversation, ModelSelection } from "@/lib/types";

const KEY = "assistant.conversations.v1";
const MAX_SAVED = 200;

type Updater = (c: Conversation) => Conversation;

export function useChat(selection: ModelSelection, onFinish?: () => void) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const controller = useRef<AbortController | null>(null);
  const selectionRef = useRef(selection);
  const onFinishRef = useRef(onFinish);
  useEffect(() => {
    selectionRef.current = selection;
    onFinishRef.current = onFinish;
  });

  // Load once on the client (localStorage is not available during SSR).
  useEffect(() => {
    setConversations(readStorage<Conversation[]>(KEY, []));
    setHydrated(true);
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
        await streamChat({
          messages: history.filter((m) => !m.error).map(({ role, content }) => ({ role, content })),
          selection: selectionRef.current,
          signal: ctrl.signal,
          onMeta: (meta) => patchMessage(convId, reply.id, { meta }),
          onDelta: (text) => {
            buffer += text;
            if (!frame) frame = requestAnimationFrame(flush);
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
    (text: string) => {
      const content = text.trim();
      if (!content || controller.current) return;
      const userMsg: ChatMessage = { id: uid(), role: "user", content, createdAt: Date.now() };
      const existing = conversations.find((c) => c.id === activeId);
      if (existing) {
        void generate(existing.id, [...existing.messages.filter((m) => !m.error), userMsg]);
        return;
      }
      const conv: Conversation = {
        id: uid(),
        title: makeTitle(content),
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
    newChat,
    openChat,
    deleteChat,
    clearAll,
  };
}
