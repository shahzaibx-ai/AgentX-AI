"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ExternalLinkIcon,
  FolderInputIcon,
  RefreshCwIcon,
  SearchIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { toast } from "sonner";

import { useConfirm } from "@/components/library/confirm";
import { ErrorBox, PageHeader, StatusDot, useLibrary, useOwnerData } from "@/components/library/shell";
import { TypeBadge } from "@/components/files/file-chip";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { admin, timeAgo } from "@/lib/library-admin";
import { fileUrl, formatSize, uploadDocuments, type LibraryDocument } from "@/lib/library";
import { cn } from "@/lib/utils";

const PAGE = 50;
const selectCls =
  "h-9 rounded-md border bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

// ------------------------------------------------------------------ upload dialog
function UploadDialog({
  open,
  onOpenChange,
  defaultCollection,
  onUploaded,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  defaultCollection: string;
  onUploaded: () => void;
}) {
  const { config, handleError, refreshConfig, collections } = useLibrary();
  const [collection, setCollection] = useState(defaultCollection);
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [rejected, setRejected] = useState<{ filename: string; reason: string; duplicate: boolean }[]>([]);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const limit = config.limits.library_file_max_bytes;

  useEffect(() => {
    if (open) {
      setCollection(defaultCollection || collections[0]?.id || "");
      setFiles([]);
      setRejected([]);
      setProgress(null);
    }
  }, [open, defaultCollection, collections]);

  const add = (list: File[]) => {
    const ok = list.filter((f) => {
      const tooBig = f.size > limit;
      if (tooBig) toast(`${f.name} is over ${formatSize(limit)}`);
      return !tooBig;
    });
    setFiles((cur) => [...cur, ...ok].slice(0, 50));
  };

  // One file per request: progress per file, and each stays under the proxy body limit.
  const upload = async (replace: boolean, list = files) => {
    if (!collection || !list.length) return;
    setProgress(0);
    setRejected([]);
    const total = list.reduce((s, f) => s + f.size, 0) || 1;
    let sent = 0;
    let accepted = 0;
    const failed: typeof rejected = [];
    try {
      for (const file of list) {
        try {
          const res = await uploadDocuments([file], collection, replace, (p) =>
            setProgress((sent + p * file.size) / total),
          );
          accepted += res.accepted.length;
          failed.push(...res.rejected);
        } catch (err) {
          failed.push({ filename: file.name, reason: handleError(err), duplicate: false });
        }
        sent += file.size;
      }
      if (accepted) {
        toast(`${accepted} ${accepted === 1 ? "document" : "documents"} uploaded`, {
          description: "Indexing runs in the background.",
        });
        onUploaded();
        refreshConfig();
      }
      if (failed.length) {
        setRejected(failed);
        setFiles(list.filter((f) => failed.some((r) => r.filename === f.name)));
      } else {
        onOpenChange(false);
      }
    } finally {
      setProgress(null);
    }
  };

  const duplicates = rejected.filter((r) => r.duplicate);
  return (
    <Dialog open={open} onOpenChange={(o) => progress === null && onOpenChange(o)}>
      <DialogContent>
        <DialogTitle>Upload documents</DialogTitle>
        <DialogDescription>
          Up to 50 files, {formatSize(limit)} each. PDF, Word, Excel, PowerPoint, text, CSV, Markdown, HTML or code.
        </DialogDescription>
        {collections.length === 0 ? (
          <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            Create a collection first, on the Collections page.
          </p>
        ) : (
          <>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">Collection</span>
              <select className={selectCls} value={collection} onChange={(e) => setCollection(e.target.value)}>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => input.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setOver(false);
                add([...e.dataTransfer.files]);
              }}
              className={cn(
                "flex flex-col items-center gap-1 rounded-xl border-2 border-dashed px-4 py-7 text-center outline-none focus-visible:ring-2 focus-visible:ring-ring",
                over ? "border-foreground bg-muted" : "border-border hover:bg-muted/50",
              )}
            >
              <UploadIcon className="size-5" />
              <span className="text-sm font-medium">Drop files or choose</span>
              <span className="text-xs text-muted-foreground">They&apos;re indexed for search after upload</span>
            </button>
            <input
              ref={input}
              type="file"
              multiple
              hidden
              accept={config.limits.extensions.join(",")}
              onChange={(e) => {
                add([...(e.target.files ?? [])]);
                e.target.value = "";
              }}
              data-testid="library-upload-input"
            />
            {files.length > 0 && (
              <ul className="max-h-48 divide-y overflow-y-auto rounded-lg border text-sm">
                {files.map((f, i) => {
                  const r = rejected.find((x) => x.filename === f.name);
                  return (
                    <li key={`${f.name}-${i}`} className="flex items-center gap-2 px-2.5 py-1.5">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">{f.name}</span>
                        {r && <span className="block text-xs text-destructive">{r.reason}</span>}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">{formatSize(f.size)}</span>
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        aria-label={`Remove ${f.name}`}
                        disabled={progress !== null}
                        onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))}
                      >
                        <Trash2Icon />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
            {progress !== null && (
              <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
                <div className="h-full bg-foreground transition-[width]" style={{ width: `${progress * 100}%` }} />
              </div>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              {duplicates.length > 0 && (
                <Button
                  variant="outline"
                  disabled={progress !== null}
                  onClick={() => upload(true, files.filter((f) => duplicates.some((d) => d.filename === f.name)))}
                >
                  Replace {duplicates.length === 1 ? "existing copy" : `${duplicates.length} existing copies`}
                </Button>
              )}
              <Button disabled={!files.length || !collection || progress !== null} onClick={() => upload(false)}>
                {progress !== null ? `Uploading ${Math.round(progress * 100)}%` : `Upload ${files.length || ""}`.trim()}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ page
export function LibraryDocuments() {
  const { handleError, refreshConfig, collections } = useLibrary();
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [collection, setCollection] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [moveTo, setMoveTo] = useState("");
  const { ask, dialog } = useConfirm();

  // Deep links from Overview: ?status=failed, ?upload=1, ?collection=<id>
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("status")) setStatus(p.get("status")!);
    if (p.get("collection")) setCollection(p.get("collection")!);
    if (p.get("upload")) setUploadOpen(true);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setQ(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);
  useEffect(() => setOffset(0), [q, collection, status]);

  const { data, error, reload } = useOwnerData(
    () => admin.documents({ query: q, collection_id: collection, status, limit: PAGE, offset }),
    [q, collection, status, offset],
  );
  const docs = useMemo(() => data?.documents ?? [], [data]);

  const indexing = docs.some((d) => d.status === "queued" || d.status === "processing");
  useEffect(() => {
    if (!indexing) return;
    const t = setInterval(reload, 2500);
    return () => clearInterval(t);
  }, [indexing, reload]);

  const open = docs.find((d) => d.id === openId) ?? null;
  const allChecked = docs.length > 0 && docs.every((d) => selected.has(d.id));
  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const after = () => {
    reload();
    refreshConfig();
  };
  const runBulk = async (action: "delete" | "reindex" | "move", ids: string[], to?: string) => {
    try {
      const res = await admin.bulk(action, ids, to);
      const verb = action === "delete" ? "Deleted" : action === "move" ? "Moved" : "Re-indexing";
      if (res.done.length) toast(`${verb} ${res.done.length} ${res.done.length === 1 ? "document" : "documents"}`);
      if (res.failed.length) toast.error(res.failed[0].reason, { description: res.failed.length > 1 ? `${res.failed.length} failed` : undefined });
      setSelected(new Set());
      after();
    } catch (err) {
      toast.error(handleError(err));
    }
  };
  const confirmDelete = (ids: string[], name?: string) =>
    ask({
      title: ids.length === 1 ? `Delete ${name ?? "this document"}?` : `Delete ${ids.length} documents?`,
      description: "They're removed from the index and from storage. Answers stop citing them. This can't be undone.",
      action: "Delete",
      run: async () => {
        await runBulk("delete", ids);
        setOpenId(null);
      },
    });

  const total = data?.total ?? 0;
  const ids = [...selected];
  return (
    <>
      <PageHeader
        title="Documents"
        description="Everything people can search from chat, by collection."
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <UploadIcon />
            Upload
          </Button>
        }
      />
      <div className="flex flex-wrap gap-2 px-4 pb-3 sm:px-6">
        <div className="relative min-w-48 flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label="Search documents"
            placeholder="Search by name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
          />
        </div>
        <select aria-label="Collection" className={selectCls} value={collection} onChange={(e) => setCollection(e.target.value)}>
          <option value="">All collections</option>
          {collections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select aria-label="Status" className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          <option value="indexed">Ready</option>
          <option value="queued">Queued</option>
          <option value="processing">Indexing</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {ids.length > 0 && (
        <div className="mx-4 mb-3 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/50 px-3 py-2 text-sm sm:mx-6">
          <span className="font-medium">{ids.length} selected</span>
          <div className="flex-1" />
          <Button size="sm" variant="outline" onClick={() => runBulk("reindex", ids)}>
            <RefreshCwIcon />
            Re-index
          </Button>
          <select aria-label="Move to collection" className={cn(selectCls, "h-8")} value={moveTo} onChange={(e) => setMoveTo(e.target.value)}>
            <option value="">Move to…</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <Button size="sm" variant="outline" disabled={!moveTo} onClick={() => runBulk("move", ids, moveTo)}>
            <FolderInputIcon />
            Move
          </Button>
          <Button size="sm" variant="destructive" onClick={() => confirmDelete(ids)}>
            <Trash2Icon />
            Delete
          </Button>
        </div>
      )}

      {error && <ErrorBox message={error} onRetry={reload} />}
      <div className="px-4 pb-10 sm:px-6">
        {!data && !error ? (
          <Skeleton className="h-64 w-full" />
        ) : data && docs.length === 0 ? (
          <div className="rounded-2xl border border-dashed p-10 text-center">
            <p className="font-medium">{q || collection || status ? "No documents match." : "No documents yet."}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {q || collection || status ? "Try other filters." : "Upload PDFs, Word files or notes for people to search."}
            </p>
          </div>
        ) : (
          data && (
            <div className="overflow-x-auto rounded-2xl border">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="w-10 px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label="Select all on this page"
                        checked={allChecked}
                        onChange={() => setSelected(allChecked ? new Set() : new Set(docs.map((d) => d.id)))}
                      />
                    </th>
                    <th className="w-[40%] px-2 py-2 font-medium">Name</th>
                    <th className="px-2 py-2 font-medium">Collection</th>
                    <th className="px-2 py-2 font-medium">Status</th>
                    <th className="px-2 py-2 text-right font-medium">Size</th>
                    <th className="px-2 py-2 text-right font-medium">Cited</th>
                    <th className="px-3 py-2 text-right font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id} className={cn("border-t hover:bg-muted/40", selected.has(d.id) && "bg-muted/40")}>
                      <td className="px-3 py-2">
                        <input type="checkbox" aria-label={`Select ${d.title}`} checked={selected.has(d.id)} onChange={() => toggle(d.id)} />
                      </td>
                      <td className="max-w-0 px-2 py-2">
                        <button
                          type="button"
                          onClick={() => setOpenId(d.id)}
                          className="flex w-full min-w-0 items-center gap-2.5 text-left outline-none focus-visible:underline"
                        >
                          <TypeBadge ext={d.ext} small />
                          <span className="truncate font-medium">{d.title}</span>
                        </button>
                      </td>
                      <td className="px-2 py-2 whitespace-nowrap text-muted-foreground">{d.collection ?? "—"}</td>
                      <td className="px-2 py-2" title={d.error || undefined}>
                        <StatusDot status={d.status} />
                      </td>
                      <td className="px-2 py-2 text-right whitespace-nowrap tabular-nums">{formatSize(d.size)}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{d.uses}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap text-muted-foreground">{timeAgo(d.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
        {total > PAGE && (
          <div className="mt-3 flex items-center justify-end gap-2 text-sm">
            <span className="text-muted-foreground tabular-nums">
              {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
            </span>
            <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
              Previous
            </Button>
            <Button size="sm" variant="outline" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
              Next
            </Button>
          </div>
        )}
      </div>

      <DocumentDrawer
        doc={open}
        onClose={() => setOpenId(null)}
        onChanged={after}
        onDelete={(d) => confirmDelete([d.id], d.title)}
      />
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} defaultCollection={collection} onUploaded={after} />
      {dialog}
    </>
  );
}

function DocumentDrawer({
  doc,
  onClose,
  onChanged,
  onDelete,
}: {
  doc: LibraryDocument | null;
  onClose: () => void;
  onChanged: () => void;
  onDelete: (d: LibraryDocument) => void;
}) {
  const { handleError, collections } = useLibrary();
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try {
      await fn();
      toast(done);
      onChanged();
    } catch (err) {
      toast.error(handleError(err));
    } finally {
      setBusy(false);
    }
  };
  const row = (label: string, value: React.ReactNode) => (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right break-words">{value}</dd>
    </>
  );
  const indexing = doc?.status === "queued" || doc?.status === "processing";
  return (
    <Sheet open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
        {doc && (
          <>
            <div className="flex items-start gap-3 border-b p-4 pr-12">
              <TypeBadge ext={doc.ext} />
              <div className="min-w-0">
                <SheetTitle className="text-[15px] break-words">{doc.title}</SheetTitle>
                <SheetDescription className="mt-1">
                  <StatusDot status={doc.status} />
                  {indexing && doc.step && <span className="ml-2 text-xs">{doc.step}</span>}
                </SheetDescription>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {doc.error && (
                <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  {doc.error}
                </p>
              )}
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                {row("Collection", doc.collection ?? "—")}
                {row("File", <span className="font-mono text-xs">{doc.filename}</span>)}
                {row("Size", formatSize(doc.size))}
                {row("Cited in answers", doc.uses)}
                {row("Uploaded by", doc.uploaded_by)}
                {row("Uploaded", new Date(doc.created_at * 1000).toLocaleString())}
                {row("Indexed", doc.indexed_at ? new Date(doc.indexed_at * 1000).toLocaleString() : "—")}
                {row("Engine", doc.engine || "—")}
              </dl>
              <label className="mt-6 flex flex-col gap-1.5 text-sm">
                <span className="font-medium">Move to collection</span>
                <select
                  className={selectCls}
                  value={doc.collection_id ?? ""}
                  disabled={busy || indexing}
                  onChange={(e) => act(() => admin.bulk("move", [doc.id], e.target.value), "Moved. Re-indexing with the new collection.")}
                >
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap gap-2 border-t p-3">
              <Button asChild variant="outline" size="sm">
                <a href={fileUrl(doc.id)} target="_blank" rel="noopener noreferrer">
                  <ExternalLinkIcon />
                  Open original
                </a>
              </Button>
              <Button variant="outline" size="sm" disabled={busy || indexing} onClick={() => act(() => admin.reindex(doc.id), "Re-indexing")}>
                <RefreshCwIcon />
                Re-index
              </Button>
              <div className="flex-1" />
              <Button variant="destructive" size="sm" disabled={busy} onClick={() => onDelete(doc)}>
                <Trash2Icon />
                Delete
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
