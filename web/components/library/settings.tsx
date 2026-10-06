"use client";

import { ErrorBox, PageHeader, useOwnerData } from "@/components/library/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { admin } from "@/lib/library-admin";

const ENV: Record<string, string> = {
  engine: "RAG_ENGINE",
  model: "RAG_MODEL",
  embedding_model: "RAG_EMBEDDING_MODEL",
  store_name: "RAG_STORE_NAME",
  chunk_tokens: "RAG_CHUNK_TOKENS",
  chunk_overlap: "RAG_CHUNK_OVERLAP",
  top_k: "RAG_TOP_K",
  index_concurrency: "RAG_INDEX_CONCURRENCY",
  owner_auth: "LIBRARY_TOKEN",
};
const LABEL: Record<string, string> = {
  engine: "Search engine",
  model: "Answer model",
  embedding_model: "Embedding model",
  store_name: "Index name",
  store_id: "Index id",
  chunk_tokens: "Passage size (tokens)",
  chunk_overlap: "Passage overlap (tokens)",
  top_k: "Passages per question",
  index_concurrency: "Files indexed at once",
  owner_auth: "Owner access",
};

export function LibrarySettingsPage() {
  const { data, error, reload } = useOwnerData(admin.settings);
  return (
    <>
      <PageHeader
        title="Index settings"
        description={
          <>
            Read-only. Change them in <code className="font-mono text-xs">api/.env</code> and restart the API. Passage size
            applies to files indexed afterwards; re-index to update older ones.
          </>
        }
      />
      {error && <ErrorBox message={error} onRetry={reload} />}
      <div className="px-4 pb-10 sm:px-6">
        {!data && !error && <Skeleton className="h-72 w-full" />}
        {data && (
          <div className="overflow-hidden rounded-2xl border">
            <table className="w-full text-sm">
              <tbody>
                {Object.keys(LABEL).map((k) => (
                  <tr key={k} className="border-t first:border-t-0">
                    <th scope="row" className="w-1/2 px-4 py-2.5 text-left font-normal">
                      {LABEL[k]}
                      {ENV[k] && <span className="block font-mono text-[11px] text-muted-foreground">{ENV[k]}</span>}
                    </th>
                    <td className="px-4 py-2.5 text-right font-mono text-xs break-all">
                      {String(data[k as keyof typeof data] ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
