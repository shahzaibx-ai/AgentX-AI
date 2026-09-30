/** localStorage that never throws (private windows, blocked storage, SSR). */

export function readStore<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeStore(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage full or unavailable: history is a convenience, keep going
  }
}

export const KEYS = {
  model: "sentiment-studio.model.v1",
  history: "sentiment-studio.history.v1",
} as const;
