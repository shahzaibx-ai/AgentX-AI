"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchModels } from "@/lib/api";
import { readStorage, writeStorage } from "@/lib/helpers";
import type { ModelInfo, ModelSelection, ModelsResponse } from "@/lib/types";

const KEY = "assistant.model.v1";

export interface UseModels {
  data: ModelsResponse | null;
  loading: boolean;
  error: string | null;
  selection: ModelSelection;
  /** The model that will actually answer: the selection, or the server's default for Auto. */
  effective: ModelInfo | null;
  select: (selection: ModelSelection) => void;
  refresh: () => Promise<void>;
}

function findModel(data: ModelsResponse | null, sel: ModelSelection): ModelInfo | null {
  if (!data || !sel) return null;
  const provider = data.providers.find((p) => p.id === sel.provider);
  return provider?.models.find((m) => m.id === sel.model) ?? null;
}

export function useModels(): UseModels {
  const [data, setData] = useState<ModelsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<ModelSelection>(null);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async (refresh: boolean) => {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setLoading(true);
    try {
      const res = await fetchModels(refresh, ctrl.signal);
      setData(res);
      setError(null);
      // Drop a saved selection that no longer exists (e.g. the model was removed).
      setSelection((sel) => (sel && !findModel(res, sel) ? null : sel));
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      if (controller.current === ctrl) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setSelection(readStorage<ModelSelection>(KEY, null));
    void load(false);
    return () => controller.current?.abort();
  }, [load]);

  const select = useCallback((sel: ModelSelection) => {
    setSelection(sel);
    writeStorage(KEY, sel);
  }, []);

  const refresh = useCallback(() => load(true), [load]);

  return {
    data,
    loading,
    error,
    selection,
    effective: findModel(data, selection) ?? data?.default ?? null,
    select,
    refresh,
  };
}
