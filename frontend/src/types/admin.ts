export interface AdminCase {
  id: string;
  verdict: string;
  risk_score: number;
  source: string;
  company_name: string | null;
  phones: string[] | null;
  emails: string[] | null;
  raw_text_preview: string | null;
  created_at: string;
}

export interface AdminStats {
  total: number;
  aman: number;
  waspada: number;
  bahaya: number;
}

export interface WhitelistEntry {
  id: number;
  company_name: string;
  legal_type: string;
  synced_at: string;
}

export type ReportStatus = "pending" | "approved" | "rejected";

export type ReportType =
  | "biaya_travel"
  | "perusahaan_fiktif"
  | "tppo_eksploitasi"
  | "pencurian_data_scam";

export interface CommunityReport {
  id: string;
  reporter_ip: string;
  company_name: string;
  report_type: ReportType;
  description: string;
  evidence_url: string | null;
  status: ReportStatus;
  submitted_at: string;
  reviewed_at: string | null;
  reviewer_note: string | null;
}
