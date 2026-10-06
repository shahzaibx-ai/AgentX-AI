"use client";

import { ErrorBox, PageHeader, Stat, useOwnerData } from "@/components/library/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { admin, timeAgo } from "@/lib/library-admin";
import { formatSize } from "@/lib/library";

export function LibraryStorage() {
  const { data, error, reload } = useOwnerData(admin.storage);
  const used = data ? data.totals.library_size + data.totals.chat_size : 0;
  const pct = data ? Math.min(100, (used / data.quota_bytes) * 100) : 0;
  return (
    <>
      <PageHeader title="Storage" description="Originals are kept on the API server so people can open what an answer cited." />
      {error && <ErrorBox message={error} onRetry={reload} />}
      {!data && !error && (
        <div className="px-4 sm:px-6">
          <Skeleton className="h-48 w-full" />
        </div>
      )}
      {data && (
        <div className="flex flex-col gap-4 px-4 pb-10 sm:px-6">
          <section className="rounded-2xl border bg-card p-4">
            <div className="flex items-baseline gap-2">
              <h2 className="text-sm font-medium">Used</h2>
              <span className="text-sm tabular-nums">
                {formatSize(used)} of {formatSize(data.quota_bytes)}
              </span>
            </div>
            <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-muted" role="img" aria-label={`${pct.toFixed(1)}% used`}>
              <div className="bg-foreground" style={{ width: `${(data.totals.library_size / data.quota_bytes) * 100}%` }} />
              <div className="bg-foreground/40" style={{ width: `${(data.totals.chat_size / data.quota_bytes) * 100}%` }} />
            </div>
            <p className="mt-2 flex gap-4 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <i className="size-2 rounded-full bg-foreground" /> Library {formatSize(data.totals.library_size)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <i className="size-2 rounded-full bg-foreground/40" /> Chat files {formatSize(data.totals.chat_size)}
              </span>
            </p>
            <p className="mt-3 font-mono text-xs break-all text-muted-foreground">{data.data_dir}</p>
          </section>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Library file limit" value={formatSize(data.library_file_max_bytes)} />
            <Stat label="Chat file limit" value={formatSize(data.chat_file_max_bytes)} />
            <Stat
              label="Chat files kept for"
              value={data.chat_file_retention_days ? `${data.chat_file_retention_days} days` : "Forever"}
              sub="Then removed from storage and the index"
            />
          </div>
          <section className="rounded-2xl border bg-card p-4">
            <h2 className="mb-2 text-sm font-medium">Largest chat files</h2>
            {data.largest_chat_files.length ? (
              <ul className="divide-y text-sm">
                {data.largest_chat_files.map((d) => (
                  <li key={d.id} className="flex gap-3 py-2">
                    <span className="min-w-0 flex-1 truncate">{d.title}</span>
                    <span className="shrink-0 tabular-nums">{formatSize(d.size)}</span>
                    <span className="hidden w-32 shrink-0 text-right text-xs text-muted-foreground sm:block">
                      {d.expires_at ? `removed ${new Date(d.expires_at * 1000).toLocaleDateString()}` : timeAgo(d.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No files added in chats.</p>
            )}
          </section>
        </div>
      )}
    </>
  );
}
