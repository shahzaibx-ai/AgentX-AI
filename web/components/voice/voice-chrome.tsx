"use client";

import { useEffect, useState } from "react";
import { LoaderCircleIcon } from "lucide-react";

/** Live "● Voice 01:23" pill for the header while a voice session runs. */
export function VoiceTimer({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");

  return (
    <div
      role="timer"
      aria-label={`Voice session, ${mm} minutes ${ss} seconds`}
      className="mr-1 flex h-8 shrink-0 items-center gap-2 rounded-full border px-2.5 text-[13px] text-muted-foreground sm:px-3"
    >
      <span className="size-2 rounded-full bg-emerald-500" />
      <span className="hidden font-medium text-foreground sm:inline">Voice</span>
      <span className="font-mono text-xs tabular-nums">
        {mm}:{ss}
      </span>
    </div>
  );
}

/** Shown for the moment it takes to download the voice module. */
export function VoiceLoading() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
      <LoaderCircleIcon className="size-6 motion-safe:animate-spin" />
      <span className="text-sm">Starting voice mode…</span>
    </div>
  );
}
