/**
 * Voice mode (LiveKit): types, API calls and constants.
 * Self-contained: the voice components depend only on this file, shadcn/ui
 * primitives, lucide-react, sonner and the LiveKit packages.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

// ---------- types ----------

export interface VoiceOptionInfo {
  id: string;
  name: string;
  description: string;
}

export interface VoiceConfig {
  enabled: boolean;
  reason: string | null;
  voices: VoiceOptionInfo[];
}

export interface VoiceSessionInfo {
  server_url: string;
  participant_token: string;
  room_name: string;
  participant_identity: string;
}

/** The model picked in the host app; null = automatic. */
export type VoiceModelSelection = { provider: string; model: string } | null;

/** Earlier chat messages the voice session continues from. */
export interface VoiceHistoryMessage {
  role: "user" | "assistant";
  content: string;
  error?: string;
  pending?: boolean;
}

/** Which model answered a spoken reply (published by the agent). */
export interface VoiceReplyMeta {
  provider: string;
  provider_label: string;
  model: string;
  local: boolean;
  fallback: boolean;
  notice: string | null;
}

/** A finished transcript, ready for the host to save into its chat. */
export interface VoiceTranscript {
  /** Stable per spoken segment: save with upsert so late words update it. */
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  voice: true;
  meta?: VoiceReplyMeta;
}

// ---------- constants ----------

/** Agent attributes published by the voice agent (agent/voice_agent.py). */
export const AGENT_ATTR = {
  model: "assistant.model",
  provider: "assistant.provider",
  local: "assistant.local",
  notice: "assistant.notice",
  error: "assistant.error",
} as const;

export const TRANSCRIPTION_FINAL_ATTR = "lk.transcription_final";

// ---------- API ----------

export class VoiceApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "VoiceApiError";
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return res.status >= 500
    ? "Can't reach the AI server. Make sure the API is running."
    : `Request failed (${res.status})`;
}

export async function fetchVoiceConfig(signal?: AbortSignal): Promise<VoiceConfig> {
  const res = await fetch(`${API_BASE}/voice/config`, { cache: "no-store", signal });
  if (!res.ok) throw new VoiceApiError(await detail(res), res.status);
  return (await res.json()) as VoiceConfig;
}

export interface CreateVoiceSessionInput {
  mode?: "chat" | "dictation";
  selection: VoiceModelSelection;
  voice: string | null;
  participantName: string;
  history: VoiceHistoryMessage[];
}

export async function createVoiceSession(input: CreateVoiceSessionInput): Promise<VoiceSessionInfo> {
  const res = await fetch(`${API_BASE}/voice/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: input.mode,

      provider: input.selection?.provider ?? null,
      model: input.selection?.model ?? null,
      voice: input.voice,
      participant_name: input.participantName,
      history: input.history
        .filter((m) => !m.error && !m.pending && m.content.trim())
        .slice(-20)
        .map(({ role, content }) => ({ role, content })),
    }),
  });
  if (!res.ok) throw new VoiceApiError(await detail(res), res.status);
  return (await res.json()) as VoiceSessionInfo;
}
