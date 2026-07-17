export type Verdict = "AMAN" | "WASPADA" | "BAHAYA" | "ERROR";

export interface ExtractedEntities {
  companies: string[];
  contacts: string[];
  emails: string[];
  urls: string[];
  addresses: string[];
  salaries: string[];
}

export interface OsintPhone {
  source?: string;
  phone?: string;
  url?: string;
  rating?: number | null;
  review_count?: number | null;
  reported_fraud?: boolean;
  found?: boolean;
  summary?: string;
  risk_flags?: string[];
  error?: string;
  authenticated?: boolean;
}

export interface OsintWebsite {
  url?: string;
  ok?: boolean;
  title?: string;
  snippet?: string;
  risk_flags?: string[];
  safe_flags?: string[];
  error?: string;
}

export interface OsintSearch {
  query?: string;
  ok?: boolean;
  results?: { title?: string; url?: string; snippet?: string }[];
  risk_flags?: string[];
}

export interface OsintPayload {
  domain?: Record<string, unknown>;
  email_security?: Record<string, unknown>;
  address_validations?: Record<string, unknown>[];
  phones?: OsintPhone[];
  companies?: Record<string, unknown>[];
  web?: {
    enabled?: boolean;
    websites?: OsintWebsite[];
    searches?: OsintSearch[];
    risk_flags?: string[];
    safe_flags?: string[];
    error?: string;
  };
  threads?: {
    enabled?: boolean;
    found?: boolean;
    posts?: { snippet?: string; source?: string; query?: string }[];
    profiles?: { username?: string; url?: string; title?: string }[];
    risk_flags?: string[];
    error?: string;
  };
  evidence_policy?: {
    mode?: string;
    note?: string;
    social?: string;
  };
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
  osint?: OsintPayload | null;
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
