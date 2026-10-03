export const pct = (value: number, digits = 1): string => `${(value * 100).toFixed(digits)}%`;

export const count = (value: number): string => value.toLocaleString("en-US");

export function duration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`;
}

export function timeAgo(at: number, now = Date.now()): string {
  const seconds = Math.round((now - at) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  return new Date(at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export const wordCount = (text: string): number => (text.match(/\S+/g) ?? []).length;
