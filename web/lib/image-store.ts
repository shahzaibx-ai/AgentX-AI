/**
 * Photos live in IndexedDB (localStorage is too small and only holds strings).
 * Chat history keeps just the metadata (`ChatImage`) and refers to photos by id.
 * When IndexedDB is unavailable (some private windows) photos are kept in
 * memory for this tab only.
 */

const DB_NAME = "assistant.images";
const STORE = "images";

interface StoredImage {
  id: string;
  blob: Blob;
  createdAt: number;
}

const memory = new Map<string, StoredImage>();
const urls = new Map<string, string>();
let dbPromise: Promise<IDBDatabase | null> | null = null;

function openDb(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") return resolve(null);
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return dbPromise;
}

function run<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T | undefined> {
  return openDb().then(
    (db) =>
      new Promise<T | undefined>((resolve, reject) => {
        if (!db) return resolve(undefined);
        const tx = db.transaction(STORE, mode);
        const req = fn(tx.objectStore(STORE));
        tx.oncomplete = () => resolve(req.result);
        tx.onerror = () => reject(tx.error ?? new Error("Couldn't save the photo."));
        tx.onabort = () => reject(tx.error ?? new Error("Couldn't save the photo."));
      }),
  );
}

export async function saveImage(id: string, blob: Blob): Promise<void> {
  const record: StoredImage = { id, blob, createdAt: Date.now() };
  try {
    const db = await openDb();
    if (!db) throw new Error("IndexedDB is not available");
    await run("readwrite", (s) => s.put(record));
  } catch (err) {
    // Usually the storage quota or a private window. The photo still works until the tab closes.
    console.warn("Photo kept in memory only:", err);
    memory.set(id, record);
  }
}

export async function loadImage(id: string): Promise<Blob | null> {
  const cached = memory.get(id);
  if (cached) return cached.blob;
  try {
    const record = await run<StoredImage>("readonly", (s) => s.get(id) as IDBRequest<StoredImage>);
    return record?.blob ?? null;
  } catch {
    return null;
  }
}

export async function deleteImage(id: string): Promise<void> {
  memory.delete(id);
  const url = urls.get(id);
  if (url) {
    URL.revokeObjectURL(url);
    urls.delete(id);
  }
  try {
    await run("readwrite", (s) => s.delete(id));
  } catch {
    /* already gone */
  }
}

/** Reuse a preview URL made while attaching, so a sent photo shows without reloading it. */
export function rememberUrl(id: string, url: string) {
  const old = urls.get(id);
  if (old && old !== url) URL.revokeObjectURL(old);
  urls.set(id, url);
}

/** A cached object URL, if one exists (lets components render the first frame without waiting). */
export const cachedUrl = (id: string) => urls.get(id) ?? null;

/** An object URL for a stored photo (cached per id), or null if it's gone. */
export async function imageUrl(id: string): Promise<string | null> {
  const known = urls.get(id);
  if (known) return known;
  const blob = await loadImage(id);
  if (!blob) return null;
  const url = urls.get(id) ?? URL.createObjectURL(blob);
  urls.set(id, url);
  return url;
}

/**
 * Deletes photos no saved chat refers to (deleted chats, photos removed
 * before sending). Only photos stored before `olderThan` are touched, so
 * photos being attached or sent right now, here or in another tab, are safe.
 */
export async function collectGarbage(keep: Set<string>, olderThan: number): Promise<number> {
  const db = await openDb();
  if (!db) return 0;
  const stale: string[] = [];
  await new Promise<void>((resolve) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).openCursor();
    req.onsuccess = () => {
      const cursor = req.result;
      if (!cursor) return;
      const record = cursor.value as StoredImage;
      if (!keep.has(record.id) && record.createdAt < olderThan) stale.push(record.id);
      cursor.continue();
    };
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
  await Promise.all(stale.map(deleteImage));
  return stale.length;
}
