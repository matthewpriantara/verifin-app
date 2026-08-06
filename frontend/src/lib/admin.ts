import { API_BASE } from "@/lib/api";
import type { AdminCase, WhitelistEntry } from "@/types/admin";

export type { AdminCase, AdminStats, WhitelistEntry } from "@/types/admin";

export async function fetchCases(limit = 50, skip = 0): Promise<AdminCase[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/cases?limit=${limit}&skip=${skip}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Gagal mengambil kasus (${res.status})`);
  return res.json();
}

export async function fetchWhitelist(limit = 100): Promise<WhitelistEntry[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/whitelist?limit=${limit}`,
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
