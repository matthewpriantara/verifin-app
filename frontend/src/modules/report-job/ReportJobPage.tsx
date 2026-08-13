"use client";

import { useState, useEffect, Suspense, useRef } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { motion } from "motion/react";
import {
  ArrowLeft,
  Buildings,
  LinkSimple,
  Note,
  CheckCircle,
  Warning,
  Flag,
  UploadSimple,
  X,
  CaretDown,
  FolderOpen,
} from "@phosphor-icons/react";
import { cn, getHistory, type HistoryItem } from "@/lib/utils";
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
    desc: "Nama tidak terdaftar di AHU atau kantor tidak ditemukan.",
  },
  {
    value: "tppo_eksploitasi",
    label: "Indikasi TPPO & Eksploitasi",
    desc: "Penyaluran kerja ilegal ke luar negeri atau kerja paksa.",
  },
  {
    value: "pencurian_data_scam",
    label: "Pencurian Data & Task Scam",
    desc: "Meminta data sensitif (KTP) atau penipuan tugas online.",
  },
];

export default function ReportJobPage() {
  return (
    <Suspense fallback={<div className="min-h-[60vh]" />}>
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
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(urlCaseId || null);

  const [companyName, setCompanyName] = useState("");
  const [reportType, setReportType]   = useState<ReportType | "">("");
  const [description, setDescription] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  // Load history dari localStorage
  useEffect(() => {
    const items = getHistory();
    setHistoryItems(items);

    // Jika ada caseId dari URL, coba pre-fill dari sessionStorage
    if (urlCaseId) {
      setSelectedCaseId(urlCaseId);
      const raw = sessionStorage.getItem("verifin:last-report");
      if (raw) {
        try {
          const report = JSON.parse(raw);
          const companies = report?.entities?.companies;
          if (Array.isArray(companies) && companies.length > 0 && companies[0]) {
            setCompanyName(companies[0]);
          }
          const urls = report?.entities?.urls;
          if (Array.isArray(urls) && urls.length > 0 && urls[0]) {
            setEvidenceUrl(urls[0]);
          }
        } catch {
          // ignore
        }
      }
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
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat mengirim laporan.");
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
            Laporan Anda mengenai <span className="font-semibold">{companyName}</span> telah berhasil kami terima.
            Laporan ini akan ditinjau oleh tim moderator admin sebelum mempengaruhi skor risiko perusahaan.
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
                onClick={() => router.push(`/report/${activeCaseId}`)}
                className="w-full rounded-xl bg-text-primary py-3 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 text-center"
              >
                Kembali ke Laporan
              </button>
            ) : (
              <Link
                href="/"
                className="w-full rounded-xl bg-text-primary py-3 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 text-center"
              >
                Kembali ke Beranda
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
              className="w-full rounded-xl border border-border bg-bg-subtle py-3 text-[13px] font-medium text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary"
            >
              Kirim Laporan Lain
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 lg:py-20">
      
      {/* ── Header Bagian Atas ── */}
      <div className="mb-10">
        {activeCaseId ? (
          <button
            onClick={() => router.back()}
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition-colors hover:text-text-primary"
          >
            <ArrowLeft size={14} weight="bold" /> Kembali ke Laporan
          </button>
        ) : (
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition-colors hover:text-text-primary"
          >
            <ArrowLeft size={14} weight="bold" /> Kembali
          </Link>
        )}

        <div className="mt-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">
              Community Watch
            </p>
            <h1 className="mt-1.5 text-3xl font-semibold tracking-tight text-text-primary sm:text-4xl">
              Laporkan Lowongan Mencurigakan
            </h1>
            <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-text-secondary">
              Bantu lindungi sesama pencari kerja dari kejahatan rekrutmen. Setiap laporan akan dimoderasi terlebih dahulu oleh tim admin sebelum mempengaruhi skor risiko perusahaan.
            </p>
          </div>
        </div>
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
                  Pilih dari hasil verifikasi yang sudah Anda lakukan
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
                    <option value="">— Pilih kasus —</option>
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
                  placeholder="Contoh: PT Investasi Cerdas Sejahtera"
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
                Jelaskan kronologis kejadian secara jelas dan rinci <span className="text-bahaya-fg">*</span>
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
                  placeholder="Tuliskan secara lengkap bagaimana modus terjadi. Misalnya: Saya dihubungi via WA untuk interview kerja, lalu diminta mentransfer biaya penginapan hotel melalui agen travel palsu..."
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
                  Upload Gambar Bukti <span className="text-text-muted">(opsional, max 5MB)</span>
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
                    <img src={evidencePreview} alt="Preview bukti" className="h-40 w-full object-cover" />
                    <button
                      type="button"
                      onClick={handleRemoveFile}
                      className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-lg bg-bahaya-bg/80 text-bahaya-fg backdrop-blur-sm transition-colors hover:bg-bahaya-bg"
                      title="Hapus gambar"
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
                    <span className="text-[11px] font-medium">Klik untuk upload gambar</span>
                    <span className="text-[10px] text-text-muted">JPG, PNG, WebP — maks 5MB</span>
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
              <strong>Pernyataan Kebenaran Data:</strong> Pastikan seluruh data dan penjelasan yang Anda sampaikan didasari kejadian nyata dan bukti yang sah. Laporan yang bersifat fitnah atau penyebaran data palsu dapat berimplikasi pada sanksi hukum sesuai peraturan yang berlaku di Indonesia.
            </p>
          </div>

          <div className="flex items-center justify-end">
            <button
              type="submit"
              disabled={!companyName || !reportType || !description || loading || (selectedMode === "from_history" && !selectedCaseId)}
              className="w-full rounded-xl bg-text-primary py-3.5 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 disabled:opacity-40 sm:w-48"
            >
              {loading ? "Mengirim..." : "Kirim Laporan"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
