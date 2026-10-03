"use client";

import { motion } from "motion/react";
import {
  Scan,
  Cpu,
  Globe,
  WarningCircle,
  CheckCircle,
  Graph,
  ShieldWarning,
  MapPin,
  Envelope,
  Phone,
  CurrencyDollar,
  Buildings,
} from "@phosphor-icons/react";

export function RadarPipelineDemo() {
  return (
    <div className="relative mt-12 w-full overflow-hidden rounded-3xl border border-border bg-bg-elevated p-6 shadow-[0_4px_24px_rgba(44,40,37,0.06)] sm:p-8 lg:p-10">
      {/* Background subtle radar grid pattern */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, var(--border) 1px, transparent 0)",
          backgroundSize: "28px 28px",
        }}
      />

      {/* Header Pipeline Demo */}
      <div className="relative z-10 mb-8 flex flex-col items-center justify-between gap-4 border-b border-border/60 pb-6 sm:flex-row">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Live Pipeline Simulation
            </span>
          </div>
          <h3 className="mt-1 text-lg font-bold text-text-primary sm:text-xl">
            Simulasi Deteksi Multi-Sinyal Verifin
          </h3>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-border bg-bg-subtle px-3 py-1 font-mono text-[11px] text-text-secondary">
          <span>Target Kasus:</span>
          <span className="font-bold text-text-primary">Loker Admin Telegram #2026-X</span>
        </div>
      </div>

      {/* Main 3-Column Pipeline Grid */}
      <div className="relative z-10 grid grid-cols-1 items-center gap-8 lg:grid-cols-12 lg:gap-6">
        {/* ── 1. KIRI: Sinyal Ekstraksi Masuk (3 Cols) ── */}
        <div className="flex flex-col gap-4 lg:col-span-3">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            01. Sumber & Ekstraksi
          </p>

          {/* Sinyal 1: OCR */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/70 p-3.5 shadow-2xs transition-colors hover:border-border-focus"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-aman-bg text-aman-fg border border-aman-border">
              <Scan size={18} weight="bold" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-semibold text-text-primary">PaddleOCR</span>
                <CheckCircle size={14} weight="fill" className="text-emerald-600" />
              </div>
              <p className="text-[11px] text-text-muted">Pindai teks poster & tipografi</p>
            </div>
          </motion.div>

          {/* Sinyal 2: Hybrid NER */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/70 p-3.5 shadow-2xs transition-colors hover:border-border-focus"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-aman-bg text-aman-fg border border-aman-border">
              <Cpu size={18} weight="bold" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-semibold text-text-primary">Hybrid NER</span>
                <CheckCircle size={14} weight="fill" className="text-emerald-600" />
              </div>
              <p className="text-[11px] text-text-muted">Ekstraksi entitas & nomor kontak</p>
            </div>
          </motion.div>

          {/* Sinyal 3: URL Inspector */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/70 p-3.5 shadow-2xs transition-colors hover:border-border-focus"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-aman-bg text-aman-fg border border-aman-border">
              <Globe size={18} weight="bold" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-semibold text-text-primary">URL Ingestion</span>
                <CheckCircle size={14} weight="fill" className="text-emerald-600" />
              </div>
              <p className="text-[11px] text-text-muted">Analisis domain & landing page</p>
            </div>
          </motion.div>
        </div>

        {/* ── 2. TENGAH: Kartu Loker yang Sedang Diinspeksi (5 Cols) ── */}
        <div className="lg:col-span-5">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="relative rounded-2xl border-2 border-border-focus bg-bg p-5 shadow-lg"
          >
            {/* Tag Sedang Dipindai */}
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-text-primary text-bg">
                  <Buildings size={16} weight="bold" />
                </div>
                <div>
                  <h4 className="text-[14px] font-bold text-text-primary">PT Samudra Sentosa Abadi</h4>
                  <p className="text-[11px] text-text-muted">Posisi: Staff Admin Entri Data</p>
                </div>
              </div>
              <span className="rounded-full border border-waspada-border bg-waspada-bg px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase text-waspada-fg">
                Inspecting
              </span>
            </div>

            {/* Detail Entitas Terdeteksi */}
            <div className="space-y-2.5 text-[12px]">
              {/* Gaji */}
              <div className="flex items-center justify-between rounded-xl border border-bahaya-border bg-bahaya-bg/40 p-2.5">
                <div className="flex items-center gap-2 text-text-secondary">
                  <CurrencyDollar size={16} className="text-bahaya-fg shrink-0" />
                  <span>Tawaran Gaji:</span>
                </div>
                <div className="text-right">
                  <span className="font-bold text-bahaya-fg">Rp 15.000.000 / minggu</span>
                  <p className="text-[10px] text-bahaya-fg/80">⚠ Gaji di luar batas wajar (Anomali)</p>
                </div>
              </div>

              {/* Kontak WA */}
              <div className="flex items-center justify-between rounded-xl border border-bahaya-border bg-bahaya-bg/40 p-2.5">
                <div className="flex items-center gap-2 text-text-secondary">
                  <Phone size={16} className="text-bahaya-fg shrink-0" />
                  <span>Kontak PIC:</span>
                </div>
                <div className="text-right">
                  <span className="font-mono font-bold text-text-primary">0812-9844-xxxx</span>
                  <p className="text-[10px] text-bahaya-fg font-medium">⚠ 5x Laporan scam kontak</p>
                </div>
              </div>

              {/* Email */}
              <div className="flex items-center justify-between rounded-xl border border-waspada-border bg-waspada-bg/40 p-2.5">
                <div className="flex items-center gap-2 text-text-secondary">
                  <Envelope size={16} className="text-waspada-fg shrink-0" />
                  <span>Email Rekrutmen:</span>
                </div>
                <div className="text-right">
                  <span className="font-mono text-text-primary">karir.samudra@gmail.com</span>
                  <p className="text-[10px] text-waspada-fg">⚠ Domain publik gratis (Bukan korporat)</p>
                </div>
              </div>

              {/* Lokasi */}
              <div className="flex items-center justify-between rounded-xl border border-border bg-bg-elevated p-2.5">
                <div className="flex items-center gap-2 text-text-secondary">
                  <MapPin size={16} className="text-text-muted shrink-0" />
                  <span>Alamat Tercantum:</span>
                </div>
                <span className="truncate max-w-[180px] text-text-muted text-[11px]">
                  Ruko Golden Plaza No. 14, Jaksel
                </span>
              </div>
            </div>

            {/* Advance Fee Trap Warning */}
            <div className="mt-3.5 rounded-xl border border-bahaya-border bg-bahaya-bg p-3 text-center">
              <span className="flex items-center justify-center gap-1.5 font-mono text-[11px] font-bold text-bahaya-fg">
                <WarningCircle size={15} weight="fill" />
                Indikasi Pungutan Biaya Training Rp 350.000
              </span>
            </div>
          </motion.div>
        </div>

        {/* ── 3. KANAN: Panel Hasil Audit Risiko OSINT (4 Cols) ── */}
        <div className="flex flex-col gap-4 lg:col-span-4">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            02. Profil & Atribusi Risiko
          </p>

          <motion.div
            initial={{ opacity: 0, x: 16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="rounded-2xl border border-border bg-bg-subtle/50 p-4.5"
          >
            {/* Risk Score Progress Bar */}
            <div className="mb-4">
              <div className="flex items-center justify-between text-[11px] font-mono text-text-muted mb-1.5">
                <span>RISK EVALUATION COMPLETE</span>
                <span className="font-bold text-bahaya-fg">84 / 100</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: "84%" }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, ease: "easeOut" }}
                  className="h-full rounded-full bg-bahaya-fg"
                />
              </div>
            </div>

            {/* OSINT Kanal Breakdown */}
            <div className="space-y-2 border-b border-border/60 pb-3.5 mb-3.5 text-[12px]">
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">WHOIS / DNS Usia Domain</span>
                <span className="rounded bg-bahaya-bg px-2 py-0.5 font-mono text-[10px] font-bold text-bahaya-fg">
                  Tinggi 92
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">Reputasi Nomor Telepon</span>
                <span className="rounded bg-bahaya-bg px-2 py-0.5 font-mono text-[10px] font-bold text-bahaya-fg">
                  Tinggi 86
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">Geocoding OpenStreetMap</span>
                <span className="rounded bg-waspada-bg px-2 py-0.5 font-mono text-[10px] font-bold text-waspada-fg">
                  Waspada 65
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-secondary">Deteksi Anomali Gaji & Biaya</span>
                <span className="rounded bg-bahaya-bg px-2 py-0.5 font-mono text-[10px] font-bold text-bahaya-fg">
                  Kritis 95
                </span>
              </div>
            </div>

            {/* Sinyal Keterhubungan Graf */}
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                Sinyal Jejaring Fraud (NetworkX):
              </span>
              <div className="mt-2 space-y-1.5">
                <div className="flex items-start gap-2 rounded-lg border border-bahaya-border bg-bahaya-bg/60 p-2 text-[11px] text-bahaya-fg">
                  <Graph size={15} weight="bold" className="shrink-0 mt-0.5" />
                  <span>Nomor terhubung dengan laporan sindikat loker fiktif <strong>Kasus #104</strong></span>
                </div>
                <div className="flex items-start gap-2 rounded-lg border border-waspada-border bg-waspada-bg/60 p-2 text-[11px] text-waspada-fg">
                  <ShieldWarning size={15} weight="bold" className="shrink-0 mt-0.5" />
                  <span>Klaim nama PT legal dicatut tanpa izin rekrutmen resmi</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
