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
  checked?: boolean;
  probe_status?: string;
  reputation_status?: string;
  category?: string | null;
  summary?: string;
  risk_flags?: string[];
  error?: string;
  authenticated?: boolean;
  comments?: string[];
}

export interface OsintWebsite {
  url?: string;
  ok?: boolean | null;
  /** AVAILABLE · HTTP_ERROR · NOT_FOUND · BLOCKED (anti-bot) · UNREACHABLE · SKIPPED */
  website_status?: string;
  neutral_notes?: string[];
  title?: string;
  snippet?: string;
  risk_flags?: string[];
  safe_flags?: string[];
  error?: string;
}

export interface OsintSearch {
  query?: string;
  ok?: boolean;
  status?: string;
  results?: { title?: string; url?: string; snippet?: string; source_type?: string }[];
  risk_flags?: string[];
}

export interface OsintScamCheck {
  status?: string;
  query?: string;
  warnings?: number;
  error?: string;
  results?: { title?: string; url?: string; snippet?: string }[];
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
    scam_check?: OsintScamCheck;
    evidence_counts?: { relevant_results?: number; scam_warnings?: number };
    risk_flags?: string[];
    safe_flags?: string[];
    neutral_notes?: string[];
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
    found_by_name_only?: boolean;
    linked_profiles?: string[];
    platform_hits?: Record<string, boolean>;
    social_searches?: SocialSearchAudit[];
    risk_flags?: string[];
    error?: string;
  };
  fraud_network?: {
    status?: string;
    entity_in_fraud_network?: boolean;
    entity_seen_multiple_cases?: boolean;
    fraud_case_count?: number;
    total_case_count?: number;
    threat_level?: string;
    cluster_id?: string | null;
    matched_entities?: {
      entity_type?: string;
      entity_value?: string;
      total_appearances?: number;
      fraud_appearances?: number;
      verdicts?: string[];
    }[];
    community_reports?: {
      status?: string;
      report_count?: number | null;
      pending_report_count?: number;
    };
    syndicate_analysis?: { syndicate_alerts?: { detail?: string; severity?: string }[] };
  };
  foreign_locations?: string[];
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
  evidence_delta?: number;
  calibration_delta?: number;
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

export type CaseQueryKind = "url" | "phone" | "email" | "company";

export interface CaseSummary {
  id: string;
  company_name: string | null;
  source: "text" | "image" | "url" | string | null;
  verdict: Verdict | string;
  risk_score: number;
  osint_failed: boolean;
  matched_on: CaseQueryKind | null;
  created_at: string | null;
}

export interface CaseSearchResponse {
  query_kind: CaseQueryKind | null;
  total: number;
  cases: CaseSummary[];
  too_short: boolean;
}
