/**
 * Files in chat and the Library: API calls and shared helpers.
 *
 * Chat files need no login. Library management sends the owner token
 * (LIBRARY_TOKEN on the API) kept in this tab's sessionStorage.
 */
import { API_BASE, ApiError, errorMessage } from "@/lib/api";

export interface LibraryLimits {
  chat_file_max_bytes: number;
  chat_files_per_message: number;
  library_file_max_bytes: number;
  chat_file_retention_days: number;
  extensions: string[];
}

export interface CollectionInfo {
  id: string;
  name: string;
  description: string;
  documents: number;
  size: number;
  created_at: number;
  updated_at: number;
}

export interface LibraryConfig {
  enabled: boolean;
  reason: string | null;
  engine: string;
  /** Shown to people, e.g. "Gemini File Search". */
  label: string;
  /** True when files and questions stay on your servers. */
  local: boolean;
  model: string;
  owner_auth: "open" | "token" | "disabled";
  limits: LibraryLimits;
  collections: CollectionInfo[];
}

export type DocStatus = "queued" | "processing" | "indexed" | "failed";

export interface LibraryDocument {
  id: string;
  kind: "library" | "chat";
  title: string;
  filename: string;
  ext: string;
  mime: string;
  size: number;
  status: DocStatus;
  step: string;
  error: string;
  collection_id: string | null;
  collection: string | null;
  chat_id: string | null;
  uploaded_by: string;
  uses: number;
  engine: string;
  created_at: number;
  updated_at: number;
  indexed_at: number | null;
  expires_at: number | null;
  /** Upload only: the same file was already in this chat and this is that copy. */
  reused?: boolean;
}

export const PHOTO_EXT = /\.(jpe?g|png|webp|gif|hei[cf])$/i;

export function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i > 0 ? name.slice(i).toLowerCase() : "";
}

/** Short label for a file-type badge: ".docx" → "DOCX". */
export function typeLabel(ext: string): string {
  return (ext.replace(".", "") || "file").toUpperCase().slice(0, 4);
}

const oneDecimal = (n: number) => n.toFixed(1).replace(/\.0$/, "");

export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${oneDecimal(bytes / 1024 ** 3)} GB`;
  if (bytes >= 1024 ** 2) return `${oneDecimal(bytes / 1024 ** 2)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export const fileUrl = (id: string) => `${API_BASE}/files/${id}/content`;

// ------------------------------------------------------------------ owner token
const TOKEN_KEY = "assistant.library.token";

export function getOwnerToken(): string {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setOwnerToken(token: string) {
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: the token lasts until reload */
  }
}

async function request<T>(path: string, init: RequestInit = {}, owner = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (owner) {
    const token = getOwnerToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init, headers });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the AI server. Make sure the API is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const ownerApi = <T>(path: string, init: RequestInit = {}) => request<T>(path, init, true);

export function jsonBody(body: unknown, method = "POST"): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

// ------------------------------------------------------------------ chat files
export const fetchLibraryConfig = (signal?: AbortSignal) =>
  request<LibraryConfig>("/library/config", { signal });

export const getChatFile = (id: string, signal?: AbortSignal) =>
  request<LibraryDocument>(`/files/${id}`, { signal });

export const deleteChatFile = (id: string) =>
  request<void>(`/files/${id}`, { method: "DELETE" }).catch(() => undefined);

/** Upload with progress (fetch can't report upload progress). */
export function uploadChatFile(
  file: File,
  chatId: string,
  onProgress: (fraction: number) => void,
): { promise: Promise<LibraryDocument>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<LibraryDocument>((resolve, reject) => {
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("chat_id", chatId);
    xhr.open("POST", `${API_BASE}/files`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: { detail?: unknown } & Partial<LibraryDocument> = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as LibraryDocument);
      const detail =
        typeof body.detail === "string"
          ? body.detail
          : xhr.status === 413
            ? `${file.name} is too large.`
            : xhr.status >= 500 || xhr.status === 0
              ? "Can't reach the AI server. Make sure the API is running."
              : `Upload failed (${xhr.status})`;
      reject(new ApiError(detail, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Upload failed: the connection dropped."));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

/** Upload several documents to a collection (owner). */
export function uploadDocuments(
  files: File[],
  collectionId: string,
  replace: boolean,
  onProgress: (fraction: number) => void,
): Promise<{
  accepted: LibraryDocument[];
  rejected: { filename: string; reason: string; duplicate: boolean }[];
}> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    form.append("collection_id", collectionId);
    form.append("replace", String(replace));
    xhr.open("POST", `${API_BASE}/library/documents`);
    const token = getOwnerToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as never);
      reject(
        new ApiError(
          typeof body.detail === "string" ? body.detail : `Upload failed (${xhr.status})`,
          xhr.status,
        ),
      );
    };
    xhr.onerror = () => reject(new ApiError("Upload failed: the connection dropped."));
    xhr.send(form);
  });
}
