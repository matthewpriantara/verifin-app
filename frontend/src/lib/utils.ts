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
    case "AMAN":
      return "Aman";
    case "WASPADA":
      return "Waspada";
    case "BAHAYA":
      return "Bahaya";
    default:
      return "Error";
  }
}

export function verdictTone(v: string): {
  bg: string;
  fg: string;
  border: string;
} {
  switch (normalizeVerdict(v)) {
    case "AMAN":
      return {
        bg: "bg-aman-bg",
        fg: "text-aman-fg",
        border: "border-aman-fg/20",
      };
    case "WASPADA":
      return {
        bg: "bg-waspada-bg",
        fg: "text-waspada-fg",
        border: "border-waspada-fg/20",
      };
    case "BAHAYA":
      return {
        bg: "bg-bahaya-bg",
        fg: "text-bahaya-fg",
        border: "border-bahaya-fg/20",
      };
    default:
      return {
        bg: "bg-cream-deep",
        fg: "text-charcoal-soft",
        border: "border-border",
      };
  }
}

export const REPORT_STORAGE_KEY = "verifin:last-report";
