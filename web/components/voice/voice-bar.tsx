"use client";

import { useMediaDeviceSelect } from "@livekit/components-react";
import {
  CheckIcon,
  ChevronDownIcon,
  LoaderCircleIcon,
  MicIcon,
  MicOffIcon,
  RefreshCwIcon,
  SquareIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react";

import { LevelBars } from "@/components/voice/level-bars";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { TrackReferenceOrPlaceholder } from "@livekit/components-react";
import type { VoiceOptionInfo } from "@/lib/voice";
import { cn } from "@/lib/utils";

export type VoiceUiState =
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "reconnecting"
  | "mic-blocked"
  | "failed"
  | "ended";

interface VoiceBarProps {
  state: VoiceUiState;
  micEnabled: boolean;
  micTrack?: TrackReferenceOrPlaceholder;
  errorMessage?: string;
  voices: VoiceOptionInfo[];
  voice: string | null;
  captions: boolean;
  onVoiceChange: (id: string | null) => void;
  onCaptionsChange: (on: boolean) => void;
  onToggleMic: () => void;
  onStop: () => void;
  onEnd: () => void;
  onRetry: () => void;
}

const shell =
  "mx-auto flex min-h-16 w-full max-w-3xl items-center gap-2 rounded-[32px] border bg-card px-2.5 py-2 shadow-sm sm:gap-3";

function EndButton({ onEnd }: { onEnd: () => void }) {
  return (
    <Button onClick={onEnd} aria-label="End voice mode" className="h-11 shrink-0 rounded-full px-4">
      <XIcon />
      <span className="hidden sm:inline">End</span>
    </Button>
  );
}

export function VoiceBar(props: VoiceBarProps) {
  const { state, micEnabled, onToggleMic, onStop, onEnd, onRetry } = props;

  if (state === "mic-blocked" || state === "failed" || state === "ended") {
    const title =
      state === "mic-blocked"
        ? "Microphone access is blocked"
        : state === "ended"
          ? "The voice session ended"
          : "Voice mode couldn't start";
    return (
      <div role="alert" className={cn(shell, state !== "ended" && "border-destructive/40")}>
        <span
          className={cn(
            "grid size-11 shrink-0 place-items-center rounded-full",
            state === "ended" ? "bg-muted text-muted-foreground" : "bg-destructive/10 text-destructive",
          )}
        >
          <TriangleAlertIcon className="size-5" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col leading-snug">
          <span className={cn("text-[15px] font-medium", state !== "ended" && "text-destructive")}>
            {title}
          </span>
          {props.errorMessage && (
            <span className="line-clamp-2 text-[13px] text-muted-foreground">{props.errorMessage}</span>
          )}
        </span>
        <Button variant="outline" onClick={onEnd} className="h-11 shrink-0 rounded-full px-4">
          Type instead
        </Button>
        <Button onClick={onRetry} className="h-11 shrink-0 rounded-full px-4">
          <RefreshCwIcon />
          <span className="hidden sm:inline">Try again</span>
        </Button>
      </div>
    );
  }

  const busy = state === "connecting" || state === "reconnecting";
  const canStop = state === "speaking" || state === "thinking";

  let status: React.ReactNode;
  if (state === "connecting") status = <span className="text-muted-foreground">Connecting…</span>;
  else if (state === "reconnecting")
    status = <span className="text-muted-foreground">Connection lost. Reconnecting…</span>;
  else if (!micEnabled)
    status = (
      <>
        <span className="font-medium">Microphone off</span>
        <span className="hidden text-muted-foreground sm:inline">Tap the mic to unmute</span>
      </>
    );
  else if (state === "listening")
    status = (
      <>
        <span className="font-medium">Listening…</span>
        <LevelBars track={props.micTrack} />
      </>
    );
  else if (state === "thinking")
    status = (
      <>
        <span className="text-muted-foreground">Thinking</span>
        <span aria-hidden="true" className="inline-flex gap-1">
          {[0, 150, 300].map((d) => (
            <i
              key={d}
              className="size-1.5 rounded-full bg-muted-foreground motion-safe:animate-[voice-blink_1.2s_ease-in-out_infinite]"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </span>
      </>
    );
  else
    status = (
      <span className="text-muted-foreground">
        Speaking…<span className="hidden sm:inline"> talk anytime to interrupt</span>
      </span>
    );

  return (
    <div role="group" aria-label="Voice controls" className={shell}>
      {busy ? (
        <span className="grid size-11 shrink-0 place-items-center rounded-full border text-muted-foreground">
          {state === "connecting" ? (
            <LoaderCircleIcon className="size-5 motion-safe:animate-spin" />
          ) : (
            <RefreshCwIcon className="size-[18px] motion-safe:animate-spin" />
          )}
        </span>
      ) : (
        <Button
          variant={micEnabled ? "outline" : "default"}
          size="icon"
          onClick={onToggleMic}
          aria-pressed={!micEnabled}
          aria-label={micEnabled ? "Mute microphone" : "Unmute microphone"}
          className="size-11 shrink-0 rounded-full"
        >
          {micEnabled ? <MicIcon className="size-5" /> : <MicOffIcon className="size-5" />}
        </Button>
      )}

      <span role="status" className="flex min-w-0 flex-1 items-center gap-2.5 truncate text-[15px]">
        {status}
      </span>

      {!busy && <VoiceSettings {...props} />}

      {canStop && (
        <Button
          variant="secondary"
          onClick={onStop}
          aria-label="Stop the reply"
          className="h-11 shrink-0 rounded-full px-4"
        >
          <SquareIcon className="size-3.5 fill-current" />
          <span className="hidden sm:inline">Stop</span>
        </Button>
      )}
      <EndButton onEnd={onEnd} />
    </div>
  );
}

function VoiceSettings({
  voices,
  voice,
  captions,
  onVoiceChange,
  onCaptionsChange,
}: VoiceBarProps) {
  const { devices, activeDeviceId, setActiveMediaDevice } = useMediaDeviceSelect({
    kind: "audioinput",
    requestPermissions: false,
  });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Voice settings"
          className="size-10 shrink-0 rounded-full text-muted-foreground"
        >
          <ChevronDownIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="end" className="w-72">
        <DropdownMenuLabel>Microphone</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={activeDeviceId}
          onValueChange={(id) => void setActiveMediaDevice(id)}
        >
          {devices.length === 0 && (
            <p className="px-2 pb-1.5 text-xs text-muted-foreground">Default microphone</p>
          )}
          {devices.map((d, i) => (
            <DropdownMenuRadioItem key={d.deviceId || i} value={d.deviceId}>
              <span className="truncate">{d.label || `Microphone ${i + 1}`}</span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>

        {voices.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Voice · applies to your next session</DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={voice ?? "__default"}
              onValueChange={(id) => onVoiceChange(id === "__default" ? null : id)}
            >
              <DropdownMenuRadioItem value="__default">Default</DropdownMenuRadioItem>
              {voices.map((v) => (
                <DropdownMenuRadioItem key={v.id} value={v.id} className="items-start">
                  <span className="flex flex-col">
                    <span>{v.name}</span>
                    {v.description && (
                      <span className="text-xs text-muted-foreground">{v.description}</span>
                    )}
                  </span>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </>
        )}

        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            onCaptionsChange(!captions);
          }}
        >
          <span className="flex-1">Live captions</span>
          {captions && <CheckIcon className="text-foreground" />}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
