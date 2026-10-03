import type {
  BatchPredictResponse,
  ModelInfo,
  ModelsResponse,
  PredictResponse,
} from "@/lib/types";

/** Same-origin by default: Next.js forwards /api/* to the FastAPI server (next.config.ts). */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

// First use of a model downloads it (hundreds of MB), so predictions get a long timeout.
const PREDICT_TIMEOUT_MS = 10 * 60_000;

/** `status` 0 means the API could not be reached at all (down, or timed out). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const errorMessage = (err: unknown): string =>
  err instanceof Error ? err.message : "Something went wrong.";

function describe(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{ loc, msg }, ...]
    return detail
      .map((d) => (typeof d?.msg === "string" ? d.msg.replace(/^Value error, /, "") : ""))
      .filter(Boolean)
      .join(". ") || fallback;
  }
  return fallback;
}

/** AbortSignal.any with a fallback for browsers that lack it (Safari < 17.4). */
function anySignal(signals: AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === "function") return AbortSignal.any(signals);
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      break;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}

function timeoutSignal(ms: number): AbortSignal {
  if (typeof AbortSignal.timeout === "function") return AbortSignal.timeout(ms);
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

async function request<T>(
  path: string,
  init: { method?: "GET" | "POST"; body?: unknown; signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<T> {
  const timeout = timeoutSignal(init.timeoutMs ?? 15_000);
  const signal = init.signal ? anySignal([init.signal, timeout]) : timeout;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? "GET",
      headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if (init.signal?.aborted) throw err;
    if (timeout.aborted) throw new ApiError("The API took too long to answer.", 0);
    throw new ApiError("Can't reach the API. Is it running on port 8000?", 0);
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json())?.detail;
    } catch {
      // Not JSON: the API crashed, or the Next.js proxy couldn't reach it.
    }
    if (detail === undefined && res.status >= 500) {
      throw new ApiError(
        `The API didn't answer (HTTP ${res.status}). Check that it is running on port 8000 and look at its log.`,
        res.status,
      );
    }
    throw new ApiError(describe(detail, `Request failed (HTTP ${res.status})`), res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  models: (signal?: AbortSignal) => request<ModelsResponse>("/models", { signal }),

  loadModel: (model: string) =>
    request<ModelInfo>("/models/load", {
      method: "POST",
      body: { model },
      timeoutMs: PREDICT_TIMEOUT_MS,
    }),

  predict: (body: { text: string; model: string; explain?: boolean }, signal?: AbortSignal) =>
    request<PredictResponse>("/predict", {
      method: "POST",
      body,
      signal,
      timeoutMs: PREDICT_TIMEOUT_MS,
    }),

  predictBatch: (body: { texts: string[]; model: string }, signal?: AbortSignal) =>
    request<BatchPredictResponse>("/predict/batch", {
      method: "POST",
      body,
      signal,
      timeoutMs: PREDICT_TIMEOUT_MS,
    }),
};
