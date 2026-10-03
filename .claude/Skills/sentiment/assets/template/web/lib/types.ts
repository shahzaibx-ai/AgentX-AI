// Mirrors api/app/schemas.py. Keep the two in sync.

export type ModelStatus = "not_loaded" | "loading" | "ready" | "error";

export interface LabelScore {
  label: string;
  score: number;
  logit: number;
}

export interface Attribution {
  text: string;
  /** -1 pushes toward negative, +1 toward positive. */
  weight: number;
}

export interface Prediction {
  label: string;
  score: number;
  /** Every class, from most negative to most positive. */
  probs: LabelScore[];
  tokens: string[];
  num_tokens: number;
  truncated: boolean;
  attributions: Attribution[] | null;
}

export interface PredictResponse extends Prediction {
  model: string;
  device: string;
  latency_ms: number;
}

export interface BatchItem {
  label: string;
  score: number;
  probs: LabelScore[];
  num_tokens: number;
  truncated: boolean;
}

export interface BatchPredictResponse {
  model: string;
  device: string;
  latency_ms: number;
  results: BatchItem[];
}

export interface ModelInfo {
  id: string;
  name: string;
  domain: string;
  description: string;
  languages: string;
  parameters: string;
  architecture: string;
  /** From most negative to most positive. */
  labels: string[];
  revision: string;
  default: boolean;
  status: ModelStatus;
  error: string | null;
}

export interface Limits {
  max_length: number;
  max_text_chars: number;
  max_batch_items: number;
  batch_size: number;
  explain_steps: number;
  low_confidence: number;
}

export interface ModelsResponse {
  default_model: string;
  device: string;
  limits: Limits;
  models: ModelInfo[];
}

export interface HistoryEntry {
  id: string;
  text: string;
  label: string;
  score: number;
  model: string;
  at: number;
}
