/** Owner-only Library API (the /library pages). */
import { jsonBody, ownerApi, type LibraryDocument, type CollectionInfo } from "@/lib/library";
import type { Citation } from "@/lib/types";

export interface Totals {
  by_status: Partial<Record<"queued" | "processing" | "indexed" | "failed", number>>;
  library_documents: number;
  library_size: number;
  chat_size: number;
  chat_files: number;
}

export interface Overview {
  totals: Totals;
  searches: Record<string, number>;
  queue: number;
  store: {
    id: string;
    active: number;
    pending: number;
    failed: number;
    size_bytes: number;
    embedding_model: string | null;
  } | null;
  store_error: string | null;
  activity: { at: number; actor: string; text: string }[];
}

export interface StorageInfo {
  totals: Totals;
  quota_bytes: number;
  data_dir: string;
  largest_chat_files: LibraryDocument[];
  chat_file_retention_days: number;
  chat_file_max_bytes: number;
  library_file_max_bytes: number;
}

export interface IndexSettings {
  engine: string;
  model: string;
  embedding_model: string;
  store_name: string;
  store_id: string | null;
  chunk_tokens: number;
  chunk_overlap: number;
  top_k: number;
  index_concurrency: number;
  owner_auth: string;
  now: string;
}

export interface TestResult {
  answer: string;
  cited_text: string;
  grounded: boolean;
  sources: Citation[];
  retrieval_queries: string[];
  model: string;
  seconds: number;
}

export type DocFilter = {
  query?: string;
  collection_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
};

export const admin = {
  overview: () => ownerApi<Overview>("/library/overview"),
  collections: () => ownerApi<CollectionInfo[]>("/library/collections"),
  createCollection: (name: string, description: string) =>
    ownerApi<CollectionInfo>("/library/collections", jsonBody({ name, description })),
  updateCollection: (id: string, name: string, description: string) =>
    ownerApi<CollectionInfo>(`/library/collections/${id}`, jsonBody({ name, description }, "PATCH")),
  deleteCollection: (id: string) =>
    ownerApi<{ deleted_documents: number }>(`/library/collections/${id}`, { method: "DELETE" }),
  documents: (f: DocFilter) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "") q.set(k, String(v));
    return ownerApi<{ documents: LibraryDocument[]; total: number }>(`/library/documents?${q}`);
  },
  document: (id: string) => ownerApi<LibraryDocument>(`/library/documents/${id}`),
  reindex: (id: string) =>
    ownerApi<LibraryDocument>(`/library/documents/${id}/reindex`, { method: "POST" }),
  deleteDocument: (id: string) => ownerApi<void>(`/library/documents/${id}`, { method: "DELETE" }),
  bulk: (action: "delete" | "reindex" | "move", ids: string[], collection_id?: string) =>
    ownerApi<{ done: string[]; failed: { id: string; reason: string }[] }>(
      "/library/documents/bulk",
      jsonBody({ action, ids, ...(collection_id ? { collection_id } : {}) }),
    ),
  test: (question: string, collection_ids: string[]) =>
    ownerApi<TestResult>("/library/test", jsonBody({ question, collection_ids })),
  storage: () => ownerApi<StorageInfo>("/library/storage"),
  settings: () => ownerApi<IndexSettings>("/library/settings"),
};

export function timeAgo(seconds: number): string {
  const diff = Date.now() / 1000 - seconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return new Date(seconds * 1000).toLocaleDateString();
}
