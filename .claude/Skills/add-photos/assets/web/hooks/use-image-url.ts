"use client";

import { useEffect, useState } from "react";

import { cachedUrl, imageUrl } from "@/lib/image-store";

/** The object URL of a stored photo: undefined while loading, null if it's gone. */
export function useImageUrl(id: string): string | null | undefined {
  const [state, setState] = useState<{ id: string; url: string | null } | null>(() => {
    const url = cachedUrl(id);
    return url ? { id, url } : null;
  });

  useEffect(() => {
    let alive = true;
    imageUrl(id).then(
      (url) => alive && setState({ id, url }),
      () => alive && setState({ id, url: null }),
    );
    return () => {
      alive = false;
    };
  }, [id]);

  if (state?.id === id) return state.url;
  return cachedUrl(id) ?? undefined;
}
