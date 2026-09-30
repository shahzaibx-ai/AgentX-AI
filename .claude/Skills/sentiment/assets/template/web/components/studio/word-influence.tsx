import type { Attribution } from "@/lib/types";

/**
 * The original text with each word shaded by its integrated-gradients weight:
 * blue pushed the prediction toward positive, red toward negative.
 */
export function WordInfluence({ attributions }: { attributions: Attribution[] }) {
  return (
    <div>
      <p className="text-[15px] leading-8 break-words whitespace-pre-wrap">
        {attributions.map((a, i) => {
          if (!a.text.trim() || Math.abs(a.weight) < 0.05) return <span key={i}>{a.text}</span>;
          const strength = Math.round(10 + Math.abs(a.weight) * 34);
          const color = a.weight > 0 ? "var(--positive)" : "var(--negative)";
          const direction = a.weight > 0 ? "toward positive" : "toward negative";
          return (
            <span
              key={i}
              title={`${direction} · ${a.weight.toFixed(2)}`}
              className="rounded-[4px] px-0.5 py-px"
              style={{ background: `color-mix(in srgb, ${color} ${strength}%, transparent)` }}
            >
              {a.text}
            </span>
          );
        })}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <Legend color="var(--negative)">Toward negative</Legend>
        <Legend color="var(--positive)">Toward positive</Legend>
        <span>Integrated gradients</span>
      </div>
    </div>
  );
}

function Legend({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className="size-2.5 rounded-[3px]"
        style={{ background: `color-mix(in srgb, ${color} 40%, transparent)` }}
      />
      {children}
    </span>
  );
}
