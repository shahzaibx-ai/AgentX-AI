"use client";

import {
  ChevronDownIcon,
  CloudIcon,
  HardDriveIcon,
  RefreshCwIcon,
  SparklesIcon,
  TriangleAlertIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import type { UseModels } from "@/hooks/use-models";
import { formatBytes } from "@/lib/helpers";

const AUTO = "auto";
const SEP = "::";

export function ModelPicker({ models }: { models: UseModels }) {
  const { data, loading, error, selection, effective, select, refresh } = models;

  if (loading && !data) return <Skeleton className="h-9 w-40" />;

  const local = data?.providers.find((p) => p.local);
  const cloud = data?.providers.filter((p) => !p.local) ?? [];
  const cloudReady = cloud.filter((p) => p.available && p.models.length);
  const cloudFailed = cloud.filter((p) => p.configured && !p.available);
  const cloudMissing = cloud.filter((p) => !p.configured);

  const value = selection ? `${selection.provider}${SEP}${selection.model}` : AUTO;
  const onChange = (v: string) => {
    if (v === AUTO) return select(null);
    const [provider, ...rest] = v.split(SEP);
    select({ provider, model: rest.join(SEP) });
  };

  const label = effective
    ? `${selection ? "" : "Auto · "}${effective.name}`
    : error
      ? "API offline"
      : "No models";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="max-w-[60vw] gap-1.5 px-2.5 text-[15px] font-semibold">
          {effective?.local === false ? (
            <CloudIcon className="text-muted-foreground" />
          ) : error ? (
            <TriangleAlertIcon className="text-destructive" />
          ) : (
            <HardDriveIcon className="text-muted-foreground" />
          )}
          <span className="truncate">{label}</span>
          <ChevronDownIcon className="text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        {error && (
          <p className="px-2 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          <DropdownMenuRadioItem value={AUTO} className="items-start">
            <SparklesIcon className="mt-0.5" />
            <span className="flex flex-col">
              <span>Auto</span>
              <span className="text-xs text-muted-foreground">
                Local model first, cloud if unavailable
              </span>
            </span>
          </DropdownMenuRadioItem>

          <DropdownMenuSeparator />
          <DropdownMenuLabel className="flex items-center gap-1.5">
            <HardDriveIcon className="size-3.5" /> Local · Ollama
          </DropdownMenuLabel>
          {local?.models.map((m) => (
            <DropdownMenuRadioItem key={m.id} value={`${m.provider}${SEP}${m.id}`}>
              <span className="truncate">{m.name}</span>
              <span className="ml-auto pl-2 text-xs text-muted-foreground">
                {[m.parameter_size, formatBytes(m.size_bytes)].filter(Boolean).join(" · ")}
              </span>
            </DropdownMenuRadioItem>
          ))}
          {local && !local.models.length && (
            <p className="px-2 pb-2 text-xs leading-5 text-muted-foreground">
              {local.available ? "No models installed. " : "Ollama isn't running. "}
              Run <code className="rounded bg-muted px-1 font-mono">ollama pull llama3.2</code>
              {cloudReady.length ? " — cloud models are used meanwhile." : "."}
            </p>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuLabel className="flex items-center gap-1.5">
            <CloudIcon className="size-3.5" /> Cloud (fallback)
          </DropdownMenuLabel>
          {cloudReady.map((p) => (
            <DropdownMenuSub key={p.id}>
              <DropdownMenuSubTrigger>
                {p.label}
                <span className="ml-auto text-xs text-muted-foreground">{p.models.length}</span>
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-80 w-72 overflow-y-auto">
                <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
                  {p.models.map((m) => (
                    <DropdownMenuRadioItem key={m.id} value={`${m.provider}${SEP}${m.id}`}>
                      <span className="truncate">{m.name}</span>
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          ))}
          {cloudFailed.map((p) => (
            <p key={p.id} className="px-2 py-1 text-xs text-muted-foreground">
              {p.label}: {p.error ?? "unavailable"}
            </p>
          ))}
          {!cloudReady.length && !cloudFailed.length && (
            <p className="px-2 pb-2 text-xs leading-5 text-muted-foreground">
              No cloud keys configured. Add one to <code className="font-mono">api/.env</code>.
            </p>
          )}
          {cloudMissing.length > 0 && cloudReady.length > 0 && (
            <p className="px-2 pb-1 text-xs text-muted-foreground">
              Not configured: {cloudMissing.map((p) => p.label).join(", ")}
            </p>
          )}
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            void refresh();
          }}
        >
          <RefreshCwIcon className={loading ? "animate-spin" : undefined} />
          Refresh models
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
