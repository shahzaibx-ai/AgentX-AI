import type { ReactNode } from "react";
import { EyeIcon, EyeOffIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** A line above the input about whether the model can see the photos. */
export function VisionNotice({
  tone,
  children,
  action,
}: {
  /** "warning": sending is blocked until the user acts. */
  tone: "info" | "warning";
  children: ReactNode;
  action?: { label: string; onClick: () => void };
}) {
  const Icon = tone === "warning" ? EyeOffIcon : EyeIcon;
  return (
    <div
      role={tone === "warning" ? "alert" : "status"}
      className={cn(
        "mb-2 -ml-1.5 flex items-center gap-2 rounded-2xl border px-3 py-2 text-[13px] leading-5",
        tone === "warning"
          ? "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200"
          : "bg-muted/60 text-muted-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" />
      <p className="min-w-0 flex-1">{children}</p>
      {action && (
        <Button type="button" size="sm" variant="outline" className="h-7 shrink-0 bg-background" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
