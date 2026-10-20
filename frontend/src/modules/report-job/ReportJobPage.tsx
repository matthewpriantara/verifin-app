"use client";

import { useState, useEffect, Suspense, useRef, useSyncExternalStore } from "react";
import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";
import { useSearchParams, useRouter } from "next/navigation";
import { motion } from "motion/react";
import {
  ArrowLeft,
  Buildings,
  LinkSimple,
  Note,
  CheckCircle,
  Warning,
  UploadSimple,
  X,
  CaretDown,
  FolderOpen,
} from "@phosphor-icons/react";
import { cn, getHistory, getServerHistory, subscribeHistory } from "@/lib/utils";
import ReportJobLoading from "@/app/report-job/loading";
import type { ReportType } from "@/types/admin";
import { submitCommunityReport } from "@/lib/api";

const REPORT_TYPES: { value: ReportType; label: string; desc: string }[] = [
  {
    value: "biaya_travel",
    label: "Penipuan Biaya & Travel",
    desc: "Meminta biaya registrasi, diklat, atau tiket travel palsu.",
  },
  {
    value: "perusahaan_fiktif",
    label: "Perusahaan Fiktif",
    desc: "Nama tidak terdaftar di AHU (database badan hukum resmi) atau kantornya tidak ditemukan.",
  },
  {
    value: "tppo_eksploitasi",
    label: "Indikasi TPPO & Eksploitasi",
    desc: "Penyaluran kerja ilegal ke luar negeri atau kerja paksa.",
  },
  {
    value: "pencurian_data_scam",
    label: "Pencurian Data & Penipuan Tugas",
    desc: "Meminta data sensitif (KTP) atau penipuan tugas online.",
  },
];


export default function ReportJobPage() {
  return (
    <Suspense fallback={<ReportJobLoading />}>
      <ReportJobPageInner />
    </Suspense>
  );
}

function ReportJobPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const urlCaseId = searchParams.get("caseId") || undefined;
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pilihan: lapor berdasarkan case yang ada, atau lapor baru
  const [selectedMode, setSelectedMode] = useState<"from_history" | "new">(
    urlCaseId ? "from_history" : "new"
  );
  const historyItems = useSyncExternalStore(subscribeHistory, getHistory, getServerHistory);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(urlCaseId || null);

  const [companyName, setCompanyName] = useState("");
  const [reportType, setReportType] = useState<ReportType | "">("");
  const [description, setDescription] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!urlCaseId) return;
    const raw = sessionStorage.getItem("verifin:last-report");
    if (!raw) return;
    try {
      const report = JSON.parse(raw);
      const company = report?.entities?.companies?.[0];
      const url = report?.entities?.urls?.[0];
      if (company || url) {
        setTimeout(() => {
          if (company) setCompanyName(company);
          if (url) setEvidenceUrl(url);
        }, 0);
      }
    } catch {
      // ignore
    }
  }, [urlCaseId]);

  // Saat user pilih case dari dropdown, pre-fill company name & url
  const handleSelectCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    const item = historyItems.find((h) => h.case_id === caseId);
    if (item) {
      setCompanyName(item.title);
      // Parse entitiesSummary: "Company • URL"
      const parts = item.entitiesSummary.split(" • ");
      if (parts.length > 1 && parts[1].startsWith("http")) {
        setEvidenceUrl(parts[1]);
      }
    }
  };

  const handleFileSelect = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("File harus berupa gambar (JPG, PNG, atau WebP).");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Ukuran file terlalu besar. Maksimal 5MB.");
      return;
    }
    setError("");
    setEvidenceFile(file);
    setEvidencePreview(URL.createObjectURL(file));
  };

  const handleRemoveFile = () => {
    setEvidenceFile(null);
    if (evidencePreview) {
      URL.revokeObjectURL(evidencePreview);
      setEvidencePreview(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Active case_id untuk submit
  const activeCaseId = selectedMode === "from_history" ? selectedCaseId : undefined;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName || !reportType || !description) return;

    setLoading(true);
    setError("");
    try {
      await submitCommunityReport({
        company_name: companyName,
        report_type: reportType,
        description,
        url: evidenceUrl.trim() || undefined,
        case_id: activeCaseId || undefined,
        evidence_file: evidenceFile || undefined,
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Laporan belum terkirim. Coba lagi sebentar lagi; isian kamu tidak hilang.");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="mx-auto flex min-h-[calc(100vh-140px)] w-full max-w-xl flex-col justify-center px-4 py-14 sm:px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-2xl border border-border bg-bg-elevated p-6 text-center shadow-sm"
        >
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-aman-bg text-aman-fg">
            <CheckCircle size={28} weight="fill" />
          </div>
          <h2 className="text-xl font-bold text-text-primary">Laporan Terkirim</h2>
          <p className="mt-2 text-[14px] leading-relaxed text-text-secondary">
            Laporanmu tentang <span className="font-semibold">{companyName}</span> telah berhasil kami terima.
            Admin akan meninjaunya dulu. Setelah disetujui, laporan ini menjadi bukti tambahan saat lowongan dengan kontak yang sama diperiksa.
          </p>

          <div className="mt-4 rounded-xl border border-border bg-bg-subtle/50 p-3 text-left font-mono text-[11px] text-text-muted">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span>Status:</span>
              <span className="font-semibold text-waspada-fg uppercase">Menunggu Review</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Jenis Laporan:</span>
              <span>{REPORT_TYPES.find(t => t.value === reportType)?.label}</span>
            </div>
            {evidenceFile && (
              <div className="flex justify-between py-1">
                <span>Bukti Gambar:</span>
                <span className="text-aman-fg">Terlampir</span>
              </div>
            )}
            {evidenceUrl && (
              <div className="flex justify-between py-1">
                <span>URL Bukti:</span>
                <span className="max-w-[220px] truncate">{evidenceUrl}</span>
              </div>
            )}
          </div>

          <div className="mt-6 flex flex-col gap-2">
            {activeCaseId ? (
              <button
                type="button"
                onClick={() => router.push(`/report/${activeCaseId}`)}
                className={buttonClass({ fullWidth: true })}
              >
                Kembali ke laporan
              </button>
            ) : (
              <Link
                href="/"
                className={buttonClass({ fullWidth: true })}
              >
                Kembali ke beranda
              </Link>
            )}
            <button
              onClick={() => {
                setCompanyName("");
                setReportType("");
                setDescription("");
                setEvidenceUrl("");
                handleRemoveFile();
                setSelectedMode("new");
                setSelectedCaseId(null);
                setSuccess(false);
              }}
              className={buttonClass({ variant: "secondary", fullWidth: true })}
            >
              Kirim laporan lain
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:py-12">

      {/* ── Top Bar Navigasi ── */}
      <div className="mb-6 flex items-center justify-between border-b border-border-focus/40 pb-4">
        {activeCaseId ? (
          <button
            type="button"
            onClick={() => router.back()}
            className={buttonClass()}
          >
            <ArrowLeft size={15} weight="bold" /> Kembali
          </button>
        ) : (
          <Link
            href="/"
            className={buttonClass()}
          >
            <ArrowLeft size={15} weight="bold" /> Kembali
          </Link>
        )}

        {activeCaseId && (
          <span className="inline-flex items-center rounded-lg border border-border-focus/60 bg-bg-subtle px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-text-primary">
            Kasus #{activeCaseId.slice(0, 8)}
          </span>
        )}
      </div>

      {/* ── Header Title ── */}
      <div className="mb-8 max-w-3xl">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
          Laporkan Lowongan Mencurigakan
        </h1>
        <p className="mt-2 text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">
          Bantu lindungi sesama pencari kerja dari kejahatan rekrutmen. Setiap laporan ditinjau admin dulu. Laporan yang disetujui menjadi bukti tambahan saat lowongan dengan nomor, email, atau nama yang sama diperiksa, bukan vonis terhadap perusahaan.
        </p>
      </div>

      {/* ── Form Utama ── */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {error && (
          <div className="rounded-xl border border-bahaya-border bg-bahaya-bg px-4 py-3 text-[13px] text-bahaya-fg">
            {error}
          </div>
        )}

        {/* Section 0: Pilih Mode (dari riwayat atau baru) */}
        {historyItems.length > 0 && (
          <div className="rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6">
            <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
              <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
                <FolderOpen size={11} weight="bold" className="text-bg-elevated" />
              </div>
              <span className="text-[13px] font-semibold text-text-primary">
                Sumber Laporan
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => {
                  setSelectedMode("from_history");
                  setCompanyName("");
                  setReportType("");
                  setDescription("");
                  setEvidenceUrl("");
                  handleRemoveFile();
                }}
                className={cn(
                  "flex flex-col items-start rounded-xl border p-3.5 text-left transition-all",
                  selectedMode === "from_history"
                    ? "border-text-primary bg-text-primary/5"
                    : "border-border bg-bg hover:border-border-focus",
                )}
              >
                <span className="text-[13px] font-semibold text-text-primary">Dari Riwayat Verifikasi</span>
                <span className="mt-1 text-[11px] leading-snug text-text-muted">
                  Pilih dari lowongan yang sudah kamu cek
                </span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedMode("new");
                  setSelectedCaseId(null);
                  setCompanyName("");
                  setReportType("");
                  setDescription("");
                  setEvidenceUrl("");
                  handleRemoveFile();
                }}
                className={cn(
                  "flex flex-col items-start rounded-xl border p-3.5 text-left transition-all",
                  selectedMode === "new"
                    ? "border-text-primary bg-text-primary/5"
                    : "border-border bg-bg hover:border-border-focus",
                )}
              >
                <span className="text-[13px] font-semibold text-text-primary">Laporan Baru</span>
                <span className="mt-1 text-[11px] leading-snug text-text-muted">
                  Laporkan tanpa verifikasi sebelumnya
                </span>
              </button>
            </div>

            {/* Dropdown pilih case dari history */}
            {selectedMode === "from_history" && (
              <div className="mt-4">
                <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                  Pilih Kasus Verifikasi <span className="text-bahaya-fg">*</span>
                </label>
                <div className="relative">
                  <select
                    value={selectedCaseId || ""}
                    onChange={(e) => handleSelectCase(e.target.value)}
                    className="w-full appearance-none rounded-xl border border-border bg-bg px-4 py-3 pr-10 text-[13px] text-text-primary outline-none transition-colors focus:border-border-focus"
                  >
                    <option value="">(Pilih riwayat kasus)</option>
                    {historyItems.map((item) => (
                      <option key={item.id} value={item.case_id || item.id}>
                        {item.title} ({item.verdict}, skor {item.risk_score})
                      </option>
                    ))}
                  </select>
                  <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3.5 text-text-muted">
                    <CaretDown size={14} />
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Section 1: Identitas Perusahaan & Jenis Modus */}
        <div className="rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
              <Buildings size={11} weight="bold" className="text-bg-elevated" />
            </div>
            <span className="text-[13px] font-semibold text-text-primary">
              Detail Perusahaan & Jenis Laporan
            </span>
          </div>

          <div className="flex flex-col gap-5">
            {/* Company Name */}
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                Nama Perusahaan / Entitas Terlapor <span className="text-bahaya-fg">*</span>
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-muted">
                  <Buildings size={14} />
                </span>
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Tulis nama perusahaan seperti di lowongan"
                  className="w-full rounded-xl border border-border bg-bg pl-9 pr-4 py-3 text-[13px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-border-focus"
                />
              </div>
            </div>

            {/* Report Type Grid */}
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                Pilih Jenis Modus Penipuan <span className="text-bahaya-fg">*</span>
              </label>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {REPORT_TYPES.map((type) => {
                  const selected = reportType === type.value;
                  return (
                    <button
                      key={type.value}
                      type="button"
                      onClick={() => setReportType(type.value)}
                      className={cn(
                        "flex flex-col items-start rounded-xl border p-3.5 text-left transition-all",
                        selected
                          ? "border-text-primary bg-text-primary/5"
                          : "border-border bg-bg hover:border-border-focus",
                      )}
                    >
                      <span className="text-[13px] font-semibold text-text-primary">{type.label}</span>
                      <span className="mt-1 text-[11px] leading-snug text-text-muted">{type.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Kronologi & Bukti Pendukung */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

          {/* Kolom Kiri: Kronologi Kejadian */}
          <div className="rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6 lg:col-span-2">
            <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
              <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
                <Note size={11} weight="bold" className="text-bg-elevated" />
              </div>
              <span className="text-[13px] font-semibold text-text-primary">
                Kronologi Kejadian
              </span>
            </div>

            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                Ceritakan urutan kejadiannya <span className="text-bahaya-fg">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-3.5 text-text-muted">
                  <Note size={14} />
                </span>
                <textarea
                  required
                  rows={8}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Contoh: Saya dihubungi via WA untuk interview kerja, lalu diminta mentransfer biaya penginapan hotel melalui agen travel palsu..."
                  className="w-full resize-none rounded-xl border border-border bg-bg pl-9 pr-4 py-3 text-[13px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-border-focus"
                />
              </div>
            </div>
          </div>

          {/* Kolom Kanan: Bukti Pendukung */}
          <div className="flex flex-col gap-6 rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6">
            <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
              <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
                <LinkSimple size={11} weight="bold" className="text-bg-elevated" />
              </div>
              <span className="text-[13px] font-semibold text-text-primary">
                Bukti Pendukung
              </span>
            </div>

            <div className="flex flex-col gap-4">
              {/* Upload Gambar Bukti */}
              <div>
                <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                  Unggah gambar bukti <span className="text-text-muted">(opsional, maks 5 MB)</span>
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                  className="hidden"
                />
                {evidencePreview ? (
                  <div className="relative overflow-hidden rounded-xl border border-border bg-bg">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={evidencePreview} alt="Preview bukti" className="h-40 w-full object-cover" />
                    <button
                      type="button"
                      onClick={handleRemoveFile}
                      className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-lg bg-bahaya-bg/80 text-bahaya-fg backdrop-blur-sm transition-colors hover:bg-bahaya-bg"
                      title="Hapus gambar"
                      aria-label="Hapus gambar"
                    >
                      <X size={12} weight="bold" />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-bg py-6 text-text-muted transition-colors hover:border-border-focus hover:text-text-secondary"
                  >
                    <UploadSimple size={20} weight="bold" />
                    <span className="text-[12px] font-medium">Pilih gambar</span>
                    <span className="text-[12px] text-text-muted">JPG, PNG, atau WEBP, maks 5 MB</span>
                  </button>
                )}
              </div>

              {/* Evidence URL */}
              <div>
                <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                  Tautan Bukti (Drive/dll) <span className="text-text-muted">(opsional)</span>
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-muted">
                    <LinkSimple size={14} />
                  </span>
                  <input
                    type="url"
                    value={evidenceUrl}
                    onChange={(e) => setEvidenceUrl(e.target.value)}
                    placeholder="Contoh: https://drive.google.com/..."
                    className="w-full rounded-xl border border-border bg-bg pl-9 pr-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-border-focus"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Disclaimer & Action */}
        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6">
          <div className="flex items-start gap-3 rounded-xl border border-waspada-border bg-waspada-bg/30 p-4">
            <Warning size={18} className="mt-0.5 shrink-0 text-waspada-fg" />
            <p className="text-[12px] leading-relaxed text-waspada-fg">
              <strong>Tulis yang benar-benar terjadi.</strong> Admin memeriksa setiap laporan sebelum dipakai, dan laporan tanpa dasar tidak akan disetujui. Menuduh tanpa bukti juga bisa berujung masalah hukum.
            </p>
          </div>

          <div className="flex items-center justify-end">
            <button
              type="submit"
              disabled={!companyName || !reportType || !description || loading || (selectedMode === "from_history" && !selectedCaseId)}
              className={buttonClass({ fullWidth: true, className: "sm:w-48" })}
            >
              {loading ? "Mengirim..." : "Kirim laporan"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
