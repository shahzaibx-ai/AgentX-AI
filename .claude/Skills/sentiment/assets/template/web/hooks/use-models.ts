"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { KEYS, readStore, writeStore } from "@/lib/storage";
import type { ModelInfo, ModelStatus, ModelsResponse } from "@/lib/types";

const POLL_OFFLINE_MS = 5000;
const POLL_LOADING_MS = 2000;

export interface ModelsState {
  data: ModelsResponse | null;
  /** Set when the API can't be reached (or answered with an error). */
  error: string | null;
  loading: boolean;
  selected: ModelInfo | null;
  select: (id: string) => void;
  refresh: () => Promise<void>;
  /** Update one model's status locally (e.g. it became ready after a prediction). */
  setStatus: (id: string, status: ModelStatus, error?: string | null) => void;
}

export function useModels(): ModelsState {
  const [data, setData] = useState<ModelsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Bumped after every attempt so the retry timer is rescheduled even when the error text repeats.
  const [attempt, setAttempt] = useState(0);
  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const next = await api.models(controller.signal);
      setData(next);
      setError(null);
      setSelectedId((current) => {
        const valid = (id: string | null) => !!id && next.models.some((m) => m.id === id);
        if (valid(current)) return current;
        const stored = readStore<string | null>(KEYS.model, null);
        return valid(stored) ? stored : next.default_model;
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(errorMessage(err));
    } finally {
      if (inFlight.current === controller) {
        setLoading(false);
        setAttempt((n) => n + 1);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => inFlight.current?.abort();
  }, [refresh]);

  // Keep polling while the API is offline or a model is still loading.
  const anyLoading = data?.models.some((m) => m.status === "loading") ?? false;
  useEffect(() => {
    if (loading) return;
    if (!error && !anyLoading) return;
    const timer = setTimeout(() => void refresh(), error ? POLL_OFFLINE_MS : POLL_LOADING_MS);
    return () => clearTimeout(timer);
  }, [loading, error, anyLoading, attempt, refresh]);

  const select = useCallback((id: string) => {
    setSelectedId(id);
    writeStore(KEYS.model, id);
  }, []);

  const setStatus = useCallback((id: string, status: ModelStatus, err: string | null = null) => {
    setData((current) =>
      current && {
        ...current,
        models: current.models.map((m) => (m.id === id ? { ...m, status, error: err } : m)),
      },
    );
  }, []);

  const selected = useMemo(
    () => data?.models.find((m) => m.id === selectedId) ?? null,
    [data, selectedId],
  );

  return { data, error, loading, selected, select, refresh, setStatus };
}
