"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MenuIcon, RefreshCwIcon, ServerCrashIcon } from "lucide-react";
import { toast } from "sonner";

import { AnalyzeView, type AnalysisState } from "@/components/studio/analyze-view";
import { BatchView } from "@/components/studio/batch-view";
import { ModelView } from "@/components/studio/model-view";
import { Sidebar } from "@/components/studio/sidebar";
import { ApiStatus, ModelPicker, ThemeToggle } from "@/components/studio/topbar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useHistory } from "@/hooks/use-history";
import { useModels } from "@/hooks/use-models";
import { ApiError, api, errorMessage } from "@/lib/api";
import type { HistoryEntry } from "@/lib/types";

const VIEWS = ["analyze", "batch", "model"] as const;
type View = (typeof VIEWS)[number];
const isView = (value: string): value is View => (VIEWS as readonly string[]).includes(value);

export function StudioApp() {
  const models = useModels();
  const recent = useHistory();
  const [view, setView] = useState<View>("analyze");
  const [navOpen, setNavOpen] = useState(false);
  const [text, setText] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisState>({ phase: "idle" });
  const request = useRef<AbortController | null>(null);
  const lastRun = useRef<{ text: string; model: string } | null>(null);

  const { selected, setStatus, refresh } = models;

  // ---------------------------------------------------------------- views (#batch, #model)
  useEffect(() => {
    const fromHash = () => {
      const hash = window.location.hash.slice(1);
      setView(isView(hash) ? hash : "analyze");
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);

  const changeView = useCallback((next: string) => {
    if (!isView(next)) return;
    setView(next);
    const url = next === "analyze" ? window.location.pathname : `#${next}`;
    window.history.replaceState(null, "", url);
  }, []);

  // ---------------------------------------------------------------- analysis
  const analyze = useCallback(
    async (value?: string, { save = true }: { save?: boolean } = {}) => {
      const input = value ?? text;
      if (!input.trim()) return;
      if (!selected) {
        toast.error(models.error ?? "No model is available yet.");
        return;
      }
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      // Recorded now (not on success) so a model switch mid-request re-runs this text.
      lastRun.current = { text: input, model: selected.id };
      setAnalysis({ phase: "running", modelReady: selected.status === "ready" });
      if (selected.status !== "ready") setStatus(selected.id, "loading");

      try {
        const result = await api.predict(
          { text: input, model: selected.id, explain: true },
          controller.signal,
        );
        setAnalysis({ phase: "done", result });
        setStatus(selected.id, "ready");
        if (save) {
          recent.add({ text: input, label: result.label, score: result.score, model: selected.id });
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setAnalysis({ phase: "error", message: errorMessage(err) });
        // Resync model status: the API may be down, or the model may have failed to load.
        if (err instanceof ApiError && (err.status === 0 || err.status >= 500)) void refresh();
      } finally {
        if (request.current === controller) request.current = null;
      }
    },
    [text, selected, models.error, setStatus, refresh, recent],
  );

  // When the model changes, re-run the last text with the new model.
  const analyzeRef = useRef(analyze);
  analyzeRef.current = analyze;
  const selectedId = selected?.id;
  useEffect(() => {
    const last = lastRun.current;
    if (selectedId && last && last.model !== selectedId) {
      void analyzeRef.current(last.text, { save: false });
    }
  }, [selectedId]);

  // ---------------------------------------------------------------- sidebar actions
  const newAnalysis = () => {
    request.current?.abort();
    lastRun.current = null;
    setText("");
    setAnalysis({ phase: "idle" });
    changeView("analyze");
    setNavOpen(false);
    requestAnimationFrame(() => document.getElementById("analyze-text")?.focus());
  };

  const openEntry = (entry: HistoryEntry) => {
    setNavOpen(false);
    changeView("analyze");
    setText(entry.text);
    const known = models.data?.models.some((m) => m.id === entry.model);
    if (known && entry.model !== selected?.id) {
      // The model-change effect re-runs the text with the entry's model.
      lastRun.current = { text: entry.text, model: "" };
      models.select(entry.model);
    } else {
      void analyze(entry.text, { save: false });
    }
  };

  const clearHistory = () => {
    const undo = recent.clear();
    toast("History cleared.", { action: { label: "Undo", onClick: undo } });
  };

  const sidebar = (
    <Sidebar
      history={recent.entries}
      models={models.data?.models ?? []}
      apiOnline={!models.error}
      onNew={newAnalysis}
      onOpen={openEntry}
      onClear={clearHistory}
    />
  );

  const offline = models.error !== null;

  return (
    <div className="flex h-dvh">
      <aside className="hidden w-72 shrink-0 border-r md:block">{sidebar}</aside>
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" showClose={false} className="w-72 p-0 md:hidden">
          <SheetTitle className="sr-only">History</SheetTitle>
          <SheetDescription className="sr-only">Your recent analyses</SheetDescription>
          {sidebar}
        </SheetContent>
      </Sheet>

      <Tabs value={view} onValueChange={changeView} className="flex min-w-0 flex-1 flex-col gap-0">
        <header className="flex flex-wrap items-center gap-2 border-b bg-card px-4 pt-[calc(0.625rem+env(safe-area-inset-top))] pb-2.5 sm:px-5 md:flex-nowrap">
          <Button
            variant="ghost"
            size="icon"
            className="-ml-2 text-muted-foreground md:hidden"
            aria-label="Open history"
            onClick={() => setNavOpen(true)}
          >
            <MenuIcon aria-hidden="true" />
          </Button>
          <div className="min-w-0 flex-1 md:flex-none">
            <ModelPicker
              models={models.data?.models ?? []}
              value={selected?.id}
              onChange={models.select}
            />
          </div>
          <div className="hidden flex-1 md:block" />
          <ApiStatus error={models.error} model={selected} device={models.data?.device} />
          <ThemeToggle />
          <TabsList className="order-last w-full md:order-none md:ml-1 md:w-auto">
            <TabsTrigger value="analyze">Analyze</TabsTrigger>
            <TabsTrigger value="batch">Batch</TabsTrigger>
            <TabsTrigger value="model">Model</TabsTrigger>
          </TabsList>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-[1180px] flex-col gap-5 px-4 pt-6 pb-[max(2.5rem,env(safe-area-inset-bottom))] sm:px-6">
            {offline && (
              <div
                role="alert"
                className="flex flex-wrap items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4"
              >
                <ServerCrashIcon className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
                <div className="min-w-0 flex-1 text-sm">
                  <p className="font-medium">Can&apos;t reach the API</p>
                  <p className="text-muted-foreground">
                    Start it with <code className="font-mono">cd api && uv run fastapi dev</code>. This
                    page reconnects on its own.
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => void refresh()}>
                  <RefreshCwIcon aria-hidden="true" />
                  Retry now
                </Button>
              </div>
            )}

            <TabsContent value="analyze" forceMount className="data-[state=inactive]:hidden">
              <AnalyzeView
                text={text}
                onTextChange={setText}
                onAnalyze={(value) => void analyze(value)}
                analysis={analysis}
                model={selected}
                models={models.data?.models ?? []}
                limits={models.data?.limits ?? null}
              />
            </TabsContent>
            <TabsContent value="batch" forceMount className="data-[state=inactive]:hidden">
              <BatchView
                model={selected}
                limits={models.data?.limits ?? null}
                onModelReady={(id) => setStatus(id, "ready")}
              />
            </TabsContent>
            <TabsContent value="model" forceMount className="data-[state=inactive]:hidden">
              <ModelView
                data={models.data}
                selected={selected}
                onSelect={(id) => {
                  models.select(id);
                  toast(`Using ${models.data?.models.find((m) => m.id === id)?.name ?? id}.`);
                }}
                onStatus={setStatus}
                onRefresh={() => void refresh()}
              />
            </TabsContent>
          </div>
        </main>
      </Tabs>
    </div>
  );
}
