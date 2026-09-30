import { Swatch } from "@/components/studio/label-pill";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { labelColor, labelName } from "@/lib/labels";
import { pct } from "@/lib/format";
import type { LabelScore } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Softmax probability for every class, in the model's negative → positive order. */
export function ProbabilityBars({ probs, top }: { probs: LabelScore[]; top: string }) {
  return (
    <ul className="flex flex-col gap-2.5" aria-label="Class probabilities">
      {probs.map((p) => {
        const isTop = p.label === top;
        return (
          <li key={p.label}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  tabIndex={0}
                  className="grid grid-cols-[5.5rem_minmax(0,1fr)_3.5rem] items-center gap-3 rounded-sm text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                  aria-label={`${labelName(p.label)} ${pct(p.score)}`}
                >
                  <span className="flex items-center gap-2 truncate">
                    <Swatch label={p.label} />
                    {labelName(p.label)}
                  </span>
                  <span className="h-3 rounded-r-[4px] bg-muted">
                    <span
                      className="block h-full min-w-0.5 rounded-r-[4px] transition-[width] duration-300 motion-reduce:transition-none"
                      style={{ width: `${p.score * 100}%`, background: labelColor(p.label) }}
                    />
                  </span>
                  <span
                    className={cn(
                      "text-right font-mono text-xs tabular",
                      isTop ? "font-medium text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {pct(p.score)}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="top">
                {labelName(p.label)}: {pct(p.score, 2)} · logit {p.logit.toFixed(2)}
              </TooltipContent>
            </Tooltip>
          </li>
        );
      })}
    </ul>
  );
}
