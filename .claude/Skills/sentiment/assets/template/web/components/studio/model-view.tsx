"use client";

import { useState } from "react";
import { ExternalLinkIcon, LoaderCircleIcon, TriangleAlertIcon } from "lucide-react";
import { toast } from "sonner";

import { LabelPill } from "@/components/studio/label-pill";
import { StatusDot, statusText } from "@/components/studio/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";
import { count, pct } from "@/lib/format";
import type { ModelInfo, ModelsResponse, ModelStatus } from "@/lib/types";

const ENDPOINTS = [
  ["GET", "/api/health", "Service status, device and each model's load state"],
  ["GET", "/api/models", "Model catalog, limits and the default model"],
  ["POST", "/api/models/load", "Load a model now instead of on first use"],
  ["POST", "/api/predict", "One text: label, probabilities, tokens, word influence"],
  ["POST", "/api/predict/batch", "Up to the batch limit of texts in one request"],
] as const;

export function ModelView({
  data,
  selected,
  onSelect,
  onStatus,
  onRefresh,
}: {
  data: ModelsResponse | null;
  selected: ModelInfo | null;
  onSelect: (id: string) => void;
  onStatus: (id: string, status: ModelStatus, error?: string | null) => void;
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  async function load(model: ModelInfo) {
    setBusy(model.id);
    onStatus(model.id, "loading");
    try {
      await api.loadModel(model.id);
      onStatus(model.id, "ready");
      toast(`${model.name} is ready.`);
    } catch (err) {
      const message = errorMessage(err);
      onStatus(model.id, "error", message);
      toast.error(message);
      onRefresh(); // the server's own status is the truth (it may still be loading)
    } finally {
      setBusy(null);
    }
  }

  if (!data || !selected) {
    return <p className="py-16 text-center text-muted-foreground">Connect the API to see model details.</p>;
  }
  const limits = data.limits;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">{selected.name}</h1>
        <p className="mt-1 max-w-[65ch] text-muted-foreground">{selected.description}</p>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Model card</CardTitle>
            <Badge variant="outline" className="font-mono font-normal">
              {selected.architecture}
            </Badge>
          </CardHeader>
          <CardContent>
            <Details
              rows={[
                [
                  "Hugging Face",
                  <a
                    key="hf"
                    href={`https://huggingface.co/${selected.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[13px] break-all underline-offset-4 hover:underline"
                  >
                    {selected.id}
                    <ExternalLinkIcon className="size-3.5 shrink-0" aria-hidden="true" />
                  </a>,
                ],
                ["Revision", <span key="rev" className="font-mono text-[13px]">{selected.revision}</span>],
                ["Domain", selected.domain],
                ["Parameters", selected.parameters],
                [
                  "Labels",
                  <span key="labels" className="flex flex-wrap gap-x-3 gap-y-1">
                    {selected.labels.map((l) => (
                      <LabelPill key={l} label={l} />
                    ))}
                  </span>,
                ],
                ["Languages", selected.languages],
                ["Weights", "safetensors (pickled .bin files are never loaded)"],
              ]}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Runtime</CardTitle>
            <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <StatusDot status={selected.status} />
              {statusText(selected.status)}
            </span>
          </CardHeader>
          <CardContent>
            <Details
              rows={[
                ["Framework", "PyTorch 2.2 · Transformers 4.57"],
                ["Device", <span key="d" className="font-mono text-[13px]">{data.device}</span>],
                ["Max sequence", `${limits.max_length} tokens · longer text is truncated`],
                ["Batch size", `${limits.batch_size} texts per forward pass`],
                ["Limits", `${count(limits.max_text_chars)} characters per text · ${count(limits.max_batch_items)} texts per batch`],
                [
                  "Explanations",
                  limits.explain_steps > 0
                    ? `Integrated gradients, ${limits.explain_steps} steps`
                    : "Off",
                ],
                ["Review flag", `Top probability below ${pct(limits.low_confidence, 0)}`],
              ]}
            />
            {selected.status === "error" && selected.error && (
              <p className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
                <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                {selected.error}
              </p>
            )}
            {selected.status !== "ready" && (
              <Button
                variant="outline"
                className="self-start"
                disabled={busy !== null || selected.status === "loading"}
                onClick={() => load(selected)}
              >
                {(busy === selected.id || selected.status === "loading") && (
                  <LoaderCircleIcon className="animate-spin" aria-hidden="true" />
                )}
                {selected.status === "error" ? "Try loading again" : "Load now"}
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All models</CardTitle>
          <span className="text-xs text-muted-foreground">Models load on first use and stay in memory</span>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-muted text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Model</th>
                <th className="px-4 py-2 text-left font-medium">Domain</th>
                <th className="px-4 py-2 text-left font-medium">Labels</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.models.map((m) => (
                <tr key={m.id} className="border-t">
                  <td className="px-4 py-3">
                    <p className="font-medium">
                      {m.name}
                      {m.default && <span className="ml-2 text-xs font-normal text-muted-foreground">default</span>}
                    </p>
                    <p className="font-mono text-xs break-all text-muted-foreground">{m.id}</p>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{m.domain}</td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                    {m.labels.length === 5 ? "1–5 stars" : m.labels.join(" / ")}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="inline-flex items-center gap-2">
                      <StatusDot status={m.status} />
                      {statusText(m.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <div className="flex justify-end gap-2">
                      {m.status !== "ready" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy !== null || m.status === "loading"}
                          onClick={() => load(m)}
                        >
                          {busy === m.id && <LoaderCircleIcon className="animate-spin" aria-hidden="true" />}
                          Load
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={m.id === selected.id}
                        onClick={() => onSelect(m.id)}
                      >
                        {m.id === selected.id ? "In use" : "Use"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API</CardTitle>
          <span className="text-xs text-muted-foreground">
            Interactive docs at <span className="font-mono">http://localhost:8000/docs</span> (development)
          </span>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <tbody>
              {ENDPOINTS.map(([method, path, what]) => (
                <tr key={path} className="border-t first:border-t-0">
                  <td className="w-px px-4 py-2.5 font-mono text-xs font-medium">{method}</td>
                  <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap">{path}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Details({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-y-3">
      {rows.map(([term, value]) => (
        <div key={term} className="contents">
          <dt className="text-muted-foreground">{term}</dt>
          <dd className="mb-2 min-w-0 sm:mb-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
