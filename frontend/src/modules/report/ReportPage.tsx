"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
  ShieldCheck,
  ShieldWarning,
  ShieldSlash,
  ShareNetwork,
  ChatTeardropText,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  InstagramLogo,
  FacebookLogo,
  LinkedinLogo,
  TiktokLogo,
  TwitterLogo,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { ShapChart } from "@/modules/report/ShapChart";
import { EvidencePanel } from "@/components/report/EvidencePanel";
import { REPORT_STORAGE_KEY, cn, normalizeVerdict, verdictTone } from "@/lib/utils";
import { getCaseById } from "@/lib/api";
import type { VerifyResponse, ExtractedEntities } from "@/types/verify";

/* ─── helpers ──────────────────────────────────────────────────────────── */
function VerdictIcon({ verdict, size = 40 }: { verdict: string; size?: number }) {
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
function riskLevelLabel(verdict: string) {
  const n = normalizeVerdict(verdict);
  if (n === "AMAN")    return "Risiko rendah";
  if (n === "WASPADA") return "Risiko sedang";
  if (n === "BAHAYA")  return "Risiko tinggi";
  return "Tidak dapat dinilai";
}
function verdictStroke(verdict: string): string {
  const n = normalizeVerdict(verdict);
  if (n === "AMAN")    return "#2f5c34";
  if (n === "WASPADA") return "#7a5500";
  if (n === "BAHAYA")  return "#8f2f2d";
  return "#8a8279";
}
const ENTITY_FIELDS: { key: keyof ExtractedEntities; label: string; icon: React.ElementType }[] = [
  { key: "companies", label: "Perusahaan", icon: Buildings },
  { key: "contacts",  label: "Kontak/HP",  icon: Phone },
  { key: "emails",    label: "Email",       icon: EnvelopeSimple },
  { key: "urls",      label: "URL",         icon: LinkSimple },
  { key: "addresses", label: "Alamat",      icon: MapPin },
  { key: "salaries",  label: "Gaji",        icon: Money },
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
        <span className="mt-1 text-[9px] font-medium uppercase tracking-wide text-text-muted">
          / 100
        </span>
      </div>
    </div>
  );
}

/* ─── Social Platform Icon ─────────────────────────────────────────────────── */
function SocialPlatformIcon({ platform }: { platform: string }) {
  const p = platform.toLowerCase();
  if (p.includes("instagram")) return <InstagramLogo size={18} weight="fill" className="text-pink-500" />;
  if (p.includes("facebook")) return <FacebookLogo size={18} weight="fill" className="text-blue-600" />;
  if (p.includes("linkedin")) return <LinkedinLogo size={18} weight="fill" className="text-blue-700" />;
  if (p.includes("tiktok")) return <TiktokLogo size={18} weight="fill" className="text-black" />;
  if (p.includes("twitter") || p === "x" || p.includes("x.com")) return <TwitterLogo size={18} weight="fill" className="text-sky-500" />;
  return <ShareNetwork size={18} weight="bold" className="text-text-muted" />;
}

function detectPlatform(url: string): string {
  const u = url.toLowerCase();
  if (u.includes("instagram.com")) return "Instagram";
  if (u.includes("facebook.com")) return "Facebook";
  if (u.includes("linkedin.com")) return "LinkedIn";
  if (u.includes("tiktok.com")) return "TikTok";
  if (u.includes("threads.net") || u.includes("threads.com")) return "Threads";
  if (u.includes("twitter.com") || u.includes("x.com")) return "X";
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
      className="overflow-hidden rounded-3xl border border-border bg-bg-elevated"
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

/* ─── Page ──────────────────────────────────────────────────────────────── */
export default function ReportPage() {
  const params = useParams<{ caseId?: string }>();
  const caseId = typeof params?.caseId === "string" ? params.caseId : undefined;
  const [report, setReport] = useState<VerifyResponse | null>(null);
  const [ready, setReady] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [showEntities, setShowEntities] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void (async () => {
        try {
          if (caseId) {
            const persisted = await getCaseById(caseId);
            if (!cancelled) setReport(persisted);
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

  if (!ready) return (
    <div className="flex min-h-[50vh] items-center justify-center gap-2.5 text-text-muted">
      <CircleNotch size={16} className="animate-spin" />
      <span className="text-[14px]">Memuat laporan...</span>
    </div>
  );

  if (!report) return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center sm:px-6">
      <h1 className="text-2xl font-semibold text-text-primary">Belum ada laporan</h1>
      <p className="mt-2 text-[15px] text-text-secondary">Laporan tidak ditemukan atau sudah tidak tersedia.</p>
      <div className="mt-8"><Link href="/"><Button>Ke verifikasi</Button></Link></div>
    </div>
  );

  const tone    = verdictTone(report.verdict);
  const clamped = Math.max(0, Math.min(100, report.risk_score));
  const entities = report.entities;
  const osint   = report.osint;
  const shap    = report.shap_explanation;

  const addrs = (osint?.address_validations as Record<string, unknown>[] | undefined) || [];
  const phones = osint?.phones || [];
  const social = osint?.social;

  const primaryAddr = addrs[0] || {};
  const bizDetails = (primaryAddr.business_details as Record<string, unknown>) || {};
  const addrDetails = (primaryAddr.address_details as Record<string, unknown>) || {};
  const companyName = String(bizDetails.matched_name ?? entities?.companies?.[0] ?? "Perusahaan");
  const address = String(primaryAddr.address_input ?? entities?.addresses?.[0] ?? "");
  const hasBusinessPoint = bizDetails.source === "google_maps_serp" && bizDetails.lat != null;
  const hasCoords = typeof addrDetails.lat === "number" && typeof addrDetails.lon === "number";

  // Jejak digital: profil sosial + website resmi dari hasil pencarian web
  const socialProfiles = (social?.profiles ?? []).filter((p) => p.url);
  const webResults = (osint?.web?.searches ?? []).flatMap((s) => s.results ?? []);
  const socialWebResults = webResults
    .filter((r) => {
      const url = (r.url ?? "").toLowerCase();
      return ["instagram.com","facebook.com","linkedin.com","tiktok.com","threads.net","threads.com","twitter.com","x.com"].some((d) => url.includes(d));
    })
    .slice(0, 6);
  const officialWebsites = (osint?.web?.websites ?? []).filter((w) => w.ok && w.url);
  const hasDigitalFootprint = socialProfiles.length > 0 || socialWebResults.length > 0 || officialWebsites.length > 0;

  const riskFactors = report.risk_factors ?? [];
  const safeFactors = report.safe_factors ?? [];
  const recommendations = report.recommendations ?? [];

  const fadeUp = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-12">

      {/* ── Top bar ── */}
      <div className="mb-5 flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-1.5 text-[13px] font-medium text-text-muted transition-colors hover:text-text-primary">
          <ArrowLeft size={14} weight="bold" /> Verifikasi baru
        </Link>
        <span className="truncate font-mono text-[11px] text-text-muted sm:text-xs">
          {caseId ? `Kasus #${caseId.slice(0, 8)}` : "Laporan sementara"}
        </span>
      </div>

      {/* ── HERO: Verdict ── */}
      <motion.div
        {...fadeUp}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className={cn("mb-4 rounded-3xl border-2 p-5 sm:p-8 lg:mb-5 lg:p-10", tone.bg, tone.border)}
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
      </motion.div>

      {/* ── Faktor Penilaian (satu blok, dua kolom) ── */}
      {(safeFactors.length > 0 || riskFactors.length > 0) && (
        <Section icon={ShieldCheck} title="Faktor Penilaian" subtitle="Alasan utama di balik verdict ini" delay={0.08}>
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
            <ol className="grid gap-3 sm:grid-cols-2">
              {recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-3 rounded-2xl bg-bg-subtle px-4 py-3.5">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-text-primary text-[11px] font-bold text-bg-elevated">
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
        <Section icon={Buildings} title="Perusahaan & Lokasi" subtitle="Identitas dan titik geografis yang terverifikasi" delay={0.16}>
          <div className="grid gap-6 sm:gap-8 md:grid-cols-2">
            {/* Perusahaan */}
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Perusahaan</p>
              <p className="mt-2 text-xl font-bold text-text-primary">{companyName}</p>
              {address && <p className="mt-1 text-sm text-text-secondary">{address}</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                {hasBusinessPoint && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-aman-bg px-3 py-1 text-xs font-semibold text-aman-fg">
                    <MapPin size={12} weight="fill" /> Titik Maps ditemukan
                  </span>
                )}
                {phones.length > 0 && !phones.some((p) => p.reported_fraud) && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-aman-bg px-3 py-1 text-xs font-semibold text-aman-fg">
                    <Phone size={12} weight="fill" /> Nomor bersih
                  </span>
                )}
                {hasDigitalFootprint && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-aman-bg px-3 py-1 text-xs font-semibold text-aman-fg">
                    <ShareNetwork size={12} weight="fill" /> Jejak digital
                  </span>
                )}
              </div>
            </div>

            {/* Lokasi */}
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-text-muted">Lokasi</p>
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
                    href={`https://www.google.com/maps?q=${(addrDetails.lat as number).toFixed(6)},${(addrDetails.lon as number).toFixed(6)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl bg-text-primary px-4 py-2.5 text-sm font-semibold text-bg-elevated transition-all hover:opacity-90"
                  >
                    <MapPin size={15} weight="bold" /> Google Maps <ArrowSquareOut size={13} />
                  </a>
                  {typeof addrDetails.osm_url === "string" && addrDetails.osm_url && (
                    <a
                      href={addrDetails.osm_url as string}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-xl border border-border bg-bg-subtle px-4 py-2.5 text-sm font-semibold text-text-secondary transition-all hover:bg-bg-elevated"
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
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-text-primary px-4 py-2.5 text-sm font-semibold text-bg-elevated transition-all hover:opacity-90"
                >
                  <MapPin size={15} weight="bold" /> Buka di Google Maps <ArrowSquareOut size={13} />
                </a>
              )}
            </div>
          </div>

          {/* Telepon cross-check */}
          {phones.length > 0 && (
            <div className="mt-8 border-t border-border pt-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-text-muted">Kontak Terverifikasi</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {phones.map((p, i) => (
                  <div key={i} className="flex items-center justify-between rounded-2xl bg-bg-subtle px-4 py-3">
                    <span className="font-mono text-sm font-semibold text-text-primary">{p.phone ?? "-"}</span>
                    <span className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold",
                      p.reported_fraud ? "bg-bahaya-bg text-bahaya-fg" : "bg-aman-bg text-aman-fg"
                    )}>
                      {p.reported_fraud ? <Warning size={11} weight="fill" /> : <CheckCircle size={11} weight="fill" />}
                      {p.reported_fraud ? "Dilaporkan" : "Bersih"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>
      </div>

      {/* ── Jejak Digital ── */}
      {hasDigitalFootprint && (
        <div className="mt-6">
          <Section icon={ShareNetwork} title="Jejak Digital" subtitle="Profil media sosial dan situs resmi yang ditemukan publik" delay={0.2}>
            <div className="grid gap-3 sm:grid-cols-2">
              {/* Profil sosial terderivasi */}
              {socialProfiles.map((p, i) => (
                <a
                  key={`prof-${i}`}
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <SocialPlatformIcon platform={detectPlatform(p.url ?? "")} />
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
                  className="group flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <SocialPlatformIcon platform={detectPlatform(r.url ?? "")} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text-primary">{r.title}</p>
                    <p className="truncate text-xs text-text-muted">{detectPlatform(r.url ?? "")}</p>
                  </div>
                  <ArrowSquareOut size={15} className="shrink-0 text-text-muted transition-colors group-hover:text-text-primary" />
                </a>
              ))}
              {/* Website resmi */}
              {officialWebsites.map((w, i) => (
                <a
                  key={`site-${i}`}
                  href={w.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-center gap-3 rounded-2xl border border-border bg-bg-subtle/50 px-4 py-3.5 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <LinkSimple size={18} weight="bold" className="shrink-0 text-text-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-text-primary">{w.title ?? w.url}</p>
                    <p className="truncate text-xs text-text-muted">Situs resmi</p>
                  </div>
                  <ArrowSquareOut size={15} className="shrink-0 text-text-muted transition-colors group-hover:text-text-primary" />
                </a>
              ))}
            </div>
          </Section>
        </div>
      )}

      {/* ── Entitas lowongan (collapse) ── */}
      <motion.div {...fadeUp} transition={{ delay: 0.24 }} className="mt-6 overflow-hidden rounded-3xl border border-border bg-bg-elevated">
        <button onClick={() => setShowEntities(!showEntities)} className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left sm:px-8 sm:py-5">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-text-primary sm:text-lg">Data Lowongan yang Diekstrak</h2>
            <p className="mt-0.5 truncate text-[13px] text-text-muted sm:text-sm">{companyName}{address ? ` • ${address.split(",")[0]}` : ""}</p>
          </div>
          <span className="shrink-0 text-text-muted">{showEntities ? <CaretUp size={18} /> : <CaretDown size={18} />}</span>
        </button>
        {showEntities && (
          <div className="border-t border-border px-5 py-5 sm:px-8 sm:py-6">
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
                      {vals.map((val) => (
                        <p key={val} className="break-all rounded-xl bg-bg-subtle px-3 py-2 font-mono text-[13px] text-text-secondary">
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
      <motion.div {...fadeUp} transition={{ delay: 0.28 }} className="mt-6 overflow-hidden rounded-3xl border border-border bg-bg-elevated">
        <button onClick={() => setShowAudit((s) => !s)} className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left sm:px-8 sm:py-5">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-text-primary sm:text-lg">Detail Teknis & Atribusi Bukti</h2>
            <p className="mt-0.5 text-[13px] text-text-muted sm:text-sm">Kontribusi tiap sinyal terhadap skor akhir</p>
          </div>
          <span className="shrink-0 text-text-muted">{showAudit ? <CaretUp size={18} /> : <CaretDown size={18} />}</span>
        </button>
        {showAudit && (
          <div className="border-t border-border px-5 py-5 sm:px-8 sm:py-6">
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
      <motion.div {...fadeUp} transition={{ delay: 0.32 }} className="mt-8">
        <Link href="/"><Button fullWidth>Verifikasi lowongan lain</Button></Link>
      </motion.div>
    </div>
  );
}
