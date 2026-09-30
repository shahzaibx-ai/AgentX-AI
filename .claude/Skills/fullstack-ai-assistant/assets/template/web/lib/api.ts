import type { ModelSelection, ModelsResponse, Role, StreamMeta } from "@/lib/types";

/**
 * Requests go to `/api/*` on the same origin; `next.config.ts` rewrites them to
 * the FastAPI server (API_URL), so the browser never needs CORS.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
  } catch {
    /* not JSON */
  }
  if (res.status === 502 || res.status === 503 || res.status === 504 || res.status === 500) {
    return "Can't reach the AI server. Make sure the API is running.";
  }
  return `Request failed (${res.status})`;
}

export async function fetchModels(refresh = false, signal?: AbortSignal): Promise<ModelsResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/models${refresh ? "?refresh=true" : ""}`, {
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the AI server. Make sure the API is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (await res.json()) as ModelsResponse;
}

export interface StreamChatOptions {
  messages: { role: Role; content: string }[];
  selection: ModelSelection;
  signal: AbortSignal;
  onMeta: (meta: StreamMeta) => void;
  onDelta: (text: string) => void;
}

/** POST /api/chat and parse the server-sent event stream. */
export async function streamChat({
  messages,
  selection,
  signal,
  onMeta,
  onDelta,
}: StreamChatOptions): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        messages,
        provider: selection?.provider ?? null,
        model: selection?.model ?? null,
      }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the AI server. Make sure the API is running.");
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  if (!res.body) throw new ApiError("The server returned an empty response.");

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let finished = false;

  const handle = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
    switch (event) {
      case "meta":
        onMeta(payload as unknown as StreamMeta);
        break;
      case "error":
        throw new ApiError(String(payload.message ?? "Something went wrong."));
      case "done":
        finished = true;
        break;
      default:
        if (typeof payload.delta === "string") onDelta(payload.delta);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      handle(block);
    }
  }
  if (buffer.trim()) handle(buffer);
  if (!finished) throw new ApiError("The connection closed before the reply finished.");
}
