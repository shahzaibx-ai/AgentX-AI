"use client";

import { useCallback, useState, type FormEvent } from "react";
import { CheckCircle2Icon, CircleAlertIcon } from "lucide-react";

import { Markdown } from "@/components/chat/markdown";
import { SourcePanel, SourcesList } from "@/components/files/sources";
import { PageHeader, useLibrary } from "@/components/library/shell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { admin, type TestResult } from "@/lib/library-admin";
import { cn } from "@/lib/utils";

export function LibraryTest() {
  const { handleError, collections } = useLibrary();
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const onCite = useCallback((n: number) => setOpen(n), []);

  const run = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await admin.test(question.trim(), picked));
    } catch (err) {
      setResult(null);
      setError(handleError(err));
    } finally {
      setBusy(false);
    }
  };
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <>
      <PageHeader
        title="Retrieval test"
        description="Ask like a person would and check the answer and the passages it found. Tests count as searches."
      />
      <div className="grid gap-4 px-4 pb-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <form onSubmit={run} className="flex flex-col gap-3 rounded-2xl border bg-card p-4">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Question</span>
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="How many unused vacation days carry over?"
            />
          </label>
          <fieldset className="text-sm">
            <legend className="mb-1.5 font-medium">
              Collections <span className="font-normal text-muted-foreground">(none picked = all)</span>
            </legend>
            <div className="flex flex-wrap gap-1.5">
              {collections.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  aria-pressed={picked.includes(c.id)}
                  onClick={() => toggle(c.id)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    picked.includes(c.id) ? "border-foreground bg-foreground text-background" : "hover:bg-muted",
                  )}
                >
                  {c.name}
                </button>
              ))}
              {!collections.length && <span className="text-muted-foreground">No collections yet.</span>}
            </div>
          </fieldset>
          <Button type="submit" disabled={!question.trim() || busy || !collections.length} className="self-start">
            {busy ? "Searching…" : "Run test"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
        <section className="rounded-2xl border bg-card p-4" aria-live="polite">
          {!result ? (
            <p className="text-sm text-muted-foreground">The answer and its sources appear here.</p>
          ) : (
            <>
              <p className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {result.grounded ? (
                  <span className="inline-flex items-center gap-1 text-success">
                    <CheckCircle2Icon className="size-3.5" /> Answered from documents
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <CircleAlertIcon className="size-3.5" /> Not found in documents
                  </span>
                )}
                <span>{result.seconds}s</span>
                <span className="font-mono">{result.model}</span>
                <span>{result.sources.length} passages</span>
              </p>
              <Markdown content={result.cited_text} citations={result.sources.length} onCite={onCite} />
              <SourcesList sources={result.sources} active={open} onOpen={onCite} />
              {result.retrieval_queries.length > 0 && (
                <p className="mt-3 text-xs text-muted-foreground">
                  Searched for: {result.retrieval_queries.map((q) => `“${q}”`).join(", ")}
                </p>
              )}
              <SourcePanel
                source={result.sources.find((s) => s.number === open) ?? null}
                total={result.sources.length}
                onClose={() => setOpen(null)}
              />
            </>
          )}
        </section>
      </div>
    </>
  );
}
