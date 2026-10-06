"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchLibraryConfig, type LibraryConfig } from "@/lib/library";

/** Whether files and the Library are on, their limits and the collections to search. */
export function useLibraryConfig() {
  const [config, setConfig] = useState<LibraryConfig | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchLibraryConfig(ctrl.signal).then(setConfig, () => {
      if (!ctrl.signal.aborted) setConfig(null); // API offline or an old API: hide the features
    });
    return () => ctrl.abort();
  }, [version]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  return { config, enabled: !!config?.enabled, refresh };
}
