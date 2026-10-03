import { FrownIcon, MehIcon, SmileIcon, StarIcon, TriangleAlertIcon } from "lucide-react";

import { ProbabilityBars } from "@/components/studio/probability-bars";
import { WordInfluence } from "@/components/studio/word-influence";
import { expectedStars, isStarLabel, labelColor, labelName, labelTone } from "@/lib/labels";
import { pct } from "@/lib/format";
import type { PredictResponse } from "@/lib/types";

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2.5 text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
      {children}
    </h3>
  );
}

export function ResultView({
  result,
  lowConfidence,
  specialTokens,
}: {
  result: PredictResponse;
  lowConfidence: number;
  specialTokens: Set<string>;
}) {
  const stars = isStarLabel(result.label);
  const tone = labelTone(result.label);
  const Icon = stars ? StarIcon : tone === "positive" ? SmileIcon : tone === "negative" ? FrownIcon : MehIcon;
  const low = result.score < lowConfidence;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3.5">
          <span
            className="grid size-11 shrink-0 place-items-center rounded-xl text-white"
            style={{ background: labelColor(result.label) }}
          >
            <Icon className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-2xl leading-tight font-semibold tracking-tight">
              {labelName(result.label)}
            </p>
            <p className="text-sm text-muted-foreground tabular">
              {pct(result.score)} confidence
              {stars && ` · expected rating ${expectedStars(result.probs).toFixed(2)} ★`}
            </p>
          </div>
        </div>
        {low && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/40 px-2.5 py-1 text-xs font-medium text-warning">
            <TriangleAlertIcon className="size-3.5" aria-hidden="true" />
            Low confidence · review
          </span>
        )}
      </div>

      <section>
        <Eyebrow>Class probabilities</Eyebrow>
        <ProbabilityBars probs={result.probs} top={result.label} />
      </section>

      {result.attributions && (
        <section>
          <Eyebrow>Word influence</Eyebrow>
          <WordInfluence attributions={result.attributions} />
        </section>
      )}

      {result.truncated && (
        <p className="flex gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
          <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          This text has {result.num_tokens} tokens. Only the first {result.tokens.length} were
          classified.
        </p>
      )}

      <details className="group">
        <summary className="cursor-pointer text-sm text-muted-foreground select-none hover:text-foreground">
          {result.truncated
            ? `Tokens (${result.tokens.length} of ${result.num_tokens})`
            : `Tokens (${result.num_tokens})`}
        </summary>
        <div className="mt-2.5 flex flex-wrap gap-1">
          {result.tokens.map((token, i) => (
            <span
              key={i}
              className={
                specialTokens.has(token)
                  ? "rounded-[5px] border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground"
                  : "rounded-[5px] border bg-muted px-1.5 py-0.5 font-mono text-xs"
              }
            >
              {token}
            </span>
          ))}
        </div>
      </details>
    </div>
  );
}
