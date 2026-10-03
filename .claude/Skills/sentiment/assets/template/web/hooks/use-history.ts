"use client";

import { useCallback, useEffect, useState } from "react";

import { KEYS, readStore, writeStore } from "@/lib/storage";
import type { HistoryEntry } from "@/lib/types";

const MAX_ENTRIES = 50;

function isEntry(value: unknown): value is HistoryEntry {
  const e = value as HistoryEntry | null;
  return (
    !!e &&
    typeof e.id === "string" &&
    typeof e.text === "string" &&
    typeof e.label === "string" &&
    typeof e.score === "number" &&
    typeof e.model === "string" &&
    typeof e.at === "number"
  );
}

/** Recent single-text analyses, kept in this browser. */
export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);

  // Read after mount so server and client render the same markup.
  useEffect(() => {
    const stored = readStore<unknown>(KEYS.history, []);
    setEntries(Array.isArray(stored) ? stored.filter(isEntry) : []);
  }, []);

  const persist = useCallback((next: HistoryEntry[]) => {
    setEntries(next);
    writeStore(KEYS.history, next);
  }, []);

  const add = useCallback(
    (entry: Omit<HistoryEntry, "id" | "at">) => {
      setEntries((current) => {
        const next = [
          // Not crypto.randomUUID(): it only exists on https/localhost.
          { ...entry, id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`, at: Date.now() },
          ...current.filter((e) => !(e.text === entry.text && e.model === entry.model)),
        ].slice(0, MAX_ENTRIES);
        writeStore(KEYS.history, next);
        return next;
      });
    },
    [],
  );

  /** Clears everything and returns an undo function. */
  const clear = useCallback((): (() => void) => {
    const backup = entries;
    persist([]);
    return () => persist(backup);
  }, [entries, persist]);

  return { entries, add, clear };
}
