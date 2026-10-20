"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowLeft,
  ChatTeardropText,
  Warning,
  CheckCircle,
  Lightbulb,
  Buildings,
  Phone,
  EnvelopeSimple,
  LinkSimple,
  MapPin,
  Money,
  ShieldCheck,
  ShieldWarning,
  ShieldSlash,
  ShareNetwork,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  Info,
} from "@phosphor-icons/react";
import { SocialPlatformIcon } from "@/components/report/SocialPlatformIcon";
import { buttonClass } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ShapChart } from "@/modules/report/ShapChart";
import { EvidencePanel } from "@/components/report/EvidencePanel";
import { REPORT_STORAGE_KEY, cn, normalizeVerdict, verdictTone } from "@/lib/utils";
import { getCaseById } from "@/lib/api";
import { getPhoneStatus } from "@/lib/phone-status";
import type { VerifyResponse, ExtractedEntities } from "@/types/verify";

/* ─── helpers ──────────────────────────────────────────────────────────── */
function VerdictIcon({ verdict, size = 40 }: { verdict: string; size?: number }) {
  const v = normalizeVerdict(verdict);
  if (v === "AMAN") return <ShieldCheck size={size} weight="fill" />;
  if (v === "WASPADA") return <ShieldWarning size={size} weight="fill" />;
  if (v === "BAHAYA") return <ShieldSlash size={size} weight="fill" />;
  return <Warning size={size} weight="fill" />;
}
function vLabel(v: string) {
  const n = normalizeVerdict(v);
  return n === "AMAN" ? "Aman" : n === "WASPADA" ? "Waspada" : n === "BAHAYA" ? "Bahaya" : "Error";
}
function riskLevelLabel(verdict: string) {
  const n = normalizeVerdict(verdict);
  if (n === "AMAN") return "Risiko rendah";
  if (n === "WASPADA") return "Risiko sedang";
  if (n === "BAHAYA") return "Risiko tinggi";
  return "Tidak dapat dinilai";
}
// Menjawab komentar juri: label AMAN bukan jaminan legalitas, dan verdict menilai lowongan, bukan perusahaan.
function verdictDisclaimer(verdict: string) {
  const n = normalizeVerdict(verdict);
  if (n === "AMAN")
    return "AMAN berarti tidak ditemukan tanda bahaya pada bukti publik saat ini, bukan jaminan legalitas perusahaan. Tetap jangan transfer uang atau mengirim dokumen pribadi sebelum bertemu pihak perusahaan lewat kanal resminya.";
  if (n === "WASPADA")
    return "Bukti yang ada belum cukup untuk memastikan. Cek ulang lewat situs atau akun resmi perusahaan sebelum melamar, dan jangan mengirim uang atau dokumen pribadi.";
  if (n === "BAHAYA")
    return "Penilaian ini untuk isi lowongan yang kamu periksa, bukan vonis terhadap perusahaan yang namanya dipakai. Penipu sering mencatut nama perusahaan asli.";
  return "Sistem tidak dapat menilai lowongan ini. Lakukan pengecekan mandiri sebelum melamar.";
}

function verdictStroke(verdict: string): string {
  const n = normalizeVerdict(verdict);
  if (n === "AMAN") return "#2f5c34";
  if (n === "WASPADA") return "#7a5500";
  if (n === "BAHAYA") return "#8f2f2d";
  return "#8a8279";
}
const ENTITY_FIELDS: { key: keyof ExtractedEntities; label: string; icon: React.ElementType }[] = [
  { key: "companies", label: "Perusahaan", icon: Buildings },
  { key: "contacts", label: "Kontak/HP", icon: Phone },
  { key: "emails", label: "Email", icon: EnvelopeSimple },
  { key: "urls", label: "URL", icon: LinkSimple },
  { key: "addresses", label: "Alamat", icon: MapPin },
  { key: "salaries", label: "Gaji", icon: Money },
];

/* ─── Animated Score Gauge ─────────────────────────────────────────────────── */
function AnimatedScoreGauge({
  score,
  verdict,
  tone,
}: {
  score: number;
  verdict: string;
  tone: { fg: string };
}) {
  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    let startTime: number | null = null;
    const duration = 1400;

    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplayScore(Math.round(easeProgress * score));

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    const handle = requestAnimationFrame(step);
    return () => cancelAnimationFrame(handle);
  }, [score]);

  return (
    <div
      className="relative h-20 w-20 shrink-0 sm:h-24 sm:w-24"
      role="img"
      aria-label={`Skor risiko ${score} dari 100`}
    >
      <svg viewBox="0 0 84 84" className="h-full w-full -rotate-90 transform-gpu">
        <circle
          cx="42"
          cy="42"
          r="34"
          fill="none"
          stroke="var(--bg-muted)"
          strokeWidth="7"
        />
        <motion.circle
          cx="42"
          cy="42"
          r="34"
          fill="none"
          stroke={verdictStroke(verdict)}
          strokeWidth="7"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray="100 100"
          initial={{ strokeDashoffset: 100 }}
          animate={{ strokeDashoffset: 100 - score }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className={cn("text-2xl font-bold leading-none tabular-nums sm:text-3xl", tone.fg)}
        >
          {displayScore}
        </motion.span>
        <span className="mt-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
          / 100
        </span>
      </div>
    </div>
  );
}

/* ─── Social Platform Icon ─────────────────────────────────────────────────── */

function detectPlatform(url: string): string {
  try {
    const host = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
    if (host === "instagram.com" || host.endsWith(".instagram.com")) return "Instagram";
    if (host === "facebook.com" || host === "fb.com" || host.endsWith(".facebook.com")) return "Facebook";
    if (host === "linkedin.com" || host.endsWith(".linkedin.com")) return "LinkedIn";
    if (host === "tiktok.com" || host.endsWith(".tiktok.com")) return "TikTok";
    if (host === "threads.net" || host === "threads.com") return "Threads";
    if (host === "twitter.com" || host === "x.com" || host.endsWith(".twitter.com") || host.endsWith(".x.com")) return "X";
  } catch {
    const u = url.toLowerCase();
    if (u.includes("instagram.com")) return "Instagram";
    if (u.includes("facebook.com")) return "Facebook";
    if (u.includes("linkedin.com")) return "LinkedIn";
    if (u.includes("tiktok.com")) return "TikTok";
    if (u.includes("threads.net") || u.includes("threads.com")) return "Threads";
    if (u.includes("twitter.com") || /(?:^|[\/\.])x\.com(?:\/|$)/.test(u)) return "X";
  }
  return "Web";
}

/* ─── Section wrapper — satu blok besar, info dibagi grid ─────────────────── */
function Section({
  icon: Icon,
  title,
  subtitle,
  children,
  delay = 0,
}: {
  icon: React.ElementType;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="overflow-hidden rounded-2xl border border-border bg-bg-elevated"
    >
      <header className="flex items-start gap-3 border-b border-border px-5 py-4 sm:px-8 sm:py-5">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-bg-subtle text-text-secondary">
          <Icon size={18} weight="bold" />
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-bold text-text-primary sm:text-lg">{title}</h2>
          {subtitle && <p className="mt-0.5 text-[13px] text-text-muted sm:text-sm">{subtitle}</p>}
        </div>
      </header>
      <div className="px-5 py-5 sm:px-8 sm:py-6">{children}</div>
    </motion.section>
  );
}

function ReportSkeleton() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-12 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-4 w-24" />
      </div>

      <div className="rounded-2xl border border-border bg-bg-elevated p-6 sm:p-8 lg:p-10">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <Skeleton className="h-16 w-16 rounded-2xl" />
            <div className="space-y-2">
              <Skeleton className="h-9 w-44" />
              <Skeleton className="h-4 w-28" />
            </div>
          </div>
          <div className="space-y-2 flex-1 lg:max-w-xl">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
          <Skeleton className="h-20 w-20 rounded-full shrink-0" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-border bg-bg-elevated p-6 space-y-3">
          <Skeleton className="h-5 w-44" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/4" />
        </div>
        <div className="rounded-2xl border border-border bg-bg-elevated p-6 space-y-3">
          <Skeleton className="h-5 w-44" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-bg-elevated p-6 space-y-4">
        <Skeleton className="h-6 w-56" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

/* ─── Page ──────────────────────────────────────────────────────────────── */
export default function ReportPage() {
  const params = useParams<{ caseId?: string }>();
  const caseId = typeof params?.caseId === "string" ? params.caseId : undefined;
  const [report, setReport] = useState<VerifyResponse | null>(null);
  const [ready, setReady] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [showEntities, setShowEntities] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void (async () => {
        try {
          if (caseId) {
            try {
              const persisted = await getCaseById(caseId);
              if (!cancelled) setReport(persisted);
            } catch (err) {
              // Server tidak terjangkau: pakai salinan hasil yang baru saja diterima, bila kasusnya sama.
              const raw = sessionStorage.getItem(REPORT_STORAGE_KEY);
              const local = raw ? (JSON.parse(raw) as VerifyResponse) : null;
              if (local && local.case_id === caseId) {
                if (!cancelled) setReport(local);
              } else {
                if (!cancelled) setLoadFailed(!(err instanceof Error && /tidak ditemukan|404/i.test(err.message)));
                throw err;
              }
            }
          } else {
            const raw = sessionStorage.getItem(REPORT_STORAGE_KEY);
            if (!cancelled) setReport(raw ? (JSON.parse(raw) as VerifyResponse) : null);
          }
        } catch {
          if (!cancelled) setReport(null);
        } finally {
          if (!cancelled) setReady(true);
        }
      })();
    });
    return () => { cancelled = true; };
  }, [caseId]);

  if (!ready) return <ReportSkeleton />;

  if (!report) return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center sm:px-6">
      <h1 className="text-2xl font-semibold text-text-primary">{loadFailed ? "Laporan belum bisa dimuat" : "Belum ada laporan"}</h1>
      <p className="mt-2 text-[15px] text-text-secondary">
        {loadFailed
          ? "Server verifikasi sedang tidak terjangkau. Coba muat ulang halaman ini sebentar lagi."
          : "Laporan tidak ditemukan atau sudah tidak tersedia."}
      </p>
      <div className="mt-8"><Link href="/" className={buttonClass()}>Ke verifikasi</Link></div>
    </div>
  );

  const tone = verdictTone(report.verdict);
  const clamped = Math.max(0, Math.min(100, report.risk_score));
  const entities = report.entities;
  const osint = report.osint;
  const shap = report.shap_explanation;

  const addrs = (osint?.address_validations as Record<string, unknown>[] | undefined) || [];
  const phones = osint?.phones || [];
  const social = osint?.social;

  const primaryAddr = addrs[0] || {};
  const bizDetails = (primaryAddr.business_details as Record<string, unknown>) || {};
  const addrDetails = (primaryAddr.address_details as Record<string, unknown>) || {};
  // Nama dari lowongan, bukan judul hasil Google Maps; nama tempat di peta ditampilkan terpisah.
  const companyName = entities?.companies?.[0] ?? "Nama perusahaan tidak disebut";
  const mapsPlaceName = typeof bizDetails.matched_name === "string" ? bizDetails.matched_name : null;
  const addressSource = primaryAddr.address_source as string | undefined;
  const addressFromPosting = !addressSource || addressSource === "posting_address" || addressSource === "posting_address_refined";
  const address = entities?.addresses?.[0] ?? "";
  const hasBusinessPoint = bizDetails.source === "google_maps_serp" && bizDetails.lat != null;
  const hasCoords = typeof addrDetails.lat === "number" && typeof addrDetails.lon === "number";

  // Jejak digital: profil sosial + website resmi dari hasil pencarian web
  const socialProfiles = (social?.profiles ?? []).filter((p) => p.url);
  const webResults = (osint?.web?.searches ?? []).flatMap((s) => s.results ?? []);
  const socialWebResults = webResults
    .filter((r) => {
      const url = (r.url ?? "").toLowerCase();
      return ["instagram.com", "facebook.com", "linkedin.com", "tiktok.com", "threads.net", "threads.com", "twitter.com", "x.com"].some((d) => url.includes(d));
    })
    .slice(0, 6);
  const officialWebsites = (osint?.web?.websites ?? []).filter((w) => w.website_status === "AVAILABLE" && w.url);
  const searches = osint?.web?.searches ?? [];
  const searchUnavailable = searches.length > 0 && searches.every((s) => s.status === "UNAVAILABLE");
  const nothingToSearch = searches.length === 0 && !entities?.companies?.length;
  const hasDigitalFootprint = socialProfiles.length > 0 || socialWebResults.length > 0 || officialWebsites.length > 0;

  const riskFactors = report.risk_factors ?? [];
  const safeFactors = report.safe_factors ?? [];
  const recommendations = report.recommendations ?? [];

  const fadeUp = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-12">

      {/* ── Top bar ── */}
      <div className="mb-6 flex items-center justify-between border-b border-border-focus/40 pb-4">
        <Link
          href="/"
          className={buttonClass()}
        >
          <ArrowLeft size={15} weight="bold" /> Cek lowongan lain
        </Link>
        <span className="inline-flex items-center rounded-lg border border-border-focus/60 bg-bg-subtle px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-text-primary">
          {caseId ? `Kasus #${caseId.slice(0, 8)}` : "Laporan Sementara"}
        </span>
      </div>

      {/* ── HERO: Verdict ── */}
      <motion.div
        {...fadeUp}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className={cn("mb-4 rounded-2xl border-2 p-5 sm:p-8 lg:mb-5 lg:p-10", tone.bg, tone.border)}
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:gap-10">
          {/* Icon + verdict */}
          <div className="flex items-center gap-4 lg:shrink-0">
            <div className={cn("shrink-0", tone.fg)}>
              <span className="hidden sm:block"><VerdictIcon verdict={report.verdict} size={56} /></span>
              <span className="block sm:hidden"><VerdictIcon verdict={report.verdict} size={44} /></span>
            </div>
            <div>
              <h1 className={cn("text-3xl font-bold tracking-tight sm:text-5xl", tone.fg)}>
                {vLabel(report.verdict)}
              </h1>
              <p className="mt-1 text-sm font-medium text-text-secondary">{riskLevelLabel(report.verdict)}</p>
            </div>
          </div>

          {/* Summary — fleksibel, mengisi ruang tengah */}
          {report.summary && (
            <p className="flex-1 text-[14px] leading-relaxed text-text-secondary sm:text-[15px] lg:px-2">
              {report.summary}
            </p>
          )}

          {/* Score gauge — ring memuat angka di tengah, satu unit ringkas */}
          <div className="flex items-center gap-4 border-t pt-5 lg:shrink-0 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8" style={{ borderColor: "var(--border)" }}>
            <AnimatedScoreGauge score={clamped} verdict={report.verdict} tone={tone} />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Skor risiko</p>
              <p className="mt-1 text-sm font-bold text-text-secondary">{clamped} dari 100</p>
            </div>
          </div>
        </div>
        <p className="mt-5 flex gap-2 border-t pt-4 text-[13px] leading-relaxed text-text-secondary" style={{ borderColor: "var(--border)" }}>
          <Info size={16} weight="bold" className="mt-0.5 shrink-0" aria-hidden />
          <span>{verdictDisclaimer(report.verdict)}</span>
        </p>
      </motion.div>

      {/* ── Faktor Penilaian (satu blok, dua kolom) ── */}
      {(safeFactors.length > 0 || riskFactors.length > 0) && (
        <Section icon={ShieldCheck} title="Faktor Penilaian" subtitle="Alasan utama di balik hasil ini" delay={0.08}>
          <div className="grid gap-6 sm:gap-8 md:grid-cols-2">
            <div>
              <p className="mb-3 flex items-center gap-2 text-sm font-bold text-aman-fg">
                <CheckCircle size={16} weight="fill" /> Mendukung keamanan
              </p>
              <ul className="space-y-2.5">
                {safeFactors.length > 0 ? safeFactors.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed text-text-secondary">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-aman-fg" />
                    {f}
                  </li>
                )) : <li className="text-sm text-text-muted">Tidak ada faktor pendukung.</li>}
              </ul>
            </div>
            <div>
              <p className="mb-3 flex items-center gap-2 text-sm font-bold text-bahaya-fg">
                <Warning size={16} weight="fill" /> Perlu diwaspadai
              </p>
              <ul className="space-y-2.5">
                {riskFactors.length > 0 ? riskFactors.map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed text-text-secondary">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-bahaya-fg" />
                    {f}
                  </li>
                )) : <li className="text-sm text-text-muted">Tidak ada faktor risiko terdeteksi.</li>}
              </ul>
            </div>
          </div>
        </Section>
      )}

      {/* ── Rekomendasi ── */}
      {recommendations.length > 0 && (
        <div className="mt-6">
          <Section icon={Lightbulb} title="Rekomendasi Sebelum Melamar" subtitle="Langkah aman yang disarankan" delay={0.12}>
            <ol className="grid list-none gap-3 sm:grid-cols-2">
              {recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-3 rounded-2xl bg-bg-subtle px-4 py-3.5">
                  <span aria-hidden className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-text-primary text-[11px] font-bold text-bg-elevated">
                    {i + 1}
                  </span>
                  <span className="text-sm leading-relaxed text-text-secondary">{r}</span>
                </li>
              ))}
            </ol>
          </Section>
        </div>
      )}

      {/* ── Perusahaan & Lokasi (satu blok, grid) ── */}
      <div className="mt-6">
        <Section icon={Buildings} title="Perusahaan & Lokasi" subtitle="Identitas dan titik lokasi dari sumber publik" delay={0.16}>
          <div className="grid gap-6 sm:gap-8 md:grid-cols-2">
            {/* Perusahaan */}
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Perusahaan</p>
              <p className="mt-2 text-xl font-bold text-text-primary">{companyName}</p>
              <p className="mt-1 text-sm text-text-secondary">{address || "Lowongan tidak mencantumkan alamat."}</p>
              {/* Temuan ini netral: penipu memakai nama, alamat, dan akun perusahaan asli. Warnanya tidak hijau. */}
              <div className="mt-4 flex flex-wrap gap-2">
                {hasBusinessPoint && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-bg-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                    <MapPin size={12} weight="fill" /> Ada di Google Maps
                  </span>
                )}
                {phones.length > 0 && phones.every((p) => getPhoneStatus(p).kind === "safe") && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-bg-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                    <Phone size={12} weight="fill" /> Nomor tanpa laporan
                  </span>
                )}
                {hasDigitalFootprint && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-bg-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                    <ShareNetwork size={12} weight="fill" /> Ada jejak publik
                  </span>
                )}
              </div>
            </div>

            {/* Lokasi */}
            <div>
              <div className="flex items-center gap-2">
                <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Lokasi</p>
                {addrDetails.match_level === "area" && (
                  <span className="rounded-md bg-waspada-bg px-2 py-0.5 text-[11px] font-semibold text-waspada-fg">
                    Hanya wilayah/kode pos
                  </span>
                )}
                {addrDetails.match_level === "business" && (
                  <span className="rounded-md bg-bg-subtle px-2 py-0.5 text-[11px] font-semibold text-text-secondary">
                    Tempat usaha di peta
                  </span>
                )}
                {addrDetails.match_level === "street" && (
                  <span className="rounded-md bg-bg-subtle px-2 py-0.5 text-[11px] font-semibold text-text-secondary">
                    Tingkat Jalan
                  </span>
                )}
                {addrDetails.match_level === "exact" && (
                  <span className="rounded-md bg-aman-bg px-2 py-0.5 text-[11px] font-semibold text-aman-fg">
                    Titik Presisi
                  </span>
                )}
              </div>
              {!addressFromPosting && addrs.length > 0 && (
                <p className="mt-2 rounded-lg bg-bg-subtle px-3 py-2 text-[13px] leading-relaxed text-text-secondary">
                  {addressSource === "web_search"
                    ? "Lowongan tidak mencantumkan alamat. Titik di bawah adalah alamat dari hasil pencarian web tentang nama perusahaan, bukan lokasi yang ditulis lowongan."
                    : "Lowongan hanya menyebut wilayah penempatan. Titik di bawah adalah hasil pencarian wilayah atau nama usaha di wilayah itu, bukan alamat kantor dari lowongan."}
                </p>
              )}
              {mapsPlaceName && addrDetails.match_level === "business" && (
                <p className="mt-2 text-[13px] text-text-muted">Tempat di peta: {mapsPlaceName}</p>
              )}
              {typeof addrDetails.display_name === "string" && addrDetails.display_name ? (
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{addrDetails.display_name}</p>
              ) : address ? (
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{address}</p>
              ) : (
                <p className="mt-2 text-sm text-text-muted">Alamat tidak tersedia.</p>
              )}
              {hasCoords && (
                <p className="mt-3 font-mono text-xs text-text-muted">
                  {(addrDetails.lat as number).toFixed(6)}, {(addrDetails.lon as number).toFixed(6)}
                </p>
              )}

              {/* Buka di Maps buttons */}
              {hasCoords && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={
                      addrDetails.match_level === "exact" || addrDetails.match_level === "business"
                        ? `https://www.google.com/maps?q=${(addrDetails.lat as number).toFixed(6)},${(addrDetails.lon as number).toFixed(6)}`
                        : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                            `${entities?.companies?.[0] ?? ""}, ${
                              (addrDetails.display_name as string) || address
                            }`.trim().replace(/^,\s*/, "")
                          )}`
                    }
                    target="_blank"
                    rel="noreferrer"
                    className={buttonClass()}
                  >
                    <MapPin size={15} weight="bold" /> Google Maps <ArrowSquareOut size={13} />
                  </a>
                  {typeof addrDetails.osm_url === "string" && addrDetails.osm_url && (
                    <a
                      href={addrDetails.osm_url as string}
                      target="_blank"
                      rel="noreferrer"
                      className={buttonClass({ variant: "secondary" })}
                    >
                      <MapPin size={15} weight="bold" /> OpenStreetMap <ArrowSquareOut size={13} />
                    </a>
                  )}
                </div>
              )}
              {!hasCoords && typeof bizDetails.maps_url === "string" && bizDetails.maps_url && (
                <a
                  href={bizDetails.maps_url}
                  target="_blank"
                  rel="noreferrer"
                  className={buttonClass({ className: "mt-4" })}
                >
                  <MapPin size={15} weight="bold" /> Buka di Google Maps <ArrowSquareOut size={13} />
                </a>
              )}
            </div>
          </div>

          {/* Telepon cross-check */}
          {phones.length > 0 && (
            <div className="mt-8 border-t border-border pt-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-text-muted">Reputasi Kontak</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {phones.map((p, i) => {
                  const status = getPhoneStatus(p);
                  return (
                    <div key={i} className="flex items-center justify-between rounded-2xl bg-bg-subtle px-4 py-3">
                      <span className="font-mono text-sm font-semibold text-text-primary">{p.phone ?? "-"}</span>
                      <span className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold",
                        status.kind === "risk"
                          ? "bg-bahaya-bg text-bahaya-fg"
                          : status.kind === "safe"
                            ? "bg-aman-bg text-aman-fg"
                            : "bg-bg-muted text-text-muted"
                      )}>
                        {status.kind === "risk" && <Warning size={11} weight="fill" />}
                        {status.kind === "safe" && <CheckCircle size={11} weight="fill" />}
                        {status.shortLabel}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Section>
      </div>

      {/* ── Jejak Digital ── */}
      <div className="mt-6">
        <Section icon={ShareNetwork} title="Jejak Digital" subtitle="Profil media sosial dan situs web dari pencarian publik" delay={0.2}>
          {hasDigitalFootprint && social?.found_by_name_only && (
            <p className="mb-3 text-[13px] leading-relaxed text-text-muted">
              Akun media sosial di bawah ditemukan lewat pencarian nama dan tidak ditautkan oleh lowongan. Akun itu milik
              pemilik nama, bukan bukti bahwa lowongan ini berasal darinya.
            </p>
          )}
          {hasDigitalFootprint ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* Profil sosial terderivasi */}
              {socialProfiles.map((p, i) => (
                <a
                  key={`prof-${i}`}
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <SocialPlatformIcon size={18} platform={detectPlatform(p.url ?? "")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text-primary">{p.username ?? p.title ?? p.url}</p>
                    <p className="truncate text-xs text-text-muted">{detectPlatform(p.url ?? "")}</p>
                  </div>
                  <ArrowSquareOut size={15} className="shrink-0 text-text-muted transition-colors group-hover:text-text-primary" />
                </a>
              ))}
              {/* Hasil web sosial (bila profil kosong) */}
              {socialProfiles.length === 0 && socialWebResults.map((r, i) => (
                <a
                  key={`web-${i}`}
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <SocialPlatformIcon size={18} platform={detectPlatform(r.url ?? "")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text-primary">{r.title}</p>
                    <p className="truncate text-xs text-text-muted">{detectPlatform(r.url ?? "")}</p>
                  </div>
                  <ArrowSquareOut size={15} className="shrink-0 text-text-muted transition-colors group-hover:text-text-primary" />
                </a>
              ))}
              {/* Website resmi & tautan publik */}
              {officialWebsites.map((w, i) => {
                const platform = detectPlatform(w.url ?? "");
                const isSocial = platform !== "Web";
                const isPost = /\/(p|post|reel|tv|status)\//i.test(w.url ?? "");
                const label = isSocial
                  ? isPost
                    ? `Postingan ${platform}`
                    : `Kanal ${platform}`
                  : "Situs web";

                return (
                  <a
                    key={`site-${i}`}
                    href={w.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                  >
                    {isSocial ? (
                      <SocialPlatformIcon size={18} platform={platform} />
                    ) : (
                      <LinkSimple size={18} weight="bold" className="shrink-0 text-text-muted" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-text-primary">{w.title ?? w.url}</p>
                      <p className="truncate text-xs text-text-muted">{label}</p>
                    </div>
                    <ArrowSquareOut size={15} className="shrink-0 text-text-muted transition-colors group-hover:text-text-primary" />
                  </a>
                );
              })}
            </div>
          ) : nothingToSearch ? (
            <p className="rounded-2xl border border-dashed border-border bg-bg-subtle/30 px-6 py-6 text-center text-[13px] text-text-muted">
              Lowongan tidak menyebut nama perusahaan, jadi tidak ada nama yang bisa dicari jejaknya.
            </p>
          ) : searchUnavailable ? (
            <p className="rounded-2xl border border-dashed border-border bg-bg-subtle/30 px-6 py-6 text-center text-[13px] text-text-muted">
              Mesin pencari tidak dapat dihubungi saat pemeriksaan, jadi jejak digital belum bisa dicek. Ini bukan berarti tidak ada jejak.
            </p>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-bg-subtle/30 px-6 py-8 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-bg-elevated text-text-muted shadow-2xs">
                <ShareNetwork size={20} weight="duotone" />
              </div>
              <p className="mt-3 text-[13px] font-semibold text-text-primary">
                Belum Ditemukan Jejak Digital Publik
              </p>
              <p className="mt-1 max-w-md text-[12px] leading-relaxed text-text-muted">
                Pencarian publik tidak menemukan profil media sosial atau situs web yang terhubung dengan nama, nomor, atau email di lowongan ini.
              </p>
            </div>
          )}
        </Section>
      </div>

      {/* ── Entitas lowongan (collapse) ── */}
      <motion.div {...fadeUp} transition={{ delay: 0.24 }} className="mt-6 overflow-hidden rounded-2xl border border-border bg-bg-elevated">
        <button type="button" aria-expanded={showEntities} aria-controls="report-entities" onClick={() => setShowEntities(!showEntities)} className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left sm:px-8 sm:py-5">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-text-primary sm:text-lg">Data Lowongan yang Diekstrak</h2>
            <p className="mt-0.5 truncate text-[13px] text-text-muted sm:text-sm">{companyName}{address ? ` • ${address.split(",")[0]}` : ""}</p>
          </div>
          <span className="shrink-0 text-text-muted">{showEntities ? <CaretUp size={18} /> : <CaretDown size={18} />}</span>
        </button>
        {showEntities && (
          <div id="report-entities" className="border-t border-border px-5 py-5 sm:px-8 sm:py-6">
            <div className="grid gap-5 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3">
              {ENTITY_FIELDS.map(({ key, label, icon: Icon }) => {
                const vals = entities?.[key] || [];
                if (vals.length === 0) return null;
                return (
                  <div key={key}>
                    <div className="mb-2 flex items-center gap-2">
                      <Icon size={14} weight="bold" className="text-text-muted" />
                      <p className="text-xs font-bold uppercase tracking-wider text-text-muted">{label}</p>
                    </div>
                    <div className="space-y-1.5">
                      {vals.map((val, vi) => (
                        <p key={`${val}-${vi}`} className="break-all rounded-xl bg-bg-subtle px-3 py-2 font-mono text-[13px] text-text-secondary">
                          {val}
                        </p>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </motion.div>

      {/* ── Detail teknis / SHAP (collapse) ── */}
      <motion.div {...fadeUp} transition={{ delay: 0.28 }} className="mt-6 overflow-hidden rounded-2xl border border-border bg-bg-elevated">
        <button type="button" aria-expanded={showAudit} aria-controls="report-audit" onClick={() => setShowAudit((s) => !s)} className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left sm:px-8 sm:py-5">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-text-primary sm:text-lg">Detail Teknis & Atribusi Bukti</h2>
            <p className="mt-0.5 text-[13px] text-text-muted sm:text-sm">Kontribusi tiap sinyal terhadap skor akhir</p>
          </div>
          <span className="shrink-0 text-text-muted">{showAudit ? <CaretUp size={18} /> : <CaretDown size={18} />}</span>
        </button>
        {showAudit && (
          <div id="report-audit" className="border-t border-border px-5 py-5 sm:px-8 sm:py-6">
            {shap && shap.feature_contributions.length > 0 && (
              <>
                <ShapChart shap={shap} />
                <div className="my-8 border-t border-border" />
              </>
            )}
            <EvidencePanel osint={osint} />
          </div>
        )}
      </motion.div>

      {/* ── CTA ── */}
      {/* ── CTA Actions ── */}
      <motion.div {...fadeUp} transition={{ delay: 0.32 }} className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Link href="/" className={buttonClass({ className: "flex-1" })}>
          Cek lowongan lain
        </Link>
        <Link
          href={caseId ? `/report-job?caseId=${encodeURIComponent(caseId)}` : "/report-job"}
          className={buttonClass({ variant: "danger", className: "flex-1 sm:max-w-xs" })}
        >
          <ChatTeardropText size={16} weight="bold" />
          Laporkan kasus ini
        </Link>
      </motion.div>
    </div>
  );
}
