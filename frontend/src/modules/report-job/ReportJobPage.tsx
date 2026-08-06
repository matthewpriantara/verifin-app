"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowLeft,
  Buildings,
  LinkSimple,
  Globe,
  Note,
  CheckCircle,
  Warning,
  Flag,
  CloudArrowUp,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { ReportType } from "@/types/admin";

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
  const [companyName, setCompanyName] = useState("");
  const [reportType, setReportType]   = useState<ReportType | "">("");
  const [description, setDescription] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [fileName, setFileName]       = useState("");

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // IP pelapor disimulasikan terdeteksi otomatis dari client side
  const simulatedIp = "182.253.48.117";

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName || !reportType || !description) return;

    setLoading(true);
    // Simulasikan delay network call
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setLoading(false);
    setSuccess(true);
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
            <div className="flex justify-between py-1 border-b border-border/40">
              <span>Pelapor (IP):</span>
              <span>{simulatedIp}</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Jenis Laporan:</span>
              <span>{REPORT_TYPES.find(t => t.value === reportType)?.label}</span>
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-2">
            <Link
              href="/"
              className="w-full rounded-xl bg-text-primary py-3 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 text-center"
            >
              Kembali ke Beranda
            </Link>
            <button
              onClick={() => {
                setCompanyName("");
                setReportType("");
                setDescription("");
                setEvidenceUrl("");
                setFileName("");
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
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition-colors hover:text-text-primary"
        >
          <ArrowLeft size={14} weight="bold" /> Kembali
        </Link>

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

          {/* IP Detector Banner */}
          <div className="flex shrink-0 items-center gap-3 rounded-xl border border-border bg-bg-subtle px-4 py-2.5 text-[13px]">
            <div className="flex items-center gap-2 text-text-secondary">
              <Globe size={15} className="text-text-muted" />
              <span>IP Terdeteksi:</span>
            </div>
            <span className="font-mono font-semibold text-text-primary">{simulatedIp}</span>
          </div>
        </div>
      </div>

      {/* ── Form Utama di Bagian Bawah ── */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        
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
              {/* Evidence URL */}
              <div>
                <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                  Tautan Bukti Gambar/Drive <span className="text-text-muted">(opsional)</span>
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

              {/* Upload file placeholder */}
              <div>
                <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
                  Unggah File Bukti <span className="text-text-muted">(opsional)</span>
                </label>
                <div className="relative flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-bg p-5 text-center transition-colors hover:border-border-focus">
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={handleFileChange}
                    className="absolute inset-0 cursor-pointer opacity-0"
                  />
                  <CloudArrowUp size={24} className="text-text-muted" />
                  <p className="mt-2 text-[12px] font-semibold text-text-primary">
                    {fileName || "Pilih file bukti"}
                  </p>
                  <p className="mt-0.5 text-[10px] text-text-muted">
                    Maksimal 5MB (PNG, JPG, PDF)
                  </p>
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
              disabled={!companyName || !reportType || !description || loading}
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
