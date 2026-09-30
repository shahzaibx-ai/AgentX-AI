"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";

import { StatusDot, statusText } from "@/components/studio/status";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ModelInfo } from "@/lib/types";

export function ModelPicker({
  models,
  value,
  onChange,
}: {
  models: ModelInfo[];
  value: string | undefined;
  onChange: (id: string) => void;
}) {
  const current = models.find((m) => m.id === value);
  return (
    <Select value={value} onValueChange={onChange} disabled={models.length === 0}>
      <SelectTrigger aria-label="Model" className="h-9 w-full max-w-full min-w-0 font-medium sm:w-auto sm:min-w-64">
        <SelectValue placeholder={models.length ? "Choose a model" : "Connecting…"}>
          {current && (
            <span className="truncate">
              {current.name}
              <span className="font-normal text-muted-foreground"> · {current.domain}</span>
            </span>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent className="w-[var(--radix-select-trigger-width)] min-w-80">
        {models.map((m) => (
          <SelectItem key={m.id} value={m.id} textValue={m.name} className="items-start">
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="flex items-center gap-2">
                <span className="font-medium">{m.name}</span>
                <span className="text-muted-foreground">· {m.domain}</span>
              </span>
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <StatusDot status={m.status} className="size-1.5" />
                {statusText(m.status)} ·{" "}
                {m.labels.length === 5 ? "1–5 stars" : `${m.labels.length} classes`}
              </span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function ApiStatus({
  error,
  model,
  device,
}: {
  error: string | null;
  model: ModelInfo | null;
  device: string | undefined;
}) {
  const status = error ? "offline" : (model?.status ?? "not_loaded");
  const label = error
    ? "API offline"
    : model?.status === "ready"
      ? `Ready · ${device ?? ""}`
      : model
        ? statusText(model.status)
        : "Connecting";
  const detail = error ?? (model?.status === "error" ? model.error : `${model?.name ?? ""} on ${device ?? "…"}`);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          role="status"
          className="inline-flex h-8 max-w-56 shrink-0 items-center gap-2 rounded-full border px-3 text-xs text-muted-foreground"
        >
          <StatusDot status={status} />
          <span className="hidden truncate sm:inline">{label}</span>
          <span className="sr-only sm:hidden">{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-80">{detail}</TooltipContent>
    </Tooltip>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Switch between light and dark"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="text-muted-foreground"
    >
      <SunIcon className="hidden dark:block" aria-hidden="true" />
      <MoonIcon className="dark:hidden" aria-hidden="true" />
    </Button>
  );
}
