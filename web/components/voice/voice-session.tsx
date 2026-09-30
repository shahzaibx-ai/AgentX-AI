"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  RoomAudioRenderer,
  SessionEvent,
  SessionProvider,
  useAgent,
  useLocalParticipant,
  useSession,
  useSessionContext,
  useSessionMessages,
  type ReceivedMessage,
} from "@livekit/components-react";
import { ConnectionState, TokenSource } from "livekit-client";
import { MicIcon, TriangleAlertIcon } from "lucide-react";
import { toast } from "sonner";

import { LevelBars, PulseMark } from "@/components/voice/level-bars";
import { VoiceBar, type VoiceUiState } from "@/components/voice/voice-bar";
import "@/components/voice/voice.css";
import { cn } from "@/lib/utils";
import {
  AGENT_ATTR,
  TRANSCRIPTION_FINAL_ATTR,
  createVoiceSession,
  type VoiceHistoryMessage,
  type VoiceModelSelection,
  type VoiceOptionInfo,
  type VoiceReplyMeta,
  type VoiceTranscript,
} from "@/lib/voice";

export interface VoiceSessionProps {
  /** Model picked in the host app (null = automatic). */
  selection: VoiceModelSelection;
  /** Shown to the agent as the participant name. */
  participantName: string;
  /** Earlier messages of the open chat, so voice continues the conversation. */
  history: VoiceHistoryMessage[];
  voices: VoiceOptionInfo[];
  voice: string | null;
  captions: boolean;
  onPrefsChange: (patch: { voice?: string | null; captions?: boolean }) => void;
  /** Finished transcripts in spoken order. Save with upsert by `id`. */
  onTranscripts: (messages: VoiceTranscript[]) => void;
  onEnd: () => void;
  onRetry: () => void;
  /** Renders assistant text (e.g. your Markdown component). Defaults to plain text. */
  renderText?: (text: string) => React.ReactNode;
}

function PlainText(text: string) {
  return <p className="whitespace-pre-wrap">{text}</p>;
}

const AGENT_CONNECT_TIMEOUT_MS = 20_000;

function isMicPermissionError(err: unknown): boolean {
  const e = err as { name?: string; message?: string };
  return (
    e?.name === "NotAllowedError" ||
    e?.name === "NotFoundError" ||
    e?.name === "NotReadableError" ||
    /permission|denied|not allowed|requested device not found/i.test(e?.message ?? "")
  );
}

function micErrorText(err: unknown): string {
  const name = (err as { name?: string })?.name;
  if (name === "NotFoundError") return "No microphone was found. Connect one and try again.";
  if (name === "NotReadableError") return "Your microphone is being used by another app.";
  return "Allow microphone access in your browser's site settings, then try again.";
}

/**
 * One voice conversation: fetches a token from the API, joins the LiveKit
 * room with the microphone on, and renders the live voice UI.
 * Loaded on demand (next/dynamic) so LiveKit is not in the initial bundle.
 */
export function VoiceSession(props: VoiceSessionProps) {
  const inputs = useRef(props);
  useEffect(() => {
    inputs.current = props;
  }, [props]);

  const [setupError, setSetupError] = useState<string | null>(null);
  const [micError, setMicError] = useState<string | null>(null);

  const tokenSource = useMemo(
    () =>
      TokenSource.literal(async () => {
        const { selection, voice, participantName, history } = inputs.current;
        try {
          const res = await createVoiceSession({ selection, voice, participantName, history });
          return { serverUrl: res.server_url, participantToken: res.participant_token };
        } catch (err) {
          setSetupError((err as Error).message);
          throw err;
        }
      }),
    [],
  );

  const session = useSession(tokenSource, {
    agentConnectTimeoutMilliseconds: AGENT_CONNECT_TIMEOUT_MS,
  });
  const sessionRef = useRef(session);
  useEffect(() => {
    sessionRef.current = session;
  });

  // Start once. The zero-delay timer lets React Strict Mode's mount/unmount/mount
  // in development cancel the first attempt instead of creating two rooms.
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      sessionRef.current
        .start({ tracks: { microphone: { enabled: true } } })
        .catch((err: unknown) => {
          if (cancelled) return;
          if (isMicPermissionError(err)) setMicError(micErrorText(err));
          else setSetupError((prev) => prev ?? (err as Error)?.message ?? "Could not connect.");
        });
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      void sessionRef.current.end();
    };
  }, []);

  useEffect(() => {
    const emitter = session.internal.emitter;
    const onMediaError = (err: Error) => setMicError(micErrorText(err));
    emitter.on(SessionEvent.MediaDevicesError, onMediaError);
    return () => {
      emitter.off(SessionEvent.MediaDevicesError, onMediaError);
    };
  }, [session.internal.emitter]);

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer />
      <VoiceView {...props} setupError={setupError} micError={micError} />
    </SessionProvider>
  );
}

type Transcript = Extract<ReceivedMessage, { type: "userTranscript" | "agentTranscript" }>;

function isTranscript(m: ReceivedMessage): m is Transcript {
  return m.type === "userTranscript" || m.type === "agentTranscript";
}

function metaFrom(attributes: Record<string, string>): VoiceReplyMeta | undefined {
  const model = attributes[AGENT_ATTR.model];
  if (!model) return undefined;
  const notice = attributes[AGENT_ATTR.notice] || null;
  return {
    provider: attributes[AGENT_ATTR.provider] ?? "",
    provider_label: attributes[AGENT_ATTR.provider] ?? "",
    model,
    local: attributes[AGENT_ATTR.local] === "true",
    fallback: !!notice,
    notice,
  };
}

function VoiceView({
  renderText = PlainText,
  voices,
  voice,
  captions,
  onPrefsChange,
  onTranscripts,
  onEnd,
  onRetry,
  setupError,
  micError,
}: VoiceSessionProps & { setupError: string | null; micError: string | null }) {
  const session = useSessionContext();
  const agent = useAgent();
  const { messages } = useSessionMessages();
  const { isMicrophoneEnabled, localParticipant } = useLocalParticipant();

  const transcripts = useMemo(
    () => messages.filter(isTranscript).filter((m) => m.message.trim()),
    [messages],
  );

  // ---- state shown in the bar ----
  const everConnected = useRef(false);
  if (session.isConnected) everConnected.current = true;

  const connection = session.connectionState;
  let state: VoiceUiState;
  if (micError) state = "mic-blocked";
  else if (setupError || agent.state === "failed") state = "failed";
  else if (connection === ConnectionState.Reconnecting || connection === ConnectionState.SignalReconnecting)
    state = "reconnecting";
  else if (connection === ConnectionState.Disconnected && everConnected.current) state = "ended";
  else if (agent.state === "listening" || agent.state === "thinking" || agent.state === "speaking")
    state = agent.state;
  else state = "connecting";

  const failure =
    micError ??
    setupError ??
    (agent.state === "failed"
      ? `${agent.failureReasons.join(" ") || "The voice agent didn't join."} Make sure the agent is running and uses the same LiveKit project.`
      : state === "ended"
        ? "The connection to the voice agent closed."
        : undefined);

  // ---- save finished transcripts in order ----
  // Each transcript maps to one chat message (stable id), so text that arrives
  // after a message was saved updates it instead of being lost.
  const saved = useRef(new Map<string, string>()); // transcript id -> saved text
  const pendingSave = useRef<Transcript[]>([]);
  const agentAttrs = useRef(agent.attributes);
  useEffect(() => {
    agentAttrs.current = agent.attributes;
  });

  const toChatMessage = useCallback(
    (m: Transcript): VoiceTranscript => ({
      id: `voice-${m.id}`,
      role: m.type === "userTranscript" ? "user" : "assistant",
      content: m.message.trim(),
      createdAt: m.timestamp,
      voice: true,
      meta: m.type === "agentTranscript" ? metaFrom(agentAttrs.current) : undefined,
    }),
    [],
  );

  useEffect(() => {
    const agentBusy = agent.state === "speaking" || agent.state === "thinking";
    const batch: VoiceTranscript[] = [];
    let blocked = false;
    for (let i = 0; i < transcripts.length; i++) {
      const m = transcripts[i];
      const text = m.message.trim();
      const previous = saved.current.get(m.id);
      if (previous !== undefined) {
        if (previous !== text) {
          saved.current.set(m.id, text);
          batch.push(toChatMessage(m)); // late words: update the saved message
        }
        continue;
      }
      if (blocked) continue;
      // A user transcript is done when STT marks it final (or a newer one follows).
      // An agent reply is done only once the agent has stopped speaking.
      const done =
        m.type === "userTranscript"
          ? m.attributes?.[TRANSCRIPTION_FINAL_ATTR] === "true" || i < transcripts.length - 1
          : !agentBusy;
      if (!done) {
        blocked = true; // keep the chat in spoken order
        continue;
      }
      saved.current.set(m.id, text);
      batch.push(toChatMessage(m));
    }
    if (batch.length) onTranscripts(batch);
    pendingSave.current = transcripts.filter((m) => !saved.current.has(m.id));
  }, [transcripts, agent.state, onTranscripts, toChatMessage]);

  // Whatever is still open when the session closes is saved as-is.
  const onTranscriptsRef = useRef(onTranscripts);
  useEffect(() => {
    onTranscriptsRef.current = onTranscripts;
  });
  useEffect(
    () => () => {
      const rest = pendingSave.current.map(toChatMessage);
      if (rest.length) onTranscriptsRef.current(rest);
    },
    [toChatMessage],
  );

  // ---- actions ----
  const interrupt = useCallback(async () => {
    if (!agent.identity) return;
    try {
      await session.room.localParticipant.performRpc({
        destinationIdentity: agent.identity,
        method: "interrupt",
        payload: "",
      });
    } catch {
      toast.error("Couldn't stop the reply.");
    }
  }, [agent.identity, session.room]);

  const toggleMic = useCallback(async () => {
    try {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
    } catch {
      toast.error("Couldn't change the microphone.");
    }
  }, [isMicrophoneEnabled, localParticipant]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Esc inside an open menu or dialog closes that; it must not cut the reply.
      const inOverlay = (e.target as HTMLElement | null)?.closest?.(
        '[role="menu"],[role="dialog"],[role="listbox"]',
      );
      if (e.key !== "Escape" || e.defaultPrevented || inOverlay) return;
      if (agent.state === "speaking" || agent.state === "thinking") {
        e.preventDefault();
        void interrupt();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [agent.state, interrupt]);

  // ---- follow new text while the user is at the bottom ----
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [transcripts, state]);

  const notice = agent.attributes[AGENT_ATTR.notice];
  const replyError = agent.attributes[AGENT_ATTR.error];
  const model = agent.attributes[AGENT_ATTR.model];
  const lastAgentIndex = transcripts.findLastIndex((m) => m.type === "agentTranscript");
  const showIntro = transcripts.length === 0 || !captions;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scroller}
        role="log"
        aria-live="polite"
        aria-label="Voice conversation"
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        onScroll={(e) => {
          const el = e.currentTarget;
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
        }}
      >
        {showIntro ? (
          <Intro state={state} agentTrack={agent.microphoneTrack} />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 pt-8 pb-10 sm:px-6">
            {transcripts.map((m, i) =>
              m.type === "userTranscript" ? (
                <UserTurn
                  key={m.id}
                  text={m.message}
                  final={m.attributes?.[TRANSCRIPTION_FINAL_ATTR] === "true" || i < transcripts.length - 1}
                />
              ) : (
                <div key={m.id} className="flex flex-col gap-4">
                  <div className="text-[17px] leading-8">
                    {/* Hide a code fence that was opened but not yet spoken into. */}
                    {renderText(m.message.replace(/\n?```[\w+#.-]*\s*$/, ""))}
                  </div>
                  {i === lastAgentIndex && (state === "speaking" || state === "thinking") && (
                    <SpeakingIndicator
                      state={state}
                      model={model}
                      agentTrack={agent.microphoneTrack}
                    />
                  )}
                </div>
              ),
            )}
            {state === "thinking" && transcripts.at(-1)?.type === "userTranscript" && (
              <SpeakingIndicator state="thinking" model={model} agentTrack={undefined} />
            )}
          </div>
        )}
      </div>

      {(notice || replyError) && state !== "failed" && (
        <div className="mx-auto mb-2 w-full max-w-3xl px-3 sm:px-6">
          <p
            className={cn(
              "flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground",
              replyError && "border-destructive/40 text-destructive",
            )}
          >
            <TriangleAlertIcon className="mt-px size-3.5 shrink-0" />
            <span>
              {replyError
                ? `Couldn't get a reply: ${replyError}`
                : `Using ${agent.attributes[AGENT_ATTR.provider] || "another model"} because the selected model was unavailable (${notice}).`}
            </span>
          </p>
        </div>
      )}

      <div className="shrink-0 px-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] sm:px-6">
        <VoiceBar
          state={state}
          micEnabled={isMicrophoneEnabled}
          micTrack={session.local.microphoneTrack}
          errorMessage={failure}
          voices={voices}
          voice={voice}
          captions={captions}
          onVoiceChange={(id) => onPrefsChange({ voice: id })}
          onCaptionsChange={(on) => onPrefsChange({ captions: on })}
          onToggleMic={() => void toggleMic()}
          onStop={() => void interrupt()}
          onEnd={onEnd}
          onRetry={onRetry}
        />
      </div>
    </div>
  );
}

function Intro({
  state,
  agentTrack,
}: {
  state: VoiceUiState;
  agentTrack?: Parameters<typeof LevelBars>[0]["track"];
}) {
  const copy: Record<VoiceUiState, [string, string]> = {
    connecting: ["Connecting…", "Setting up your voice session."],
    listening: ["I'm listening", "Start speaking. I'll reply when you pause."],
    thinking: ["Thinking…", "Working on a reply."],
    speaking: ["Speaking…", "Talk anytime to interrupt."],
    reconnecting: ["Reconnecting…", "Your connection dropped. Trying again."],
    "mic-blocked": ["Microphone needed", "Voice mode needs access to your microphone."],
    failed: ["Voice mode is unavailable", "See the message below."],
    ended: ["Session ended", "Start again or go back to typing."],
  };
  const [title, subtitle] = copy[state];
  const live = state === "listening" || state === "speaking" || state === "thinking";
  return (
    <div className="flex h-full min-h-72 flex-col items-center justify-center px-6 pb-8 text-center">
      <PulseMark size="lg" active={live} />
      <h2 className="mt-7 text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 text-[15px] text-muted-foreground">{subtitle}</p>
      {state === "speaking" && <LevelBars track={agentTrack} className="mt-6 text-foreground" />}
    </div>
  );
}

function UserTurn({ text, final }: { text: string; final: boolean }) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div
        className={cn(
          "max-w-[85%] rounded-3xl bg-secondary px-4 py-2.5 text-[15px] leading-7 break-words whitespace-pre-wrap",
          !final && "text-muted-foreground",
        )}
      >
        {text}
        {!final && (
          <span
            aria-hidden="true"
            className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 bg-current motion-safe:animate-[voice-caret_1s_steps(2,start)_infinite]"
          />
        )}
      </div>
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <MicIcon className="size-3" />
        {final ? "Spoken" : "Listening…"}
      </span>
    </div>
  );
}

function SpeakingIndicator({
  state,
  model,
  agentTrack,
}: {
  state: "speaking" | "thinking";
  model?: string;
  agentTrack?: Parameters<typeof LevelBars>[0]["track"];
}) {
  return (
    <div className="flex items-center gap-3 text-foreground">
      <PulseMark />
      {state === "speaking" ? <LevelBars track={agentTrack} /> : null}
      <span className="text-[13px] text-muted-foreground">
        {state === "speaking" ? "Speaking" : "Thinking…"}
        {model ? ` · ${model}` : ""}
      </span>
    </div>
  );
}
