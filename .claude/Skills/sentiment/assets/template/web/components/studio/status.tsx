import type { ModelStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TEXT: Record<ModelStatus, string> = {
  ready: "Ready",
  loading: "Loading",
  not_loaded: "Loads on first use",
  error: "Failed to load",
};

export const statusText = (status: ModelStatus): string => TEXT[status];

export function StatusDot({ status, className }: { status: ModelStatus | "offline"; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2 shrink-0 rounded-full",
        status === "ready" && "bg-success",
        status === "loading" && "animate-pulse bg-warning motion-reduce:animate-none",
        status === "not_loaded" && "bg-muted-foreground/50",
        (status === "error" || status === "offline") && "bg-destructive",
        className,
      )}
    />
  );
}
