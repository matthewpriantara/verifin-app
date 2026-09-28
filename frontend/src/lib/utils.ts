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
  return "WASPADA";
}

export function verdictLabel(v: string): string {
  switch (normalizeVerdict(v)) {
    case "AMAN": return "Aman Terverifikasi";
    case "WASPADA": return "Waspada (Indikasi Awal)";
    case "BAHAYA": return "Bahaya / Terindikasi Penipuan";
    case "ERROR": return "Gagal Analisis";
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

export const HISTORY_STORAGE_KEY = "verifin:history";
const HISTORY_TTL_DAYS = 30;
const HISTORY_MAX_ITEMS = 50;

export interface HistoryItem {
  id: string;
  case_id: string | null;
  title: string;
  verdict: "AMAN" | "WASPADA" | "BAHAYA";
  risk_score: number;
  timestamp: number;
  entitiesSummary: string;
}

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

const EMPTY_HISTORY: HistoryItem[] = [];
let cachedHistoryRaw: string | null = null;
let cachedHistoryItems: HistoryItem[] = EMPTY_HISTORY;

export function getHistory(): HistoryItem[] {
  if (typeof window === "undefined") return EMPTY_HISTORY;
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) {
      cachedHistoryRaw = null;
      cachedHistoryItems = EMPTY_HISTORY;
      return EMPTY_HISTORY;
    }
    if (raw === cachedHistoryRaw) {
      return cachedHistoryItems;
    }
    cachedHistoryRaw = raw;
    const items: HistoryItem[] = JSON.parse(raw);
    if (!Array.isArray(items)) {
      cachedHistoryItems = EMPTY_HISTORY;
      return EMPTY_HISTORY;
    }
    const cutoff = Date.now() - HISTORY_TTL_DAYS * 86400000;
    const fresh = items.filter((item) => item.timestamp > cutoff);
    if (fresh.length !== items.length) {
      const serialized = JSON.stringify(fresh);
      localStorage.setItem(HISTORY_STORAGE_KEY, serialized);
      cachedHistoryRaw = serialized;
    }
    cachedHistoryItems = fresh.sort((a, b) => b.timestamp - a.timestamp);
    return cachedHistoryItems;
  } catch {
    cachedHistoryItems = EMPTY_HISTORY;
    return EMPTY_HISTORY;
  }
}

export function getServerHistory(): HistoryItem[] {
  return EMPTY_HISTORY;
}

export function subscribeHistory(callback: () => void): () => void {
  if (typeof window === "undefined") return () => { };
  window.addEventListener("storage", callback);
  window.addEventListener("verifin:history-updated", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("verifin:history-updated", callback);
  };
}

export function addHistory(item: Omit<HistoryItem, "timestamp">): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getHistory();
    const filtered = item.case_id
      ? existing.filter((h) => h.case_id !== item.case_id)
      : existing;

    const newEntry: HistoryItem = { ...item, timestamp: Date.now() };
    const updated = [newEntry, ...filtered].slice(0, HISTORY_MAX_ITEMS);

    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new Event("verifin:history-updated"));
  } catch {
    // silent fail
  }
}

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

export function clearHistory(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    window.dispatchEvent(new Event("verifin:history-updated"));
  } catch {
    // silent fail
  }
}
