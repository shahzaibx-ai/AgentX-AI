export type Role = "user" | "assistant";

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  local: boolean;
  size_bytes?: number | null;
  parameter_size?: string | null;
  family?: string | null;
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

export interface ModelsResponse {
  providers: ProviderStatus[];
  default: ModelInfo | null;
  has_local_models: boolean;
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

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  meta?: StreamMeta;
  error?: string;
  pending?: boolean;
  feedback?: "up" | "down" | null;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}
