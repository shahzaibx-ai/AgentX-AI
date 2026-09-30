/** Colour, name and icon for each sentiment label, across all models. */

const COLORS: Record<string, string> = {
  negative: "var(--negative)",
  neutral: "var(--neutral)",
  positive: "var(--positive)",
  "1 star": "var(--negative)",
  "2 stars": "var(--stars-2)",
  "3 stars": "var(--neutral)",
  "4 stars": "var(--stars-4)",
  "5 stars": "var(--positive)",
};

export const labelColor = (label: string): string => COLORS[label] ?? "var(--neutral)";

export const labelName = (label: string): string =>
  label.charAt(0).toUpperCase() + label.slice(1);

export type LabelTone = "positive" | "neutral" | "negative";

export function labelTone(label: string): LabelTone {
  if (label === "positive" || label === "4 stars" || label === "5 stars") return "positive";
  if (label === "negative" || label === "1 star" || label === "2 stars") return "negative";
  return "neutral";
}

export const isStarLabel = (label: string): boolean => /star/.test(label);

/** Expected star rating from a 1-5 star distribution (probs ordered 1 → 5). */
export function expectedStars(probs: { score: number }[]): number {
  return probs.reduce((sum, p, i) => sum + p.score * (i + 1), 0);
}
