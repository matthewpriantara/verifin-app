export type Verdict = "AMAN" | "WASPADA" | "BAHAYA" | "ERROR";

export interface ExtractedEntities {
  companies: string[];
  contacts: string[];
  emails: string[];
  urls: string[];
  addresses: string[];
  salaries: string[];
}

export interface VerifyResponse {
  verdict: Verdict | string;
  risk_score: number;
  summary: string;
  risk_factors: string[];
  safe_factors: string[];
  recommendations: string[];
  entities?: ExtractedEntities | null;
  model_used?: string | null;
}

export interface TextVerifyRequest {
  text: string;
  include_raw_text?: boolean;
}

export interface LlmStatusResponse {
  provider: string;
  configured: boolean;
  reachable: boolean;
  available_models: string[];
  target_model: string;
  detail?: string | null;
}

export interface ApiError {
  detail: string;
}
