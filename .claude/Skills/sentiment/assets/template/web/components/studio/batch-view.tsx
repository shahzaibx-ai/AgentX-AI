"use client";

import { useMemo, useRef, useState } from "react";
import {
  CopyIcon,
  DownloadIcon,
  LoaderCircleIcon,
  TriangleAlertIcon,
  UploadIcon,
  XIcon,
} from "lucide-react";
import { toast } from "sonner";

import { LabelPill, Swatch } from "@/components/studio/label-pill";
import { Eyebrow } from "@/components/studio/result-view";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, errorMessage } from "@/lib/api";
import { BATCH_SAMPLE } from "@/lib/config";
import { downloadFile, textsFromFile, toCsv } from "@/lib/csv";
import { count, duration, pct } from "@/lib/format";
import { labelColor, labelName } from "@/lib/labels";
import type { BatchItem, Limits, ModelInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

// Rows per request: small enough for a smooth progress bar, large enough to batch well.
const CHUNK = 64;
const MAX_FILE_BYTES = 10 * 1024 * 1024;

interface BatchRun {
  model: ModelInfo;
  texts: string[];
  results: BatchItem[];
  latencyMs: number;
}

type Filter = "all" | "review" | string;

export function BatchView({
  model,
  limits,
  onModelReady,
}: {
  model: ModelInfo | null;
  limits: Limits | null;
  onModelReady: (id: string) => void;
}) {
  const [input, setInput] = useState("");
  const [run, setRun] = useState<BatchRun | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [dragging, setDragging] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const maxRows = limits?.max_batch_items ?? 1000;
  const maxChars = limits?.max_text_chars ?? 5000;
  const lowConfidence = limits?.low_confidence ?? 0.6;
  const rows = useMemo(
    () => input.split(/\r?\n/).map((l) => l.trim()).filter(Boolean),
    [input],
  );
  const tooLong = rows.findIndex((r) => r.length > maxChars);
  const running = progress !== null;

  async function start() {
    if (!model || rows.length === 0 || running) return;
    const texts = rows.slice(0, maxRows);
    const controller = new AbortController();
    abort.current = controller;
    setError(null);
    setProgress({ done: 0, total: texts.length });
    const results: BatchItem[] = [];
    let latency = 0;
    try {
      for (let i = 0; i < texts.length; i += CHUNK) {
        const chunk = texts.slice(i, i + CHUNK);
        const res = await api.predictBatch({ texts: chunk, model: model.id }, controller.signal);
        results.push(...res.results);
        latency += res.latency_ms;
        setProgress({ done: results.length, total: texts.length });
        if (i === 0) onModelReady(model.id);
      }
      setRun({ model, texts, results, latencyMs: latency });
      setFilter("all");
    } catch (err) {
      if (!controller.signal.aborted) setError(errorMessage(err));
      else toast("Batch cancelled.");
    } finally {
      setProgress(null);
      abort.current = null;
    }
  }

  function loadFile(file: File) {
    if (file.size > MAX_FILE_BYTES) {
      toast.error("That file is over 10 MB. Split it into smaller files.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const texts = textsFromFile(file.name, String(reader.result ?? ""));
      if (texts.length === 0) {
        toast.error(`No text found in ${file.name}.`);
        return;
      }
      setInput(texts.slice(0, maxRows).join("\n"));
      toast(
        texts.length > maxRows
          ? `Loaded the first ${count(maxRows)} of ${count(texts.length)} rows from ${file.name}.`
          : `Loaded ${count(texts.length)} rows from ${file.name}.`,
      );
    };
    reader.onerror = () => toast.error(`Couldn't read ${file.name}.`);
    reader.readAsText(file);
  }

  function exportRows(): string {
    if (!run) return "";
    return toCsv(
      ["text", "label", "confidence", ...run.model.labels.map((l) => `p_${l.replace(/\s+/g, "_")}`)],
      run.results.map((r, i) => [
        run.texts[i],
        r.label,
        r.score.toFixed(4),
        ...r.probs.map((p) => p.score.toFixed(4)),
      ]),
    );
  }

  async function copyCsv() {
    try {
      await navigator.clipboard.writeText(exportRows());
      toast(`Copied ${count(run?.results.length ?? 0)} rows as CSV.`);
    } catch {
      toast.error("Copying isn't allowed here. Use Download instead.");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Batch analysis</h1>
        <p className="mt-1 max-w-[65ch] text-muted-foreground">
          One text per line, or upload a CSV with a <code className="font-mono text-[0.9em]">text</code>{" "}
          column. Up to {count(maxRows)} rows per run.
        </p>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[5fr_7fr]">
        <Card>
          <CardHeader>
            <CardTitle>Texts</CardTitle>
            <span className="text-xs text-muted-foreground tabular">
              {count(rows.length)} {rows.length === 1 ? "row" : "rows"}
              {rows.length > maxRows && ` · first ${count(maxRows)} will run`}
            </span>
          </CardHeader>
          <CardContent>
            <label htmlFor="batch-text" className="sr-only">
              Texts, one per line
            </label>
            <Textarea
              id="batch-text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                const file = e.dataTransfer.files[0];
                setDragging(false);
                if (file) {
                  e.preventDefault();
                  loadFile(file);
                }
              }}
              placeholder={"One text per line, or drop a .csv / .txt file here"}
              className={cn(
                "max-h-[28rem] min-h-72 resize-y bg-card text-sm leading-relaxed",
                dragging && "border-ring ring-[3px] ring-ring/30",
              )}
            />
            {tooLong !== -1 && (
              <p className="flex gap-2 text-sm text-destructive">
                <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                Row {tooLong + 1} is longer than {count(maxChars)} characters. Shorten or split it.
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.txt,text/csv,text/plain"
                className="sr-only"
                tabIndex={-1}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) loadFile(file);
                  e.target.value = "";
                }}
              />
              <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={running}>
                <UploadIcon aria-hidden="true" />
                Upload CSV or TXT
              </Button>
              {!input && (
                <Button variant="ghost" onClick={() => setInput(BATCH_SAMPLE)}>
                  Use sample
                </Button>
              )}
              <div className="flex-1" />
              {running ? (
                <Button variant="outline" onClick={() => abort.current?.abort()}>
                  <XIcon aria-hidden="true" />
                  Cancel
                </Button>
              ) : (
                <Button onClick={start} disabled={!model || rows.length === 0 || tooLong !== -1}>
                  Run batch
                </Button>
              )}
            </div>
            {progress && (
              <div className="flex flex-col gap-1.5" role="status">
                <Progress value={(progress.done / progress.total) * 100} />
                <p className="flex items-center gap-2 text-xs text-muted-foreground tabular">
                  <LoaderCircleIcon className="size-3.5 animate-spin" aria-hidden="true" />
                  {progress.done === 0 && model?.status !== "ready"
                    ? `Loading ${model?.name}… the first run downloads the model.`
                    : `Analyzed ${count(progress.done)} of ${count(progress.total)}`}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Results</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={copyCsv} disabled={!run}>
                <CopyIcon aria-hidden="true" />
                Copy
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!run}
                onClick={() => downloadFile(`sentiment-${run?.model.name.toLowerCase().replace(/\s+/g, "-")}.csv`, exportRows())}
              >
                <DownloadIcon aria-hidden="true" />
                Download CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {error && (
              <p role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
                <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                {error}
              </p>
            )}
            {!run && !error && (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Run a batch to see the label split and every row&apos;s result.
              </p>
            )}
            {run && (
              <BatchResults
                run={run}
                filter={filter}
                onFilter={setFilter}
                lowConfidence={lowConfidence}
                stale={!!model && model.id !== run.model.id}
                currentModel={model?.name}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BatchResults({
  run,
  filter,
  onFilter,
  lowConfidence,
  stale,
  currentModel,
}: {
  run: BatchRun;
  filter: Filter;
  onFilter: (f: Filter) => void;
  lowConfidence: number;
  stale: boolean;
  currentModel?: string;
}) {
  const labels = run.model.labels;
  const total = run.results.length;
  const counts = labels.map((l) => run.results.filter((r) => r.label === l).length);
  const review = run.results.filter((r) => r.score < lowConfidence).length;
  const average = run.results.reduce((s, r) => s + r.score, 0) / Math.max(total, 1);

  const shown = run.results
    .map((r, i) => ({ ...r, index: i, text: run.texts[i] }))
    .filter((r) =>
      filter === "all" ? true : filter === "review" ? r.score < lowConfidence : r.label === filter,
    );

  const filters: [Filter, string][] = [
    ["all", `All ${count(total)}`],
    ...labels.map((l, i): [Filter, string] => [l, `${labelName(l)} ${count(counts[i])}`]),
    ["review", `Needs review ${count(review)}`],
  ];

  return (
    <div className="flex flex-col gap-5">
      {stale && (
        <p className="rounded-lg border bg-muted/60 px-3 py-2 text-sm text-muted-foreground">
          These results are from {run.model.name}. Run the batch again to use {currentModel}.
        </p>
      )}

      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        <Stat value={count(total)} label={`Texts · ${duration(run.latencyMs)}`} />
        <Stat value={pct(average)} label="Avg. confidence" />
        <Stat value={count(review)} label={`Below ${pct(lowConfidence, 0)} · review`} />
      </div>

      <section>
        <Eyebrow>Label distribution · {run.model.name}</Eyebrow>
        <div
          className="flex h-3.5 gap-0.5"
          role="img"
          aria-label={labels.map((l, i) => `${labelName(l)} ${counts[i]}`).join(", ")}
        >
          {labels.map((l, i) =>
            counts[i] ? (
              <Tooltip key={l}>
                <TooltipTrigger asChild>
                  <span
                    className="h-full first:rounded-l-[4px] last:rounded-r-[4px]"
                    style={{ flex: `${counts[i]} 1 0%`, background: labelColor(l) }}
                  />
                </TooltipTrigger>
                <TooltipContent>
                  {labelName(l)}: {count(counts[i])} ({pct(counts[i] / total)})
                </TooltipContent>
              </Tooltip>
            ) : null,
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {labels.map((l, i) => (
            <span key={l} className="inline-flex items-center gap-1.5 tabular">
              <Swatch label={l} />
              {labelName(l)} {count(counts[i])} · {pct(counts[i] / Math.max(total, 1))}
            </span>
          ))}
        </div>
      </section>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter rows">
        {filters.map(([key, name]) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => onFilter(key)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs transition-colors",
              filter === key
                ? "border-primary bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:text-foreground",
            )}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="max-h-[28rem] overflow-auto rounded-lg border">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-muted text-xs text-muted-foreground">
            <tr>
              <th className="w-px px-3 py-2 text-left font-medium">#</th>
              <th className="px-3 py-2 text-left font-medium">Text</th>
              <th className="px-3 py-2 text-left font-medium">Label</th>
              <th className="px-3 py-2 text-right font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                  No rows match this filter.
                </td>
              </tr>
            )}
            {shown.map((r) => (
              <tr key={r.index} className="border-t align-top">
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground tabular">{r.index + 1}</td>
                <td className="min-w-56 px-3 py-2 break-words">{r.text}</td>
                <td className="px-3 py-2">
                  <LabelPill label={r.label} />
                  {r.score < lowConfidence && (
                    <span className="mt-0.5 block text-[11px] text-warning">Review</span>
                  )}
                  {r.truncated && (
                    <span className="mt-0.5 block text-[11px] text-muted-foreground">Truncated</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs tabular">{pct(r.score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border px-3 py-2.5">
      <p className="text-xl font-semibold tracking-tight tabular">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
