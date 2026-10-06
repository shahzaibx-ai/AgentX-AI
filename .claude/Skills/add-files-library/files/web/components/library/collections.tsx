"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { FolderIcon, PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import { useConfirm } from "@/components/library/confirm";
import { ErrorBox, PageHeader, useLibrary, useOwnerData } from "@/components/library/shell";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { admin, timeAgo } from "@/lib/library-admin";
import { formatSize, type CollectionInfo } from "@/lib/library";

function CollectionForm({
  editing,
  open,
  onOpenChange,
  onSaved,
}: {
  editing: CollectionInfo | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}) {
  const { handleError } = useLibrary();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seen, setSeen] = useState<string | null>(null);
  const key = open ? (editing?.id ?? "new") : null;
  if (key !== seen) {
    setSeen(key);
    setName(editing?.name ?? "");
    setDescription(editing?.description ?? "");
    setError("");
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (editing) await admin.updateCollection(editing.id, name.trim(), description.trim());
      else await admin.createCollection(name.trim(), description.trim());
      toast(editing ? "Collection saved" : `Created ${name.trim()}`);
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(handleError(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>{editing ? "Edit collection" : "New collection"}</DialogTitle>
        <DialogDescription>People pick collections in chat with Search Library.</DialogDescription>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="HR Policies" autoFocus />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">
              Description <span className="font-normal text-muted-foreground">(optional)</span>
            </span>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={300}
              rows={3}
              placeholder="Handbook, leave and benefits policies"
            />
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || busy}>
              {busy ? "Saving…" : editing ? "Save" : "Create"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function LibraryCollections() {
  const { handleError, refreshConfig } = useLibrary();
  const { data, error, reload } = useOwnerData(admin.collections);
  const [form, setForm] = useState<{ open: boolean; editing: CollectionInfo | null }>({ open: false, editing: null });
  const { ask, dialog } = useConfirm();
  const saved = () => {
    reload();
    refreshConfig();
  };

  return (
    <>
      <PageHeader
        title="Collections"
        description="Group documents by topic or team. Each collection is searched on its own."
        actions={
          <Button onClick={() => setForm({ open: true, editing: null })}>
            <PlusIcon />
            New collection
          </Button>
        }
      />
      {error && <ErrorBox message={error} onRetry={reload} />}
      <div className="px-4 pb-10 sm:px-6">
        {!data && !error && <Skeleton className="h-40 w-full" />}
        {data && data.length === 0 && (
          <div className="rounded-2xl border border-dashed p-10 text-center">
            <FolderIcon className="mx-auto mb-2 size-6 text-muted-foreground" />
            <p className="font-medium">No collections yet</p>
            <p className="mt-1 text-sm text-muted-foreground">Create one, then upload documents to it.</p>
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.map((c) => (
              <li key={c.id} className="flex flex-col rounded-2xl border bg-card p-4">
                <div className="flex items-start gap-2">
                  <FolderIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate font-medium">{c.name}</h2>
                    <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{c.description || "No description"}</p>
                  </div>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  {c.documents} {c.documents === 1 ? "document" : "documents"} · {formatSize(c.size)} · updated {timeAgo(c.updated_at)}
                </p>
                <div className="mt-3 flex gap-1.5">
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/library/documents?collection=${c.id}`}>Documents</Link>
                  </Button>
                  <div className="flex-1" />
                  <Button size="icon-sm" variant="ghost" aria-label={`Edit ${c.name}`} onClick={() => setForm({ open: true, editing: c })}>
                    <PencilIcon />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={`Delete ${c.name}`}
                    onClick={() =>
                      ask({
                        title: `Delete ${c.name}?`,
                        description:
                          c.documents > 0
                            ? `Its ${c.documents} ${c.documents === 1 ? "document is" : "documents are"} deleted too, from the index and from storage. This can't be undone.`
                            : "This can't be undone.",
                        action: "Delete collection",
                        run: async () => {
                          try {
                            await admin.deleteCollection(c.id);
                            toast(`Deleted ${c.name}`);
                            saved();
                          } catch (err) {
                            toast.error(handleError(err));
                          }
                        },
                      })
                    }
                  >
                    <Trash2Icon />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <CollectionForm
        open={form.open}
        editing={form.editing}
        onOpenChange={(open) => setForm((f) => ({ ...f, open }))}
        onSaved={saved}
      />
      {dialog}
    </>
  );
}
