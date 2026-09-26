export type Verdict = "AMAN" | "WASPADA" | "BAHAYA" | "ERROR";

export interface ExtractedEntities {
  companies: string[];
  contacts: string[];
  emails: string[];
  urls: string[];
  addresses: string[];
  location_candidates: string[];
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

export interface SocialSearchAudit {
  platform?: string;
  query?: string;
  status?: string;
  attempt_count?: number;
  raw_result_count?: number;
  relevant_result_count?: number;
  results?: { title?: string; url?: string; snippet?: string }[];
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
  social?: {
    enabled?: boolean;
    platform?: string;
    found?: boolean;
    posts?: {
      snippet?: string;
      source?: string;
      query?: string;
      platform?: string;
      title?: string;
      url?: string;
    }[];
    profiles?: { username?: string; url?: string; title?: string }[];
    platform_hits?: Record<string, boolean>;
    social_searches?: SocialSearchAudit[];
    risk_flags?: string[];
    error?: string;
  };
  fraud_network?: {
    status?: string;
    entity_in_fraud_network?: boolean;
    total_case_count?: number;
    threat_level?: string;
    cluster_id?: string | null;
  };
  evidence_policy?: {
    mode?: string;
    note?: string;
    social?: string;
  };
  timing?: Record<string, unknown>;
}

export interface ShapFeatureContribution {
  feature: string;
  feature_key: string;
  value: number | string;
  contribution: number;
  impact: "risk" | "safe";
  description: string;
  delta: number;
}

export interface ShapWaterfallItem {
  label: string;
  value: number;
  cumulative: number;
  impact: "risk" | "safe";
  delta: number;
}

export interface ShapExplanation {
  model_type: string;
  base_value: number;
  final_risk_score: number;
  verdict: string;
  feature_contributions: ShapFeatureContribution[];
  waterfall_chart: ShapWaterfallItem[];
  top_risk_features: string[];
  top_safe_features: string[];
  summary: string;
  evidence_confidence?: number | null;
  decision_confidence?: number | null;
  confidence_method?: string;
  probe_hit_rate_percent?: number | null;
  probe_applicability?: {
    applicable?: number;
    positive?: number;
    outcomes?: Record<string, boolean>;
  };
  coverage_probes?: {
    name?: string;
    label?: string;
    status?: string;
    applicable?: boolean;
    hit?: boolean;
  }[];
}

export interface VerifyResponse {
  case_id?: string | null;
  verdict: Verdict | string;
  risk_score: number;
  summary: string;
  risk_factors: string[];
  safe_factors: string[];
  recommendations: string[];
  entities?: ExtractedEntities | null;
  model_used?: string | null;
  osint?: OsintPayload | null;
  shap_explanation?: ShapExplanation | null;
}

export interface TextVerifyRequest {
  text: string;
  include_raw_text?: boolean;
}

export interface LlmStatusResponse {
  provider: string;
  configured: boolean;
  reachable: boolean;
  available_models?: string[];
  target_model: string;
  detail?: string | null;
}

export interface ApiError {
  detail: string;
}
