"use client";

import { AudioWaveformIcon, PlusIcon } from "lucide-react";

import { LabelPill } from "@/components/studio/label-pill";
import { StatusDot } from "@/components/studio/status";
import { Button } from "@/components/ui/button";
import { APP_CONFIG } from "@/lib/config";
import { pct, timeAgo } from "@/lib/format";
import type { HistoryEntry, ModelInfo } from "@/lib/types";

export function Sidebar({
  history,
  models,
  apiOnline,
  onNew,
  onOpen,
  onClear,
}: {
  history: HistoryEntry[];
  models: ModelInfo[];
  apiOnline: boolean;
  onNew: () => void;
  onOpen: (entry: HistoryEntry) => void;
  onClear: () => void;
}) {
  const nameOf = (id: string) => models.find((m) => m.id === id)?.name ?? id.split("/").pop();

  return (
    <div className="flex h-full flex-col gap-3 bg-sidebar px-3 pt-[calc(0.875rem+env(safe-area-inset-top))] pb-3">
      <div className="flex items-center gap-2.5 px-1.5 pb-1">
        <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
          <AudioWaveformIcon className="size-4" aria-hidden="true" />
        </span>
        <div className="leading-tight">
          <p className="text-[15px] font-semibold tracking-tight">{APP_CONFIG.appName}</p>
          <p className="font-mono text-[11px] text-muted-foreground">PyTorch · Transformers</p>
        </div>
      </div>

      <Button variant="outline" className="justify-center" onClick={onNew}>
        <PlusIcon aria-hidden="true" />
        New analysis
      </Button>

      <div className="flex items-center justify-between px-2 pt-1">
        <h2 className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
          Recent
        </h2>
        {history.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="rounded px-1 text-xs text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        )}
      </div>

      <nav aria-label="Recent analyses" className="-mx-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-1">
        {history.length === 0 ? (
          <p className="px-2 py-1 text-sm text-muted-foreground">Texts you analyze appear here.</p>
        ) : (
          history.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => onOpen(entry)}
              className="flex w-full flex-col gap-1 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-sidebar-accent focus-visible:bg-sidebar-accent focus-visible:outline-none"
            >
              <span className="truncate text-[13px]">{entry.text}</span>
              <span className="flex min-w-0 items-center gap-2 text-[11px] text-muted-foreground">
                <LabelPill label={entry.label} className="text-[11px] font-normal text-foreground" />
                <span className="tabular">{pct(entry.score, 0)}</span>
                <span className="truncate">{nameOf(entry.model)}</span>
                <span className="ml-auto shrink-0">{timeAgo(entry.at)}</span>
              </span>
            </button>
          ))
        )}
      </nav>

      <div className="flex items-center gap-2.5 border-t px-1.5 pt-3">
        <span className="grid size-8 place-items-center rounded-full bg-primary text-[13px] font-semibold text-primary-foreground">
          {APP_CONFIG.user.name.charAt(0)}
        </span>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-[13px] font-medium">{APP_CONFIG.user.name}</p>
          <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <StatusDot status={apiOnline ? "ready" : "offline"} className="size-1.5" />
            {apiOnline ? "API connected" : "API offline"}
          </p>
        </div>
      </div>
    </div>
  );
}
