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

export type ReportStatus = "pending" | "approved" | "rejected";

export type ReportType =
  | "biaya_travel"
  | "perusahaan_fiktif"
  | "tppo_eksploitasi"
  | "pencurian_data_scam"
  | string;

export interface CommunityReport {
  id: string;
  company_name: string | null;
  phone: string | null;
  email: string | null;
  url: string | null;
  report_type: ReportType;
  description: string | null;
  reporter_ip: string | null;
  status: ReportStatus;
  reviewer_note: string | null;
  reviewed_at: string | null;
  created_at: string;
}
