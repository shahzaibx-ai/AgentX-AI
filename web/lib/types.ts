export type Role = "user" | "assistant";

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  local: boolean;
  size_bytes?: number | null;
  parameter_size?: string | null;
  family?: string | null;
  /** Can read images. */
  vision?: boolean;
}

export interface ProviderStatus {
  id: string;
  label: string;
  local: boolean;
  configured: boolean;
  available: boolean;
  error?: string | null;
  models: ModelInfo[];
}

export interface ImageLimits {
  per_message: number;
  per_request: number;
  max_bytes: number;
}

export interface ModelsResponse {
  providers: ProviderStatus[];
  default: ModelInfo | null;
  /** What Auto answers with when a message has photos. */
  default_vision?: ModelInfo | null;
  has_local_models: boolean;
  image_limits?: ImageLimits | null;
}

/** `null` means "Auto": local model first, then cloud fallback. */
export type ModelSelection = { provider: string; model: string } | null;

export interface StreamMeta {
  provider: string;
  provider_label: string;
  model: string;
  local: boolean;
  fallback: boolean;
  notice: string | null;
}

/**
 * A photo in a message. Only this metadata lives in the chat history
 * (localStorage); the image itself is in IndexedDB under `id` (lib/image-store).
 */
export interface ChatImage {
  id: string;
  name: string;
  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif";
  width: number;
  height: number;
  size: number;
  /** Original size when the photo was scaled down before sending, e.g. "4032×3024". */
  resizedFrom?: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  meta?: StreamMeta;
  error?: string;
  pending?: boolean;
  feedback?: "up" | "down" | null;
  /** Photos attached to a user message. */
  images?: ChatImage[];
  /** Voice turns are identified by this ID. */
  voiceId?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}
