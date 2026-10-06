"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ErrorBox, PageHeader, Stat, useLibrary, useOwnerData } from "@/components/library/shell";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { admin, timeAgo } from "@/lib/library-admin";
import { formatSize } from "@/lib/library";
import { cn } from "@/lib/utils";

function SearchChart({ data }: { data: Record<string, number> }) {
  const [table, setTable] = useState(false);
  const days = Object.entries(data);
  const max = Math.max(1, ...days.map(([, n]) => n));
  const total = days.reduce((s, [, n]) => s + n, 0);
  const label = (d: string) =>
    new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return (
    <section className="rounded-2xl border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-sm font-medium">Searches, last 14 days</h2>
        <span className="text-xs text-muted-foreground tabular-nums">{total} total</span>
        <Button size="sm" variant="ghost" className="ml-auto h-7 text-xs" onClick={() => setTable((t) => !t)}>
          {table ? "Show chart" : "Show table"}
        </Button>
      </div>
      {table ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="py-1 font-normal">Day</th>
              <th className="py-1 text-right font-normal">Searches</th>
            </tr>
          </thead>
          <tbody>
            {days.map(([d, n]) => (
              <tr key={d} className="border-t">
                <td className="py-1">{label(d)}</td>
                <td className="py-1 text-right tabular-nums">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="flex h-36 items-end gap-1" role="img" aria-label={`${total} searches in the last 14 days`}>
          {days.map(([d, n], i) => (
            <div key={d} className="flex h-full min-w-0 flex-1 flex-col justify-end gap-1" title={`${label(d)}: ${n}`}>
              <div
                className={cn("rounded-t-sm", n ? "bg-foreground/80" : "bg-muted")}
                style={{ height: `${n ? Math.max(4, (n / max) * 100) : 2}%` }}
              />
              <span className="truncate text-center text-[10px] text-muted-foreground">
                {i % 2 === 1 || i === days.length - 1 ? new Date(`${d}T00:00:00`).getDate() : " "}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function LibraryOverview() {
  const { collections } = useLibrary();
  const { data, error, reload } = useOwnerData(admin.overview);

  // Refresh while indexing is in progress.
  const busy = !!data && (data.queue > 0 || !!data.totals.by_status.processing);
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(reload, 4000);
    return () => clearInterval(t);
  }, [busy, reload]);

  const s = data?.totals.by_status ?? {};
  return (
    <>
      <PageHeader
        title="Overview"
        description="What's in the Library, how it's used and whether indexing is healthy."
        actions={
          <Button asChild>
            <Link href="/library/documents?upload=1">Upload documents</Link>
          </Button>
        }
      />
      {error && <ErrorBox message={error} onRetry={reload} />}
      {!data && !error && (
        <div className="grid grid-cols-2 gap-3 px-4 sm:px-6 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}
      {data && (
        <div className="flex flex-col gap-4 px-4 pb-10 sm:px-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat
              label="Documents"
              value={data.totals.library_documents}
              sub={`${collections.length} collections`}
            />
            <Stat label="Ready to search" value={s.indexed ?? 0} sub={`${(s.queued ?? 0) + (s.processing ?? 0)} indexing`} />
            <Stat
              label="Need attention"
              value={
                s.failed ? (
                  <Link href="/library/documents?status=failed" className="text-destructive underline-offset-4 hover:underline">
                    {s.failed}
                  </Link>
                ) : (
                  0
                )
              }
              sub="Failed to index"
            />
            <Stat
              label="Stored"
              value={formatSize(data.totals.library_size + data.totals.chat_size)}
              sub={`${data.totals.chat_files} chat files · ${formatSize(data.totals.chat_size)}`}
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <SearchChart data={data.searches} />
            <section className="rounded-2xl border bg-card p-4">
              <h2 className="mb-3 text-sm font-medium">Index health</h2>
              {data.store_error ? (
                <p className="text-sm text-destructive">{data.store_error}</p>
              ) : data.store ? (
                <dl className="grid grid-cols-2 gap-y-2 text-sm">
                  <dt className="text-muted-foreground">Searchable</dt>
                  <dd className="text-right tabular-nums">{data.store.active}</dd>
                  <dt className="text-muted-foreground">Pending</dt>
                  <dd className="text-right tabular-nums">{data.store.pending}</dd>
                  <dt className="text-muted-foreground">Failed</dt>
                  <dd className="text-right tabular-nums">{data.store.failed}</dd>
                  <dt className="text-muted-foreground">Index size</dt>
                  <dd className="text-right tabular-nums">{formatSize(data.store.size_bytes)}</dd>
                  <dt className="text-muted-foreground">Queue</dt>
                  <dd className="text-right tabular-nums">{data.queue}</dd>
                  {data.store.embedding_model && (
                    <>
                      <dt className="text-muted-foreground">Embeddings</dt>
                      <dd className="truncate text-right font-mono text-xs" title={data.store.embedding_model}>
                        {data.store.embedding_model}
                      </dd>
                    </>
                  )}
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">The index is created with the first upload.</p>
              )}
            </section>
          </div>
          <section className="rounded-2xl border bg-card p-4">
            <h2 className="mb-2 text-sm font-medium">Recent activity</h2>
            {data.activity.length ? (
              <ul className="divide-y text-sm">
                {data.activity.map((a, i) => (
                  <li key={i} className="flex gap-3 py-2">
                    <span className="min-w-0 flex-1 break-words">{a.text}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {a.actor} · {timeAgo(a.at)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Nothing yet. Create a collection and upload documents.</p>
            )}
          </section>
        </div>
      )}
    </>
  );
}
