import { labelColor, labelName } from "@/lib/labels";
import { cn } from "@/lib/utils";

export function Swatch({ label, className }: { label: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("size-2.5 shrink-0 rounded-[3px]", className)}
      style={{ background: labelColor(label) }}
    />
  );
}

/** A label is never shown by colour alone: swatch + name. */
export function LabelPill({ label, className }: { label: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap", className)}>
      <Swatch label={label} />
      {labelName(label)}
    </span>
  );
}
