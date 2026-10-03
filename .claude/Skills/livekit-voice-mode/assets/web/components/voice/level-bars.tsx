"use client";

import { useMultibandTrackVolume, type TrackReferenceOrPlaceholder } from "@livekit/components-react";

import { cn } from "@/lib/utils";

const RESTING = [0.3, 0.6, 1, 0.55, 0.35];

/** Five bars that follow a live audio track (the mic while listening, the agent while speaking). */
export function LevelBars({
  track,
  className,
}: {
  track?: TrackReferenceOrPlaceholder;
  className?: string;
}) {
  const bands = useMultibandTrackVolume(track, { bands: 5 });
  const values = track && bands.length === 5 ? bands : RESTING.map((v) => v * 0.35);

  return (
    <span aria-hidden="true" className={cn("inline-flex h-5 items-center gap-[3px]", className)}>
      {values.map((v, i) => (
        <i
          key={i}
          className="block w-[3px] rounded-full bg-current transition-[height] duration-75"
          style={{ height: `${Math.round(4 + Math.min(1, v * 1.6) * 16)}px` }}
        />
      ))}
    </span>
  );
}

/** The app mark with a soft pulse, used as the "assistant is here" indicator. */
export function PulseMark({ size = "md", active = true }: { size?: "md" | "lg"; active?: boolean }) {
  return (
    <span
      className={cn(
        "grid shrink-0 place-items-center bg-foreground",
        size === "lg" ? "size-16 rounded-[18px]" : "size-7 rounded-lg",
        active && "animate-[voice-pulse_1.8s_ease-out_infinite] motion-reduce:animate-none",
      )}
    >
      <span
        className={cn("bg-background", size === "lg" ? "size-[22px] rounded-md" : "size-2.5 rounded-sm")}
      />
    </span>
  );
}
