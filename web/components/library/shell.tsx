"use client";

import { createContext, useCallback, useContext, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeftIcon,
  FileTextIcon,
  FlaskConicalIcon,
  FolderIcon,
  HardDriveIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  LogOutIcon,
  SlidersHorizontalIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  fetchLibraryConfig,
  getOwnerToken,
  ownerApi,
  setOwnerToken,
  type CollectionInfo,
  type LibraryConfig,
} from "@/lib/library";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/library", label: "Overview", icon: LayoutDashboardIcon },
  { href: "/library/documents", label: "Documents", icon: FileTextIcon },
  { href: "/library/collections", label: "Collections", icon: FolderIcon },
  { href: "/library/test", label: "Retrieval test", icon: FlaskConicalIcon },
  { href: "/library/storage", label: "Storage", icon: HardDriveIcon },
  { href: "/library/settings", label: "Index settings", icon: SlidersHorizontalIcon },
] as const;

interface LibraryCtx {
  config: LibraryConfig;
  /** Every collection, including empty ones (chat only lists those with documents). */
  collections: CollectionInfo[];
  refreshConfig: () => void;
  /** Call with any owner API error: a 401 shows the token prompt again. */
  handleError: (err: unknown) => string;
}

const Ctx = createContext<LibraryCtx | null>(null);

export function useLibrary(): LibraryCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLibrary must be used inside LibraryShell");
  return ctx;
}

/** Loads owner data; reload() refetches. Errors are readable messages. */
export function useOwnerData<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const { handleError } = useLibrary();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    load().then(
      (d) => {
        if (!live) return;
        setData(d);
        setError(null);
      },
      (err) => live && setError(handleError(err)),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps are passed by the caller
  }, [version, ...deps]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading: data === null && error === null, reload, setData };
}

type Gate = "loading" | "offline" | "off" | "locked" | "token" | "ok";

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-[60vh] place-items-center px-4">
      <div className="w-full max-w-md rounded-2xl border bg-card p-6">{children}</div>
    </div>
  );
}

function TokenForm({ onDone, failed }: { onDone: () => void; failed: boolean }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(failed && getOwnerToken() ? "That token didn't work." : "");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setOwnerToken(value.trim());
    try {
      await ownerApi("/library/overview");
      onDone();
    } catch (err) {
      setOwnerToken("");
      setError(err instanceof ApiError && err.status === 401 ? "That token didn't work." : (err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Centered>
      <KeyRoundIcon className="mb-3 size-6" />
      <h1 className="text-lg font-semibold">Library owner sign-in</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Enter the owner token (<code className="font-mono text-xs">LIBRARY_TOKEN</code> on the API). It&apos;s kept
        in this tab only.
      </p>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-2">
        <label htmlFor="owner-token" className="sr-only">
          Owner token
        </label>
        <Input
          id="owner-token"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Owner token"
          aria-invalid={!!error}
          autoFocus
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={!value.trim() || busy}>
          {busy ? "Checking…" : "Continue"}
        </Button>
      </form>
    </Centered>
  );
}

export function LibraryShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [config, setConfig] = useState<LibraryConfig | null>(null);
  const [gate, setGate] = useState<Gate>("loading");
  const [badToken, setBadToken] = useState(false);
  const [version, setVersion] = useState(0);
  const [collections, setCollections] = useState<CollectionInfo[]>([]);

  useEffect(() => {
    if (gate !== "ok") return;
    ownerApi<CollectionInfo[]>("/library/collections").then(setCollections, () => undefined);
  }, [gate]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchLibraryConfig(ctrl.signal).then(
      async (c) => {
        setConfig(c);
        if (!c.enabled) return setGate("off");
        if (c.owner_auth === "disabled") return setGate("locked");
        if (c.owner_auth === "open") return setGate("ok");
        if (!getOwnerToken()) return setGate("token");
        try {
          await ownerApi("/library/overview", { signal: ctrl.signal });
          setGate("ok");
        } catch (err) {
          if (ctrl.signal.aborted) return;
          setBadToken(true);
          setGate(err instanceof ApiError && err.status === 401 ? "token" : "offline");
        }
      },
      () => !ctrl.signal.aborted && setGate("offline"),
    );
    return () => ctrl.abort();
  }, [version]);

  const refreshConfig = useCallback(() => {
    fetchLibraryConfig().then(setConfig, () => undefined);
    ownerApi<CollectionInfo[]>("/library/collections").then(setCollections, () => undefined);
  }, []);
  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) {
      setBadToken(true);
      setGate("token");
    }
    return err instanceof Error ? err.message : String(err);
  }, []);

  let body: React.ReactNode;
  if (gate === "loading") {
    body = (
      <div className="flex flex-col gap-3 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  } else if (gate === "offline") {
    body = (
      <Centered>
        <h1 className="text-lg font-semibold">Can&apos;t reach the AI server</h1>
        <p className="mt-1 text-sm text-muted-foreground">Make sure the API is running, then try again.</p>
        <Button className="mt-4" variant="outline" onClick={() => setVersion((v) => v + 1)}>
          Try again
        </Button>
      </Centered>
    );
  } else if (gate === "off") {
    body = (
      <Centered>
        <h1 className="text-lg font-semibold">Files and the Library are off</h1>
        <p className="mt-1 text-sm text-muted-foreground">{config?.reason}</p>
        <p className="mt-3 text-sm">
          Set <code className="font-mono text-xs">GEMINI_API_KEY</code> in <code className="font-mono text-xs">api/.env</code>{" "}
          for Gemini File Search, or <code className="font-mono text-xs">RAG_ENGINE=offline</code> to try it without a key,
          then restart the API.
        </p>
      </Centered>
    );
  } else if (gate === "locked") {
    body = (
      <Centered>
        <h1 className="text-lg font-semibold">The Library is locked</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          In production, managing the Library needs an owner token. Set{" "}
          <code className="font-mono text-xs">LIBRARY_TOKEN</code> on the API and restart it. People can still chat
          with their own files.
        </p>
      </Centered>
    );
  } else if (gate === "token") {
    body = (
      <TokenForm
        failed={badToken}
        onDone={() => {
          setBadToken(false);
          setGate("ok");
        }}
      />
    );
  } else {
    body = (
      <Ctx.Provider value={{ config: config!, collections, refreshConfig, handleError }}>{children}</Ctx.Provider>
    );
  }

  const nav = gate === "ok";
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="shrink-0 border-b md:sticky md:top-0 md:h-dvh md:w-60 md:border-r md:border-b-0">
        <div className="flex items-center gap-2 px-3 pt-3 pb-2">
          <Button asChild variant="ghost" size="icon-sm" aria-label="Back to chat">
            <Link href="/">
              <ArrowLeftIcon />
            </Link>
          </Button>
          <LibraryIcon className="size-4" />
          <span className="font-semibold tracking-tight">Library</span>
          <span className="rounded-full border px-1.5 py-px text-[10px] font-medium text-muted-foreground">Owner</span>
          {nav && config?.owner_auth === "token" && (
            <Button
              variant="ghost"
              size="icon-sm"
              className="ml-auto"
              aria-label="Sign out of the Library"
              onClick={() => {
                setOwnerToken("");
                setBadToken(false);
                setGate("token");
              }}
            >
              <LogOutIcon />
            </Button>
          )}
        </div>
        {nav && (
          <nav aria-label="Library" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-visible">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                    active ? "bg-muted font-medium" : "text-muted-foreground",
                  )}
                >
                  <Icon className="size-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
        )}
        {nav && config && (
          <p className="hidden px-4 pt-4 text-xs leading-5 text-muted-foreground md:block">
            {config.label}
            <br />
            <span className="font-mono">{config.model}</span>
          </p>
        )}
      </aside>
      <main className="min-w-0 flex-1">{body}</main>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 px-4 pt-6 pb-4 sm:px-6">
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mx-4 flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive sm:mx-6">
      <span className="flex-1">{message}</span>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  indexed: "bg-success",
  queued: "bg-muted-foreground",
  processing: "bg-amber-500 animate-pulse",
  failed: "bg-destructive",
};
const STATUS_LABEL: Record<string, string> = {
  indexed: "Ready",
  queued: "Queued",
  processing: "Indexing",
  failed: "Failed",
};

export function StatusDot({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs whitespace-nowrap">
      <span className={cn("size-2 rounded-full", STATUS_STYLE[status])} aria-hidden />
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
