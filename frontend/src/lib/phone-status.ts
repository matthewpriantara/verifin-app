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
  // Sinyal komunitas GetContact berada di antara "dilaporkan penipuan" dan "Kaspersky bersih":
  // nomor tanpa tag belum tentu penipu (UMKM baru), tetapi tidak pantas disebut tanpa laporan.
  const gc = p.getcontact;
  if (gc?.probe_status === "COMPLETED") {
    if (gc.spam_flagged || gc.community_level === "SPAM") {
      return { kind: "risk", label: "Ditandai spam di komunitas GetContact", shortLabel: "Spam GetContact" };
    }
    if (gc.community_level === "UNKNOWN") {
      return { kind: "neutral", label: "Belum dikenal komunitas GetContact", shortLabel: "Belum dikenal" };
    }
  }
  if (p.probe_status === "COMPLETED" && p.reputation_status === "CLEAN") {
    return { kind: "safe", label: "Tidak ada laporan penipuan", shortLabel: "Tanpa laporan" };
  }
  return { kind: "neutral", label: "Tidak dapat dicek", shortLabel: "Tidak dapat dicek" };
}

// Satu baris ringkas per nomor untuk panel bukti. Tidak pernah menampilkan nama pemilik atau isi tag.
export function getcontactLine(gc?: OsintPhone["getcontact"]): string | null {
  if (!gc?.probe_status) return null;
  if (gc.probe_status !== "COMPLETED") return "GetContact: tidak tersedia saat ini";
  if (gc.community_level === "UNKNOWN") return "GetContact: belum ada tag (belum dikenal komunitas)";
  const spam = gc.spam_flagged ? "ditandai spam" : "tidak ditandai spam";
  return `GetContact: ${gc.tag_count ?? 0} tag · ${spam}`;
}
