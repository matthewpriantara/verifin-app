import { API_BASE } from "@/lib/api";

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

export async function fetchCases(limit = 50, skip = 0): Promise<AdminCase[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/verify/cases?limit=${limit}&skip=${skip}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Gagal mengambil kasus (${res.status})`);
  return res.json();
}

export async function fetchWhitelist(limit = 100): Promise<WhitelistEntry[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/verify/whitelist?limit=${limit}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Gagal mengambil whitelist (${res.status})`);
  return res.json();
}

export async function fetchAiStatus() {
  const res = await fetch(`${API_BASE}/api/v1/verify/status`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("AI status tidak tersedia");
  return res.json();
}
