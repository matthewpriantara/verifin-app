import clsx, { type ClassValue } from "clsx";
import type { Verdict } from "@/types/verify";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function normalizeVerdict(v: string): Verdict {
  const upper = v.toUpperCase();
  if (upper === "AMAN" || upper === "WASPADA" || upper === "BAHAYA" || upper === "ERROR") {
    return upper;
  }
  return "ERROR";
}

export function verdictLabel(v: string): string {
  switch (normalizeVerdict(v)) {
    case "AMAN":    return "Aman";
    case "WASPADA": return "Waspada";
    case "BAHAYA":  return "Bahaya";
    default:        return "Error";
  }
}

export function verdictTone(v: string): { bg: string; fg: string; border: string } {
  switch (normalizeVerdict(v)) {
    case "AMAN":
      return { bg: "bg-aman-bg", fg: "text-aman-fg", border: "border-aman-border" };
    case "WASPADA":
      return { bg: "bg-waspada-bg", fg: "text-waspada-fg", border: "border-waspada-border" };
    case "BAHAYA":
      return { bg: "bg-bahaya-bg", fg: "text-bahaya-fg", border: "border-bahaya-border" };
    default:
      return { bg: "bg-bg-subtle", fg: "text-text-secondary", border: "border-border" };
  }
}

export const REPORT_STORAGE_KEY = "verifin:last-report";

// ── Verification History (localStorage, TTL 30 hari) ────────────────────

export const HISTORY_STORAGE_KEY = "verifin:history";
const HISTORY_TTL_DAYS = 30;
const HISTORY_MAX_ITEMS = 50;

export interface HistoryItem {
  id: string;            // case_id atau timestamp fallback
  case_id: string | null;
  title: string;         // nama perusahaan atau input singkat
  verdict: "AMAN" | "WASPADA" | "BAHAYA";
  risk_score: number;
  timestamp: number;     // Date.now() saat disimpan
  entitiesSummary: string;
}

/**
 * Format timestamp ke "x menit lalu", "x jam lalu", "x hari lalu"
 */
export function formatTimeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;
  if (hours < 24) return `${hours} jam lalu`;
  if (days === 1) return "Kemarin";
  if (days < 7) return `${days} hari lalu`;
  return new Date(timestamp).toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

/**
 * Baca history dari localStorage, auto-hapus entry yang expired (>30 hari).
 */
export function getHistory(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];
    const items: HistoryItem[] = JSON.parse(raw);
    if (!Array.isArray(items)) return [];

    // Filter expired
    const cutoff = Date.now() - HISTORY_TTL_DAYS * 86400000;
    const fresh = items.filter((item) => item.timestamp > cutoff);

    // Simpan ulang kalau ada yang expired
    if (fresh.length !== items.length) {
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(fresh));
    }

    return fresh.sort((a, b) => b.timestamp - a.timestamp);
  } catch {
    return [];
  }
}

/**
 * Tambah entry baru ke history.
 * Auto-trim ke HISTORY_MAX_ITEMS terbaru.
 */
export function addHistory(item: Omit<HistoryItem, "timestamp">): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getHistory();

    // Hindari duplikat berdasarkan case_id
    const filtered = item.case_id
      ? existing.filter((h) => h.case_id !== item.case_id)
      : existing;

    const newEntry: HistoryItem = { ...item, timestamp: Date.now() };
    const updated = [newEntry, ...filtered].slice(0, HISTORY_MAX_ITEMS);

    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));

    // Notify komponen lain (SearchHistory) untuk refresh
    window.dispatchEvent(new Event("verifin:history-updated"));
  } catch {
    // localStorage penuh / disabled — silent fail
  }
}

/**
 * Hapus satu entry dari history berdasarkan id.
 */
export function removeHistory(id: string): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getHistory();
    const filtered = existing.filter((h) => h.id !== id);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(filtered));
    window.dispatchEvent(new Event("verifin:history-updated"));
  } catch {
    // silent fail
  }
}

/**
 * Hapus semua history.
 */
export function clearHistory(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    window.dispatchEvent(new Event("verifin:history-updated"));
  } catch {
    // silent fail
  }
}
