import type { OsintPhone } from "@/types/verify";

export type PhoneStatusKind = "risk" | "safe" | "neutral";

export interface PhoneStatus {
  kind: PhoneStatusKind;
  label: string;
  shortLabel: string;
}

const digits = (v: string) => v.replace(/\D/g, "").replace(/^0/, "62");

// Nomor yang laporan komunitasnya sudah disetujui admin, dari `fraud_network.community_reports`.
export function communityReportedPhones(reported?: string[] | null): Set<string> {
  return new Set((reported ?? []).map(digits));
}

// "Tanpa laporan" hanya boleh tampil kalau probe Kaspersky benar-benar selesai. Tidak memakai
// kata "bersih": tidak adanya laporan bukan bukti nomor aman. Laporan komunitas yang disetujui
// didahulukan, karena Kaspersky tidak mengetahuinya.
export function getPhoneStatus(p: OsintPhone, communityReported?: Set<string>): PhoneStatus {
  if (p.phone && communityReported?.has(digits(p.phone))) {
    return { kind: "risk", label: "Dilaporkan komunitas, disetujui admin", shortLabel: "Dilaporkan komunitas" };
  }
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
