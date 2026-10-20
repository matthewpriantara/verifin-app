import type { OsintPhone } from "@/types/verify";

export type PhoneStatusKind = "risk" | "safe" | "neutral";

export interface PhoneStatus {
  kind: PhoneStatusKind;
  label: string;
  shortLabel: string;
}

// "Tanpa laporan" hanya boleh tampil kalau probe Kaspersky benar-benar selesai. Tidak memakai
// kata "bersih": tidak adanya laporan bukan bukti nomor aman.
export function getPhoneStatus(p: OsintPhone): PhoneStatus {
  if (p.reported_fraud || p.reputation_status === "FLAGGED") {
    return { kind: "risk", label: "Dilaporkan penipuan", shortLabel: "Dilaporkan" };
  }
  if (p.probe_status === "COMPLETED" && p.reputation_status === "SUSPICIOUS") {
    return { kind: "risk", label: "Ditandai mencurigakan", shortLabel: "Mencurigakan" };
  }
  if (p.probe_status === "COMPLETED" && p.reputation_status === "CLEAN") {
    return { kind: "safe", label: "Tidak ada laporan penipuan", shortLabel: "Tanpa laporan" };
  }
  return { kind: "neutral", label: "Tidak dapat dicek", shortLabel: "Tidak dapat dicek" };
}
