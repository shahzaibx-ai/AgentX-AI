"use client";

import { LoaderCircleIcon, RefreshCwIcon, ScanTextIcon, TriangleAlertIcon } from "lucide-react";

import { Eyebrow, ResultView } from "@/components/studio/result-view";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { EXAMPLES } from "@/lib/config";
import { count, duration, wordCount } from "@/lib/format";
import type { Limits, ModelInfo, PredictResponse } from "@/lib/types";

const SPECIAL_TOKENS = new Set(["[CLS]", "[SEP]", "[PAD]", "<s>", "</s>", "<pad>"]);

export type AnalysisState =
  | { phase: "idle" }
  | { phase: "running"; modelReady: boolean }
  | { phase: "done"; result: PredictResponse }
  | { phase: "error"; message: string };

export function AnalyzeView({
  text,
  onTextChange,
  onAnalyze,
  analysis,
  model,
  models,
  limits,
}: {
  text: string;
  onTextChange: (text: string) => void;
  onAnalyze: (text?: string) => void;
  analysis: AnalysisState;
  model: ModelInfo | null;
  models: ModelInfo[];
  limits: Limits | null;
}) {
  const maxChars = limits?.max_text_chars ?? 5000;
  const running = analysis.phase === "running";
  const examples = EXAMPLES[model?.domain ?? "Topic"] ?? EXAMPLES.Topic;
  const result = analysis.phase === "done" ? analysis.result : null;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-balance">Analyze a text</h1>
        <p className="mt-1 max-w-[65ch] text-muted-foreground">
          The model returns a sentiment label, the probability of every class and the words that
          pushed it there.
        </p>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Input</CardTitle>
            <div className="flex flex-wrap gap-1.5" aria-label="Examples">
              {examples.map((example) => (
                <button
                  key={example.name}
                  type="button"
                  onClick={() => {
                    onTextChange(example.text);
                    onAnalyze(example.text);
                  }}
                  className="rounded-full border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-input hover:text-foreground"
                >
                  {example.name}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            <label htmlFor="analyze-text" className="sr-only">
              Text to analyze
            </label>
            <Textarea
              id="analyze-text"
              value={text}
              maxLength={maxChars}
              onChange={(e) => onTextChange(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  onAnalyze();
                }
              }}
              placeholder="Type or paste a review, a post, a headline…"
              className="max-h-96 min-h-48 resize-y bg-card text-[15px] leading-relaxed md:text-[15px]"
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground tabular">
                <span>
                  {count(text.length)} / {count(maxChars)} characters
                </span>
                <span>{count(wordCount(text))} words</span>
                <span>First {limits?.max_length ?? 512} tokens are analyzed</span>
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onTextChange("")} disabled={!text}>
                  Clear
                </Button>
                <Button onClick={() => onAnalyze()} disabled={!text.trim() || running}>
                  {running && <LoaderCircleIcon className="animate-spin" aria-hidden="true" />}
                  {running ? "Analyzing" : "Analyze"}
                  {!running && (
                    <kbd className="hidden font-mono text-[11px] opacity-60 sm:inline">Ctrl ↵</kbd>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card aria-live="polite">
          <CardHeader>
            <CardTitle>Result</CardTitle>
            {result && (
              <div className="flex flex-wrap gap-1.5">
                <Chip title={result.model}>
                  {models.find((m) => m.id === result.model)?.name ?? result.model}
                </Chip>
                <Chip title="Inference time">{duration(result.latency_ms)}</Chip>
                <Chip title="Tokens">{result.num_tokens} tokens</Chip>
                <Chip title="Device" mono>
                  {result.device}
                </Chip>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {analysis.phase === "idle" && (
              <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
                <ScanTextIcon className="size-8 opacity-60" aria-hidden="true" />
                <p className="max-w-72 text-sm">
                  Enter a text and press Analyze, or pick an example to see how {model?.name ?? "the model"} reads it.
                </p>
              </div>
            )}
            {analysis.phase === "running" &&
              (analysis.modelReady ? (
                <ResultSkeleton />
              ) : (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <LoaderCircleIcon className="size-7 animate-spin text-muted-foreground" aria-hidden="true" />
                  <p className="font-medium">Loading {model?.name ?? "the model"}…</p>
                  <p className="max-w-80 text-sm text-muted-foreground">
                    The first run downloads the model from Hugging Face. This can take a minute;
                    later requests are fast.
                  </p>
                </div>
              ))}
            {analysis.phase === "error" && (
              <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                <p className="flex gap-2 text-sm">
                  <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                  {analysis.message}
                </p>
                <Button variant="outline" size="sm" onClick={() => onAnalyze()}>
                  <RefreshCwIcon aria-hidden="true" />
                  Try again
                </Button>
              </div>
            )}
            {result && (
              <ResultView
                result={result}
                lowConfidence={limits?.low_confidence ?? 0.6}
                specialTokens={SPECIAL_TOKENS}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Chip({ children, title, mono }: { children: React.ReactNode; title: string; mono?: boolean }) {
  return (
    <span
      title={title}
      className={
        "inline-flex h-7 items-center rounded-full border px-2.5 text-xs text-muted-foreground tabular " +
        (mono ? "font-mono" : "")
      }
    >
      {children}
    </span>
  );
}

function ResultSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-label="Analyzing">
      <div className="flex items-center gap-3.5">
        <Skeleton className="size-11 rounded-xl" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <div className="flex flex-col gap-3">
        <Eyebrow>Class probabilities</Eyebrow>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
      </div>
      <div className="flex flex-col gap-2">
        <Eyebrow>Word influence</Eyebrow>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </div>
  );
}
