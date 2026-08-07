"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowLeft,
  CircleNotch,
  Warning,
  CheckCircle,
  Lightbulb,
  Buildings,
  Phone,
  EnvelopeSimple,
  LinkSimple,
  MapPin,
  Money,
  Globe,
  ShieldCheck,
  ShieldWarning,
  ShieldSlash,
  ChartBar,
  Fingerprint,
  Graph,
  MagnifyingGlass,
  Scan,
  Database,
  ChatTeardropText,
  Clock,
  ArrowSquareOut,
  FileText,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { ShapChart } from "@/modules/report/ShapChart";
import { REPORT_STORAGE_KEY, cn, normalizeVerdict, verdictTone } from "@/lib/utils";
import type { VerifyResponse, ExtractedEntities } from "@/types/verify";

/* ─── helpers ──────────────────────────────────────────────────────────── */
function VerdictIcon({ verdict, size = 36 }: { verdict: string; size?: number }) {
  const v = normalizeVerdict(verdict);
  if (v === "AMAN")    return <ShieldCheck   size={size} weight="fill" />;
  if (v === "WASPADA") return <ShieldWarning size={size} weight="fill" />;
  if (v === "BAHAYA")  return <ShieldSlash   size={size} weight="fill" />;
  return <Warning size={size} weight="fill" />;
}
function vLabel(v: string) {
  const n = normalizeVerdict(v);
  return n === "AMAN" ? "Aman" : n === "WASPADA" ? "Waspada" : n === "BAHAYA" ? "Bahaya" : "Error";
}

const ENTITY_FIELDS: { key: keyof ExtractedEntities; label: string; icon: React.ElementType }[] = [
  { key: "companies", label: "Perusahaan", icon: Buildings },
  { key: "contacts",  label: "Kontak/HP",  icon: Phone },
  { key: "emails",    label: "Email",       icon: EnvelopeSimple },
  { key: "urls",      label: "URL",         icon: LinkSimple },
  { key: "addresses", label: "Alamat",      icon: MapPin },
  { key: "salaries",  label: "Gaji",        icon: Money },
];

/* ─── Bento Card ────────────────────────────────────────────────────────── */
function BentoCard({ title, icon: Icon, children, className }: {
  title: string; icon: React.ElementType;
  children: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("rounded-2xl border border-border bg-bg-elevated p-5", className)}>
      <div className="mb-3 flex items-center gap-2 border-b border-border pb-2.5">
        <Icon size={16} weight="bold" className="text-text-muted" />
        <h3 className="text-[13px] font-semibold text-text-primary">{title}</h3>
      </div>
      {children}
    </div>
  );
}

/* ─── Factor row ────────────────────────────────────────────────────────── */
function FactorItem({ text, kind }: { text: string; kind: "risk" | "safe" | "reco" }) {
  const Icon = kind === "risk" ? Warning : kind === "safe" ? CheckCircle : Lightbulb;
  const col  = kind === "risk" ? "text-bahaya-fg" : kind === "safe" ? "text-aman-fg" : "text-waspada-fg";
  return (
    <li className="flex items-start gap-2.5">
      <span className={cn("mt-0.5 shrink-0", col)}><Icon size={15} weight="fill" /></span>
      <span className="text-[14px] leading-relaxed text-text-secondary">{text}</span>
    </li>
  );
}

/* ─── OSINT badge ───────────────────────────────────────────────────────── */
function OsintBadge({ label, status, detail }: {
  label: string; status: "ok" | "warn" | "unknown"; detail?: string;
}) {
  return (
    <div className={cn(
      "flex items-center gap-2 rounded-xl border px-3 py-2",
      status === "ok"    && "border-aman-border bg-aman-bg/40",
      status === "warn"  && "border-bahaya-border bg-bahaya-bg/40",
      status === "unknown" && "border-border bg-bg-subtle"
    )}>
      {status === "ok"    && <CheckCircle size={15} weight="fill" className="shrink-0 text-aman-fg" />}
      {status === "warn"  && <Warning     size={15} weight="fill" className="shrink-0 text-bahaya-fg" />}
      {status === "unknown" && <Clock     size={15} weight="bold" className="shrink-0 text-text-muted" />}
      <div className="min-w-0">
        <p className={cn("text-[13px] font-semibold leading-none",
          status === "ok" ? "text-aman-fg" : status === "warn" ? "text-bahaya-fg" : "text-text-muted"
        )}>{label}</p>
        {detail && <p className="mt-0.5 text-[11px] text-text-muted">{detail}</p>}
      </div>
    </div>
  );
}

/* ─── Risk gauge SVG ────────────────────────────────────────────────────── */
/* Menampilkan RISK SCORE: 0 = sangat aman (hijau), 100 = sangat berbahaya (merah).
   Sesuai risk_score dari backend — BUKAN trust score. Semakin penuh arc = semakin berisiko. */
function RiskGauge({ score, verdict }: { score: number; verdict: string }) {
  const v = normalizeVerdict(verdict);
  const c = Math.max(0, Math.min(100, score));
  const circ = Math.PI * 52;
  const filled = (c / 100) * circ;
  const col = v === "AMAN" ? "#2f5c34" : v === "WASPADA" ? "#7a5500" : v === "BAHAYA" ? "#8f2f2d" : "#8a8279";
  return (
    <div className="flex flex-col items-center">
      <svg width="130" height="72" viewBox="0 0 130 72">
        <path d="M 13 65 A 52 52 0 0 1 117 65" fill="none"
          stroke="var(--bg-muted,#e8e2d9)" strokeWidth="10" strokeLinecap="round" />
        <motion.path d="M 13 65 A 52 52 0 0 1 117 65" fill="none"
          stroke={col} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - filled }}
          transition={{ duration: 0.9, ease: "easeOut", delay: 0.3 }}
        />
        <text x="65" y="60" textAnchor="middle" fontSize="22" fontWeight="800"
          fill={col} fontFamily="monospace">{c}</text>
      </svg>
      <p className="font-mono text-[11px] text-text-muted">dari 100</p>
    </div>
  );
}

/* ─── Derived evidence metrics (semua dari data nyata) ─────────────────── */
function computeEvidenceMetrics(report: VerifyResponse) {
  const osint = report.osint;
  const domain = (osint?.domain as Record<string, unknown> | undefined) || {};
  const emailSec = (osint?.email_security as Record<string, unknown> | undefined) || {};
  const addrs = (osint?.address_validations as Record<string, unknown>[] | undefined) || [];
  const phones = osint?.phones || [];
  const web = osint?.web;
  const threads = osint?.threads;

  // Probe yang "dijalankan" = field ada di payload. Probe yang "sukses" = ada data bermakna.
  const probes: { ran: boolean; hit: boolean }[] = [];
  probes.push({ ran: true, hit: domain.age_years != null || domain.created_at != null });
  probes.push({ ran: true, hit: Object.keys(emailSec).length > 0 });
  probes.push({ ran: addrs.length > 0, hit: addrs.some((a) => a.found || a.address_found) });
  probes.push({ ran: phones.length > 0, hit: phones.some((p) => p.found || p.reported_fraud === false) });
  probes.push({ ran: Boolean(web?.enabled), hit: Boolean(web?.websites?.length || web?.searches?.length) });
  probes.push({ ran: Boolean(threads?.enabled), hit: Boolean(threads?.posts?.length || threads?.profiles?.length) });

  const ranProbes = probes.filter((p) => p.ran);
  const coverage = ranProbes.length === 0 ? 0 : Math.round((ranProbes.filter((p) => p.hit).length / probes.length) * 100);
  const coverageCount = `${ranProbes.filter((p) => p.hit).length}/${probes.length}`;

  // Confidence: dari model_used ada & shap ada => reasoning jalan; plus coverage.
  const hasReasoning = Boolean(report.summary) && Boolean(report.model_used);
  const hasShap = Boolean(report.shap_explanation?.feature_contributions?.length);
  let confidence = 0;
  if (hasReasoning) confidence += 50;
  if (hasShap) confidence += 20;
  confidence += Math.round(coverage * 0.3);
  confidence = Math.min(99, confidence);

  return { coverage, coverageCount, confidence, hasShap };
}

/* ─── Page ──────────────────────────────────────────────────────────────── */
export default function ReportPage() {
  const [report, setReport] = useState<VerifyResponse | null>(null);
  const [ready, setReady] = useState(false);
  const [auditMode, setAuditMode] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      try {
        const raw = sessionStorage.getItem(REPORT_STORAGE_KEY);
        setReport(raw ? (JSON.parse(raw) as VerifyResponse) : null);
      } catch { setReport(null); }
      finally { if (!cancelled) setReady(true); }
    });
    return () => { cancelled = true; };
  }, []);

  if (!ready) return (
    <div className="flex min-h-[50vh] items-center justify-center gap-2.5 text-text-muted">
      <CircleNotch size={16} className="animate-spin" />
      <span className="text-[14px]">Memuat laporan...</span>
    </div>
  );

  if (!report) return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center sm:px-6">
      <h1 className="text-2xl font-semibold text-text-primary">Belum ada laporan</h1>
      <p className="mt-2 text-[15px] text-text-secondary">Verifikasi dulu dari halaman utama.</p>
      <div className="mt-8"><Link href="/"><Button>Ke verifikasi</Button></Link></div>
    </div>
  );

  const tone    = verdictTone(report.verdict);
  const clamped = Math.max(0, Math.min(100, report.risk_score));
  const entities = report.entities;
  const osint   = report.osint;
  const shap    = report.shap_explanation;
  const nc      = (report as unknown as Record<string,unknown>).network_context as Record<string,unknown> | undefined;
  const metrics = computeEvidenceMetrics(report);

  const domain = (osint?.domain as Record<string, unknown> | undefined) || {};
  const addrs = (osint?.address_validations as Record<string, unknown>[] | undefined) || [];
  const phones = osint?.phones || [];
  const timing = (osint?.timing as Record<string, unknown> | undefined) || {};
  const ocrTiming = (timing.ocr as Record<string, unknown> | undefined) || {};
  const ocrSec = typeof ocrTiming.inference_sec === "number" ? ocrTiming.inference_sec : null;
  const osintSec = typeof timing.osint_parallel_sec === "number" ? timing.osint_parallel_sec : null;

  const osintBadges = [
    {
      label: "WHOIS Domain",
      status: domain.age_years != null ? "ok" : "unknown",
      detail: `Umur: ${domain.age_years ?? "tidak diketahui"}`,
    },
    {
      label: "Kredibel HP",
      status: phones.length > 0
        ? (phones.some((p) => p.reported_fraud) ? "warn" : "ok")
        : "unknown",
      detail: phones.length > 0
        ? (phones.some((p) => p.reported_fraud) ? "Ada laporan fraud" : "Bersih")
        : "Tidak ada nomor",
    },
    {
      label: "Alamat OSM",
      status: addrs.length > 0
        ? (addrs.some((a) => a.found || a.address_found) ? "ok" : "warn")
        : "unknown",
      detail: addrs.length > 0
        ? `${addrs.filter((a) => a.found || a.address_found).length}/${addrs.length} ditemukan`
        : "Tidak ada alamat",
    },
    {
      label: "Web Evidence",
      status: osint?.web?.enabled
        ? ((osint.web.websites?.length || osint.web.searches?.length) ? "ok" : "unknown")
        : "unknown",
      detail: osint?.web?.enabled ? "SERP publik" : "Nonaktif",
    },
    {
      label: "Threads/Sosmed",
      status: osint?.threads?.enabled
        ? ((osint.threads.posts?.length || osint.threads.profiles?.length) ? "ok" : "unknown")
        : "unknown",
      detail: osint?.threads?.enabled ? "Jejak publik" : "Nonaktif",
    },
    {
      label: "Legalitas AHU/OSS",
      status: "unknown",
      detail: "API publik tidak tersedia",
    },
  ] as const;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-12">

      {/* ── Top bar ── */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition-colors hover:text-text-primary">
          <ArrowLeft size={14} weight="bold" /> Verifikasi baru
        </Link>
        <div className="flex items-center gap-2">
          <span className="hidden font-mono text-[11px] text-text-muted sm:block">
            {auditMode ? "Mode Audit Forensik" : "Mode Ringkas"}
          </span>
          <button
            onClick={() => setAuditMode(!auditMode)}
            className={cn(
              "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
              auditMode ? "bg-aman-fg" : "bg-bg-muted"
            )}
            aria-label="Toggle audit mode"
          >
            <span className={cn(
              "inline-block h-4 w-4 transform rounded-full bg-bg-elevated transition-transform",
              auditMode ? "translate-x-6" : "translate-x-1"
            )} />
          </button>
        </div>
      </div>

      {!auditMode ? (
        /* ── MODE RINGKAS (User-First, semua dari data nyata) ─────────────── */
        <div className="space-y-4">

          {/* Verdict hero */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className={cn("rounded-2xl border p-6 sm:p-8", tone.bg, tone.border)}
          >
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
              <div className="flex items-start gap-4 flex-1">
                <div className={cn("shrink-0", tone.fg)}>
                  <VerdictIcon verdict={report.verdict} size={44} />
                </div>
                <div className="flex-1">
                  <p className="font-mono text-[12px] uppercase tracking-widest text-text-muted">Hasil Verifikasi</p>
                  <p className={cn("mt-1 text-4xl font-bold tracking-tight sm:text-5xl", tone.fg)}>
                    {vLabel(report.verdict)}
                  </p>
                </div>
              </div>
              <div className="flex flex-col items-center border-t border-border/40 pt-4 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-6">
                <RiskGauge score={clamped} verdict={report.verdict} />
                <p className="mt-1 text-[12px] font-mono text-text-muted">Skor Risiko</p>
                <p className="text-[10px] text-text-muted/70">0 aman · 100 bahaya</p>
              </div>
            </div>
            {report.summary && (
              <p className="mt-5 max-w-3xl text-[15px] leading-relaxed text-text-secondary">
                {report.summary}
              </p>
            )}
          </motion.div>

          {/* Grid: faktor risiko + faktor aman */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <BentoCard title="Yang Perlu Diwaspadai" icon={Warning} className="h-full">
                {(report.risk_factors || []).length === 0 ? (
                  <p className="text-[14px] text-text-muted">Tidak ada faktor risiko terdeteksi.</p>
                ) : (
                  <ul className="space-y-3">
                    {report.risk_factors.map((f, i) => <FactorItem key={i} text={f} kind="risk" />)}
                  </ul>
                )}
              </BentoCard>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}>
              <BentoCard title="Yang Terlihat Baik" icon={CheckCircle} className="h-full">
                {(report.safe_factors || []).length === 0 ? (
                  <p className="text-[14px] text-text-muted">Tidak ada faktor aman tercatat.</p>
                ) : (
                  <ul className="space-y-3">
                    {report.safe_factors.map((f, i) => <FactorItem key={i} text={f} kind="safe" />)}
                  </ul>
                )}
              </BentoCard>
            </motion.div>
          </div>

          {/* Rekomendasi */}
          {(report.recommendations || []).length > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}>
              <BentoCard title="Yang Sebaiknya Kamu Lakukan" icon={Lightbulb}>
                <ul className="space-y-3">
                  {report.recommendations.map((r, i) => <FactorItem key={i} text={r} kind="reco" />)}
                </ul>
              </BentoCard>
            </motion.div>
          )}

          {/* Entitas terdeteksi */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}>
            <BentoCard title="Info yang Terdeteksi dari Lowongan" icon={Scan}>
              {!entities || !ENTITY_FIELDS.some(({ key }) => (entities[key] || []).length > 0) ? (
                <p className="text-[14px] text-text-muted">Tidak ada entitas diekstrak.</p>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {ENTITY_FIELDS.map(({ key, label, icon: Icon }) => {
                    const vals = entities[key] || [];
                    if (vals.length === 0) return null;
                    return (
                      <div key={key}>
                        <div className="mb-1.5 flex items-center gap-1.5">
                          <Icon size={12} weight="bold" className="text-text-muted" />
                          <p className="text-[12px] font-medium text-text-muted">{label}</p>
                        </div>
                        <div className="space-y-1">
                          {vals.map((val) => (
                            <p key={val} className="break-all rounded-lg bg-bg-subtle px-2.5 py-1.5 font-mono text-[12px] text-text-secondary">
                              {val}
                            </p>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </BentoCard>
          </motion.div>

          {/* CTA + fitur lanjutan (dilabeli jujur) */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.26 }}
            className="flex flex-col gap-3">
            <Link href="/"><Button fullWidth>Verifikasi lowongan lain</Button></Link>
            <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
              <Link href="/report-job" className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3 py-1.5 text-[12px] text-text-secondary hover:border-border-focus hover:text-text-primary transition-all">
                <ChatTeardropText size={13} /> Lapor Komunitas
              </Link>
            </div>
            <p className="text-center text-[12px] text-text-muted">
              Ingin lihat bukti teknis lengkap? Aktifkan <button onClick={() => setAuditMode(true)} className="font-semibold text-text-primary underline underline-offset-2">Mode Audit</button> di atas.
            </p>
          </motion.div>
        </div>
      ) : (
        /* ── MODE AUDIT FORENSIK (semua dari data nyata) ─────────────────── */
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">

          {/* Verdict hero */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className={cn("col-span-4 rounded-2xl border p-6 sm:col-span-2 sm:p-8", tone.bg, tone.border)}
          >
            <div className="flex items-start gap-4">
              <div className={cn("shrink-0", tone.fg)}>
                <VerdictIcon verdict={report.verdict} size={40} />
              </div>
              <div className="flex-1">
                <p className="font-mono text-[12px] uppercase tracking-widest text-text-muted">Hasil Verifikasi</p>
                <p className={cn("mt-1 text-4xl font-bold tracking-tight", tone.fg)}>
                  {vLabel(report.verdict)}
                </p>
                {report.summary && (
                  <p className="mt-3 text-[15px] leading-relaxed text-text-secondary">{report.summary}</p>
                )}
              </div>
            </div>
          </motion.div>

          {/* Gauge */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.06 }}
            className={cn("col-span-4 flex flex-col items-center justify-center gap-2 rounded-2xl border p-6 sm:col-span-2", tone.bg, tone.border)}
          >
            <RiskGauge score={clamped} verdict={report.verdict} />
            <p className={cn("text-2xl font-bold", tone.fg)}>{vLabel(report.verdict)}</p>
            <div className="flex gap-4 text-[12px] font-mono text-text-muted">
              <span className="text-aman-fg">0 Aman</span>
              <span>·</span>
              <span className="text-waspada-fg">50 Waspada</span>
              <span>·</span>
              <span className="text-bahaya-fg">100 Bahaya</span>
            </div>
          </motion.div>

          {/* OSINT badges + metrics dari data nyata */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="col-span-4 rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6"
          >
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3.5">
              <div className="flex items-center gap-2">
                <MagnifyingGlass size={16} weight="bold" className="text-text-muted" />
                <h3 className="text-[14px] font-bold text-text-primary">Metrik Bukti OSINT</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-xl border border-aman-border bg-aman-bg px-3 py-1 font-mono text-[11px] font-bold text-aman-fg">
                  <ShieldCheck size={12} weight="fill" /> Confidence: {metrics.confidence}%
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-bg-subtle px-3 py-1 font-mono text-[11px] font-bold text-text-primary">
                  <Database size={12} /> Coverage: {metrics.coverage}% ({metrics.coverageCount} probe)
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              {osintBadges.map((b) => (
                <OsintBadge key={b.label} label={b.label} status={b.status} detail={b.detail} />
              ))}
            </div>
            <p className="mt-3 text-[11px] text-text-muted">
              Coverage = proporsi probe OSINT yang mengembalikan data bermakna. Confidence dihitung dari ketersediaan reasoning + XAI + coverage.
            </p>
          </motion.div>

          {/* SHAP */}
          {shap && shap.feature_contributions.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }}
              className="col-span-4 lg:col-span-3">
              <BentoCard title="Evidence Attribution (SHAP)" icon={ChartBar} className="h-full">
                <p className="mb-4 text-[14px] text-text-secondary">
                  Kontribusi tiap sinyal bukti terhadap skor risiko.{" "}
                  <span className="font-medium text-text-primary">Transparan — bukan black box.</span>
                </p>
                <ShapChart shap={shap} />
              </BentoCard>
            </motion.div>
          )}

          {/* Entitas */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }}
            className={cn("col-span-4", shap && shap.feature_contributions.length > 0 ? "lg:col-span-1" : "lg:col-span-4")}>
            <BentoCard title="Entitas Terdeteksi" icon={Scan} className="h-full">
              <p className="mb-3 text-[12px] text-text-muted">PaddleOCR + Regex NER</p>
              {!entities || !ENTITY_FIELDS.some(({ key }) => (entities[key] || []).length > 0) ? (
                <p className="text-[14px] text-text-muted">Tidak ada entitas diekstrak.</p>
              ) : (
                <div className="space-y-3">
                  {ENTITY_FIELDS.map(({ key, label, icon: Icon }) => {
                    const vals = entities[key] || [];
                    if (vals.length === 0) return null;
                    return (
                      <div key={key}>
                        <div className="mb-1 flex items-center gap-1.5">
                          <Icon size={11} weight="bold" className="text-text-muted" />
                          <p className="text-[12px] font-medium text-text-muted">{label}</p>
                        </div>
                        <div className="space-y-1">
                          {vals.map((val) => (
                            <p key={val} className="break-all rounded-lg bg-bg-subtle px-2.5 py-1.5 font-mono text-[12px] text-text-secondary">
                              {val}
                            </p>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </BentoCard>
          </motion.div>

          {/* Faktor risiko + aman */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}
            className="col-span-4 sm:col-span-2">
            <BentoCard title="Faktor Risiko" icon={Warning} className="h-full">
              {(report.risk_factors || []).length === 0 ? (
                <p className="text-[14px] text-text-muted">Tidak ada faktor risiko terdeteksi.</p>
              ) : (
                <ul className="space-y-3">
                  {report.risk_factors.map((f, i) => <FactorItem key={i} text={f} kind="risk" />)}
                </ul>
              )}
            </BentoCard>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="col-span-4 sm:col-span-2">
            <BentoCard title="Faktor Aman" icon={CheckCircle} className="h-full">
              {(report.safe_factors || []).length === 0 ? (
                <p className="text-[14px] text-text-muted">Tidak ada faktor aman tercatat.</p>
              ) : (
                <ul className="space-y-3">
                  {report.safe_factors.map((f, i) => <FactorItem key={i} text={f} kind="safe" />)}
                </ul>
              )}
            </BentoCard>
          </motion.div>

          {/* Rekomendasi */}
          {(report.recommendations || []).length > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}
              className="col-span-4 sm:col-span-2">
              <BentoCard title="Rekomendasi" icon={Lightbulb} className="h-full">
                <ul className="space-y-3">
                  {report.recommendations.map((r, i) => <FactorItem key={i} text={r} kind="reco" />)}
                </ul>
              </BentoCard>
            </motion.div>
          )}

          {/* Fraud network + pipeline */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24 }}
            className="col-span-4 sm:col-span-2">
            <div className="space-y-4 h-full">
              <BentoCard title="Fraud Network" icon={Graph}>
                <p className="mb-3 text-[13px] text-text-muted">Case-memory entity graph — cocokkan dengan riwayat kasus</p>
                {nc ? (
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between rounded-lg bg-bg-subtle px-3 py-2.5">
                      <span className="text-[14px] text-text-secondary">Terhubung jaringan fraud</span>
                      <span className={cn("text-[14px] font-bold", nc.entity_in_fraud_network ? "text-bahaya-fg" : "text-aman-fg")}>
                        {nc.entity_in_fraud_network ? "Ya" : "Tidak"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg bg-bg-subtle px-3 py-2.5">
                      <span className="text-[14px] text-text-secondary">Kasus terkait</span>
                      <span className="font-mono text-[14px] font-semibold text-text-primary">
                        {String(nc.total_case_count ?? 0)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-[14px] text-text-muted">Belum ada kasus untuk dibandingkan.</p>
                )}
              </BentoCard>

              <BentoCard title="Pipeline Analisis" icon={Fingerprint}>
                <div className="space-y-2">
                  {[
                    { k: "OCR",   v: ocrSec != null ? `PaddleOCR · ${ocrSec}s` : "PaddleOCR + OpenCV CLAHE" },
                    { k: "NER",   v: "Hybrid Regex + LLM Extraction" },
                    { k: "OSINT", v: osintSec != null ? `${osintBadges.length} probe · ${osintSec}s` : `${osintBadges.length} probe paralel` },
                    { k: "Graf",  v: "Case-memory entity graph" },
                    { k: "AI",    v: report.model_used || "Verifin AI (LLM)" },
                    { k: "XAI",   v: "SHAP Additive Explainer" },
                  ].map(({ k, v }) => (
                    <div key={k} className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-medium text-text-secondary">{k}</span>
                      <span className="truncate font-mono text-[12px] text-text-muted">{v}</span>
                    </div>
                  ))}
                </div>
              </BentoCard>
            </div>
          </motion.div>

          {/* Peta lokasi (data nyata) */}
          <MapSection osint={osint} entities={entities} />

          {/* Jejak sosmed (data nyata) */}
          <SocialSection osint={osint} />

          {/* CTA */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
            className="col-span-4">
            <Link href="/"><Button fullWidth>Verifikasi lowongan lain</Button></Link>
          </motion.div>
        </div>
      )}
    </div>
  );
}

/* ─── Map section (data nyata) ─────────────────────────────────────────── */
function MapSection({ osint, entities }: { osint: VerifyResponse["osint"]; entities: VerifyResponse["entities"] }) {
  const rawAddrs = (osint?.address_validations as Record<string,unknown>[]) || [];
  const validAddrs = rawAddrs.filter((a) => a.found || a.address_found);
  const entityAddrs = (entities?.addresses as string[]) || [];
  const hasAddrs = validAddrs.length > 0 || entityAddrs.length > 0;
  if (!hasAddrs) return null;

  const primaryAddr = validAddrs[0] || {};
  const details = (primaryAddr.address_details as Record<string, unknown>) || {};
  const bizDetails = (primaryAddr.business_details as Record<string, unknown>) || {};
  const lat = primaryAddr.lat ?? details.lat;
  const lon = primaryAddr.lon ?? details.lon;
  const addressInput = String(primaryAddr.address_input ?? entityAddrs[0] ?? "");
  const geocodedDisplay = String(details.display_name ?? primaryAddr.display_name ?? "");
  const display = addressInput || geocodedDisplay || "Alamat dari lowongan tidak tersedia";
  const matchedBizName = (bizDetails.matched_name as string | undefined) || String(entities?.companies?.[0] || "");
  const placeTitle = matchedBizName || display.split(",")[0] || "Lokasi Usaha";
  const matchLevel = String(details.match_level ?? primaryAddr.match_level ?? "area");
  const hasExactCoordinates = matchLevel === "exact" && lat != null && lon != null;

  const mapSearchQuery = matchedBizName
    ? `${matchedBizName}, ${addressInput || geocodedDisplay}`
    : addressInput || geocodedDisplay;

  const gmapsUrl = String(
    details.google_maps_url ?? primaryAddr.google_maps_url ??
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapSearchQuery)}`,
  );

  const osmUrl = (primaryAddr.osm_url ?? details.osm_url) as string | undefined;

  const confidence = (details.confidence_score as number | undefined) ?? 0.8;
  const accuracyLabel = matchLevel === "exact"
    ? "Jalan & nomor cocok dengan hasil peta"
    : matchLevel === "street"
    ? "Jalan cocok; nomor belum terkonfirmasi"
    : "Maps exact search; OSM baru menemukan area";

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.26 }}
      className="col-span-4 sm:col-span-2">
      <BentoCard title="Profil Lokasi & Peta" icon={MapPin}>
        <p className="mb-3 text-[13px] text-text-muted">
          Lokasi fisik di OpenStreetMap / Google Maps ({validAddrs.length || entityAddrs.length} lokasi)
        </p>
        <div className="overflow-hidden rounded-2xl border border-border bg-bg-elevated p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={cn(
              "inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold",
              matchLevel === "exact" ? "bg-aman-bg text-aman-fg" : "bg-bg-subtle text-text-secondary",
            )}>
              {matchLevel === "exact" ? <CheckCircle size={11} weight="fill" /> : <MapPin size={11} weight="fill" />}
              {matchLevel === "exact" ? "OSM Exact Match" : "Alamat Lowongan"}
            </span>
            <span className="rounded-md bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-500">
              {accuracyLabel}
            </span>
          </div>
          <h4 className="mt-2.5 text-[17px] font-extrabold tracking-tight text-text-primary">{placeTitle}</h4>
          <p className="mt-1 text-[12px] leading-relaxed text-text-secondary">{display}</p>
          {geocodedDisplay && geocodedDisplay !== display && (
            <p className="mt-1 text-[11px] leading-relaxed text-text-muted">
              Hasil geocode: {geocodedDisplay}
            </p>
          )}
          {hasExactCoordinates && (
            <p className="mt-2 font-mono text-[11px] text-text-muted">
              Koordinat GPS: {Number(lat).toFixed(6)}, {Number(lon).toFixed(6)}
            </p>
          )}

          {(validAddrs.length > 1 || entityAddrs.length > 1) && (
            <div className="mt-3.5 rounded-xl border border-border bg-bg-subtle p-2.5">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                {validAddrs.length || entityAddrs.length} lokasi terdeteksi:
              </p>
              <div className="space-y-1.5">
                {(validAddrs.length > 0 ? validAddrs : entityAddrs.map(a => ({ address_input: a }))).map((aItem: Record<string,unknown>, aIdx: number) => {
                  const aDisp = String(aItem.display_name ?? aItem.address_input ?? `Lokasi ${aIdx + 1}`);
                  return (
                    <div key={aIdx} className="flex items-center justify-between gap-2 rounded-lg bg-bg-elevated px-2.5 py-1.5 text-[11px]">
                      <span className="flex items-center gap-1.5 font-semibold text-text-primary truncate">
                        <Buildings size={11} /> {aDisp.split(",")[0]}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-text-muted">
                        {aDisp.split(",").slice(1, 3).join(", ") || "Terverifikasi"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="relative mt-3.5 overflow-hidden rounded-xl border border-border">
            <iframe
              title={`Peta ${placeTitle}`}
              width="100%"
              height="230"
              src={`https://maps.google.com/maps?q=${encodeURIComponent(mapSearchQuery)}&z=16&output=embed`}
              style={{ border: 0 }}
              allowFullScreen
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>


          <div className="mt-3.5 flex flex-wrap gap-2">
            <a href={gmapsUrl} target="_blank" rel="noreferrer"
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-aman-border bg-aman-bg px-3 py-2 text-[12px] font-semibold text-aman-fg transition-all hover:bg-aman-bg/80">
              <MapPin size={14} weight="bold" /> Buka Google Maps <ArrowSquareOut size={12} />
            </a>
            {typeof osmUrl === "string" && matchLevel === "exact" && (
              <a href={osmUrl} target="_blank" rel="noreferrer"
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-border bg-bg-subtle px-3 py-2 text-[12px] font-medium text-text-secondary transition-colors hover:border-border-focus">
                <Globe size={13} weight="bold" /> OpenStreetMap <ArrowSquareOut size={11} />
              </a>
            )}
          </div>
        </div>
      </BentoCard>
    </motion.div>
  );
}

/* ─── Social section (data nyata) ──────────────────────────────────────── */
function SocialSection({ osint }: { osint: VerifyResponse["osint"] }) {
  const threadsData = (osint?.threads as Record<string, unknown> | undefined) || {};
  const webData = (osint?.web as Record<string, unknown> | undefined) || {};

  const posts = (threadsData.posts as Record<string, unknown>[]) || [];
  const profiles = (threadsData.profiles as Record<string, unknown>[]) || [];
  const platformHits = threadsData.platform_hits as Record<string, boolean> | undefined;

  if (posts.length === 0 && Array.isArray(webData.searches)) {
    for (const s of webData.searches as Record<string, unknown>[]) {
      for (const r of (s.results as Record<string, unknown>[]) || []) {
        posts.push({ platform: "web_evidence", title: r.title, snippet: r.snippet, url: r.url });
      }
    }
  }

  const items = posts.length > 0 ? posts : profiles;
  const showSection = items.length > 0 || Boolean(platformHits);
  if (!showSection) return null;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.28 }}
      className="col-span-4 sm:col-span-2">
      <BentoCard title="Jejak Media Sosial & Web Publik" icon={MagnifyingGlass}>
        <p className="mb-3 text-[13px] text-text-muted">
          Profil & bukti keaktifan yang ditemukan di ruang publik
        </p>
        {platformHits && (
          <div className="mb-3.5 flex flex-wrap gap-1.5">
            {Object.entries(platformHits).map(([platform, found]) => (
              <span key={platform} className={cn(
                "rounded-lg px-2.5 py-1 text-[11px] font-semibold capitalize",
                found ? "border border-aman-border bg-aman-bg text-aman-fg" : "bg-bg-subtle text-text-muted opacity-50 line-through"
              )}>
                {platform.replace("_", " ")}
              </span>
            ))}
          </div>
        )}
        <div className="space-y-3">
          {items.slice(0, 5).map((p: Record<string, unknown>, i: number) => {
            const platformStr = typeof p.platform === "string" ? p.platform : "web";
            const titleStr = typeof p.title === "string" ? p.title : "";
            const snippetStr = typeof p.snippet === "string" ? p.snippet : "";
            const urlStr = typeof p.url === "string" ? p.url : "";
            return (
              <div key={i} className="overflow-hidden rounded-2xl border border-border bg-bg-elevated p-4">
                <span className="inline-flex items-center rounded-md border border-border bg-bg-subtle px-2 py-0.5 font-mono text-[10px] font-bold capitalize text-text-secondary">
                  {platformStr.replace("_", " ")}
                </span>
                {titleStr && (
                  <h5 className="mt-2 line-clamp-2 text-[14px] font-bold leading-snug text-text-primary">{titleStr}</h5>
                )}
                {snippetStr && (
                  <p className="mt-1.5 line-clamp-3 text-[12px] leading-relaxed text-text-secondary">{snippetStr}</p>
                )}
                {urlStr && (
                  <a href={urlStr.startsWith("http") ? urlStr : `https://${urlStr}`} target="_blank" rel="noreferrer"
                    className="mt-3 inline-flex w-full items-center justify-between rounded-xl border border-border bg-bg-subtle px-3 py-2 text-[11px] font-medium text-text-primary transition-colors hover:border-border-focus">
                    <span className="truncate">{urlStr}</span>
                    <ArrowSquareOut size={12} className="ml-1 shrink-0 text-text-muted" />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </BentoCard>
    </motion.div>
  );
}
