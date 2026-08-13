"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import {
  Warning,
  CheckCircle,
  ClockCounterClockwise,
  Flag,
  ArrowClockwise,
  LockKey,
  SignOut,
  XCircle,
  Database,
  ImageSquare,
  Link as LinkIcon,
  FileText,
  ArrowUpRight,
  MagnifyingGlass,
  Funnel,
  ShieldCheck,
  WarningOctagon,
  CaretLeft,
  CaretRight,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { fetchCases, fetchAiStatus } from "@/lib/admin";
import type { AdminCase } from "@/lib/admin";
import ReportChart from "@/modules/admin/ReportChart";
import ModerationTable from "@/modules/admin/ModerationTable";

/* ─── User Input History (Database Logs) ─────────────────────────────────── */
export interface UserInputLog {
  id: string;
  case_id: string;
  source: "text" | "image" | "url";
  raw_input: string;
  company_name: string;
  verdict: "AMAN" | "WASPADA" | "BAHAYA";
  risk_score: number;
  extracted_entities: string[];
  created_at: string;
  ip_address: string;
}

/* ─── Login Gate ──────────────────────────────────────────────────────────── */
function LoginGate({ onAuth }: { onAuth: () => void }) {
  const [pw, setPw]             = useState("");
  const [error, setError]       = useState(false);
  const [shake, setShake]       = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      if (res.ok) {
        onAuth();
      } else {
        setError(true);
        setShake(true);
        setTimeout(() => setShake(false), 500);
      }
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-text-primary">
            <LockKey size={22} weight="bold" className="text-bg-elevated" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">
              Admin Panel
            </h1>
            <p className="mt-1 text-[13px] text-text-muted">
              Masukkan password untuk melanjutkan
            </p>
          </div>
        </div>

        <motion.form
          onSubmit={submit}
          animate={shake ? { x: [0, -8, 8, -6, 6, -3, 3, 0] } : {}}
          transition={{ duration: 0.45 }}
          className="flex flex-col gap-3"
        >
          <input
            type="password"
            value={pw}
            onChange={(e) => { setPw(e.target.value); setError(false); }}
            placeholder="Password admin"
            autoFocus
            className={cn(
              "w-full rounded-xl border bg-bg-elevated px-4 py-3 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors",
              error
                ? "border-bahaya-border focus:border-bahaya-border"
                : "border-border focus:border-border-focus",
            )}
          />
          {error && (
            <p className="text-[12px] text-bahaya-fg">Password salah. Coba lagi.</p>
          )}
          <button
            type="submit"
            disabled={!pw || submitting}
            className="w-full rounded-xl bg-text-primary px-4 py-3 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {submitting ? "Memeriksa..." : "Masuk"}
          </button>
        </motion.form>
      </motion.div>
    </div>
  );
}

/* ─── Verdict badge ───────────────────────────────────────────────────────── */
function VerdictBadge({ verdict }: { verdict: string }) {
  const v = verdict.toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        v === "AMAN"    && "bg-aman-bg text-aman-fg border border-aman-border",
        v === "WASPADA" && "bg-waspada-bg text-waspada-fg border border-waspada-border",
        v === "BAHAYA"  && "bg-bahaya-bg text-bahaya-fg border border-bahaya-border",
        !["AMAN", "WASPADA", "BAHAYA"].includes(v) && "bg-bg-subtle text-text-muted border border-border",
      )}
    >
      {verdict}
    </span>
  );
}

/* ─── Stat card ───────────────────────────────────────────────────────────── */
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg-elevated p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-text-muted">{label}</p>
      <p className={cn("mt-1.5 font-mono text-3xl font-semibold tabular-nums", color)}>{value}</p>
    </div>
  );
}

/* ─── Cases table ─────────────────────────────────────────────────────────── */
function CasesTable({
  cases,
  loading,
  onViewUserInputs,
}: {
  cases: AdminCase[];
  loading: boolean;
  onViewUserInputs: () => void;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-text-muted text-[13px]">
        <ArrowClockwise size={16} className="mr-2 animate-spin" />
        Memuat kasus...
      </div>
    );
  }
  if (cases.length === 0) {
    return (
      <div className="py-16 text-center text-[13px] text-text-muted">
        Belum ada kasus yang diverifikasi
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border bg-bg-subtle">
            <th className="px-4 py-3 text-left font-medium text-text-muted">Verdict</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Skor</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Perusahaan</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Preview</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Sumber</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Waktu</th>
            <th className="px-4 py-3 text-right font-medium text-text-muted">Aksi</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {cases.map((c, i) => (
            <motion.tr
              key={c.id}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.02, duration: 0.2 }}
              className="hover:bg-bg-subtle transition-colors"
            >
              <td className="px-4 py-3">
                <VerdictBadge verdict={c.verdict} />
              </td>
              <td className="px-4 py-3 font-mono font-semibold text-text-primary">
                {c.risk_score}
              </td>
              <td className="px-4 py-3 text-text-secondary max-w-[160px] truncate">
                {c.company_name || "—"}
              </td>
              <td className="px-4 py-3 text-text-muted max-w-[240px] truncate">
                {c.raw_text_preview || "—"}
              </td>
              <td className="px-4 py-3">
                <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-text-muted uppercase">
                  {c.source || "text"}
                </span>
              </td>
              <td className="px-4 py-3 text-text-muted whitespace-nowrap">
                {c.created_at
                  ? new Date(c.created_at).toLocaleString("id-ID", {
                      dateStyle: "short",
                      timeStyle: "short",
                    })
                  : "—"}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={onViewUserInputs}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-bg-subtle px-2.5 py-1 text-[11px] font-semibold text-text-primary transition-colors hover:border-border-focus hover:bg-bg-elevated active:scale-95"
                >
                  Lihat Detail
                  <ArrowUpRight size={11} weight="bold" />
                </button>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Main page ───────────────────────────────────────────────────────────── */
export default function AdminPage() {
  const router = useRouter();

  /* auth */
  const [authed, setAuthed]         = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    fetch("/api/admin/session")
      .then((r) => (r.ok ? r.json() : { authed: false }))
      .then((d) => setAuthed(Boolean(d?.authed)))
      .catch(() => setAuthed(false))
      .finally(() => setAuthChecked(true));
  }, []);

  /* data */
  const [cases, setCases]     = useState<AdminCase[]>([]);
  const [aiStatus, setAiStatus] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  
  // Total 3 Tabs: "cases" | "moderation" | "user_inputs"
  const [activeTab, setActiveTab] = useState<"cases" | "moderation" | "user_inputs">("cases");

  // State untuk Tab Riwayat Inputan User (Database)
  const [userInputs, setUserInputs] = useState<UserInputLog[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [verdictFilter, setVerdictFilter] = useState<"ALL" | "BAHAYA" | "WASPADA" | "AMAN">("ALL");
  const [sourceFilter, setSourceFilter] = useState<"ALL" | "text" | "image" | "url">("ALL");
  const [currentPage, setCurrentPage] = useState(1);

  // Reset ke halaman 1 saat filter atau keyword pencarian berubah
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, verdictFilter, sourceFilter]);

  async function load() {
    setLoading(true);
    setError(null);
    const [casesRes, statusRes] = await Promise.allSettled([
      fetchCases(100),
      fetchAiStatus(),
    ]);
    if (casesRes.status === "fulfilled") {
      setCases(casesRes.value);
      // Map cases ke format UserInputLog untuk tab "Riwayat Inputan User"
      setUserInputs(
        casesRes.value.map((c): UserInputLog => ({
          id: c.id,
          case_id: c.id.slice(0, 8),
          source: (c.source as UserInputLog["source"]) || "text",
          raw_input: c.raw_text_preview || "—",
          company_name: c.company_name || "Tidak diketahui",
          verdict: (c.verdict as UserInputLog["verdict"]) || "WASPADA",
          risk_score: c.risk_score,
          extracted_entities: [
            ...(c.phones || []),
            ...(c.emails || []),
            ...(c.company_name ? [c.company_name] : []),
          ],
          created_at: new Date(c.created_at).toLocaleString("id-ID", {
            dateStyle: "short",
            timeStyle: "short",
          }) + " WIB",
          ip_address: "—",
        })),
      );
    } else setError(casesRes.reason instanceof Error ? casesRes.reason.message : "Gagal memuat kasus");
    if (statusRes.status === "fulfilled") setAiStatus(statusRes.value);
    setLoading(false);
  }

  useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [authed]);

  async function logout() {
    try { await fetch("/api/admin/login", { method: "DELETE" }); } catch { /* abaikan */ }
    setAuthed(false);
    setCases([]);
    setAiStatus(null);
    setError(null);
    router.push("/");
  }

  // Filter User Input Logs (Insensitif Spasi, Tanda Baca, & Huruf Besar/Kecil)
  const normalizeSearchText = (text: string) => text.toLowerCase().replace(/[\s\-_.]/g, "");
  const normalizedQuery = normalizeSearchText(searchQuery);

  const filteredUserInputs = userInputs.filter((item) => {
    const matchesSearch =
      !normalizedQuery ||
      normalizeSearchText(item.company_name).includes(normalizedQuery) ||
      normalizeSearchText(item.raw_input).includes(normalizedQuery) ||
      normalizeSearchText(item.case_id).includes(normalizedQuery) ||
      item.extracted_entities.some((entity) =>
        normalizeSearchText(entity).includes(normalizedQuery)
      );

    const matchesVerdict = verdictFilter === "ALL" || item.verdict === verdictFilter;
    const matchesSource = sourceFilter === "ALL" || item.source === sourceFilter;

    return matchesSearch && matchesVerdict && matchesSource;
  });

  // Pagination Riwayat Inputan User (6 Konten per Halaman)
  const ITEMS_PER_PAGE = 6;
  const totalPages = Math.max(1, Math.ceil(filteredUserInputs.length / ITEMS_PER_PAGE));
  const paginatedUserInputs = filteredUserInputs.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const getSourceIcon = (source: UserInputLog["source"]) => {
    switch (source) {
      case "image":
        return <ImageSquare size={13} weight="bold" className="text-text-muted" />;
      case "url":
        return <LinkIcon size={13} weight="bold" className="text-text-muted" />;
      case "text":
        return <FileText size={13} weight="bold" className="text-text-muted" />;
    }
  };

  /* render guards */
  if (!authChecked) {
    return (
      <div className="flex min-h-[calc(100vh-56px)] items-center justify-center text-text-muted">
        <span className="text-[14px]">Memeriksa sesi...</span>
      </div>
    );
  }
  if (!authed) return <LoginGate onAuth={() => setAuthed(true)} />;

  const stats = {
    total:   cases.length,
    aman:    cases.filter((c) => c.verdict === "AMAN").length,
    waspada: cases.filter((c) => c.verdict === "WASPADA").length,
    bahaya:  cases.filter((c) => c.verdict === "BAHAYA").length,
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">

      {/* ── Header ── */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">
            Dashboard
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text-primary">
            Admin Panel
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {/* AI status */}
          {aiStatus && (
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium",
                aiStatus.reachable
                  ? "border-aman-border bg-aman-bg text-aman-fg"
                  : "border-bahaya-border bg-bahaya-bg text-bahaya-fg",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  aiStatus.reachable ? "bg-aman-fg animate-pulse" : "bg-bahaya-fg",
                )}
              />
              {aiStatus.reachable ? "AI Online" : "AI Offline"}
            </span>
          )}
          {/* error */}
          {error && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-waspada-border bg-waspada-bg px-3 py-1.5 text-[12px] font-medium text-waspada-fg">
              <Warning size={12} weight="bold" />
              {error}
            </span>
          )}
          {/* logout */}
          <button
            onClick={logout}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary"
          >
            <SignOut size={13} />
            Keluar
          </button>
          {/* refresh */}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-3 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-40"
          >
            <ArrowClockwise size={13} weight="bold" className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* ── Stat cards dengan Button Lihat Detail di Sebelah Kanan ── */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total Kasus"  value={stats.total}   color="text-text-primary" />
          <StatCard label="Aman"         value={stats.aman}    color="text-aman-fg" />
          <StatCard label="Waspada"      value={stats.waspada} color="text-waspada-fg" />
          <StatCard label="Bahaya"       value={stats.bahaya}  color="text-bahaya-fg" />
        </div>
      </div>

      {/* ── Total 3 Tabs ── */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row rounded-xl border border-border bg-bg-subtle p-1">
        {[
          { id: "cases", label: `Riwayat Kasus (${stats.total})`, icon: ClockCounterClockwise },
          { id: "moderation", label: "Moderasi Laporan", icon: Flag },
          { id: "user_inputs", label: `Riwayat Inputan User (${userInputs.length})`, icon: Database },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={cn(
                "flex-1 rounded-lg px-3.5 py-2 text-[13px] font-medium transition-all",
                isActive
                  ? "bg-bg-elevated text-text-primary shadow-sm font-semibold"
                  : "text-text-muted hover:text-text-secondary hover:bg-bg-elevated/40",
              )}
            >
              <span className="flex items-center justify-center gap-2">
                <Icon size={14} weight={isActive ? "bold" : "regular"} />
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Tab 1: Riwayat Kasus ── */}
      {activeTab === "cases" && (
        <div className="flex flex-col gap-4">
          {/* chart */}
          <ReportChart cases={cases} onViewUserInputs={() => setActiveTab("user_inputs")} />

          {/* table */}
          <div className="rounded-xl border border-border bg-bg-elevated overflow-hidden">
            <div className="border-b border-border bg-bg-subtle px-4 py-3 flex items-center justify-between">
              <p className="text-[12px] font-medium text-text-muted">
                Daftar Verifikasi Terbaru (Aktivitas Verifikasi)
              </p>
            </div>
            <CasesTable cases={cases} loading={loading} onViewUserInputs={() => setActiveTab("user_inputs")} />
          </div>
        </div>
      )}

      {/* ── Tab 2: Moderasi Laporan ── */}
      {activeTab === "moderation" && (
        <div className="flex flex-col gap-4">
          {/* info callout */}
          <div className="flex items-start gap-3 rounded-xl border border-border bg-bg-elevated px-4 py-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-waspada-bg">
              <Flag size={12} weight="bold" className="text-waspada-fg" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-text-primary">Moderasi Laporan Komunitas</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-text-muted">
                Setiap laporan dari pengguna diverifikasi oleh tim admin sebelum mempengaruhi skor risiko perusahaan.
                Setujui laporan yang terbukti valid, atau tolak laporan yang tidak cukup bukti.
              </p>
            </div>
          </div>

          <ModerationTable />
        </div>
      )}

      {/* ── Tab 3: Riwayat Inputan User (Database) ── */}
      {activeTab === "user_inputs" && (
        <div className="flex flex-col gap-4">
          {/* Header Callout Info */}
          <div className="flex items-start gap-3 rounded-xl border border-border bg-bg-elevated px-4 py-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-bg-subtle border border-border text-text-primary">
              <Database size={13} weight="bold" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-text-primary">Riwayat Inputan User dari Database PostgreSQL</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-text-muted">
                Menampilkan log seluruh inputan teks, poster gambar (OCR), dan link URL yang dikirim oleh publik ke sistem Verifin beserta entitas & bukti risiko yang diekstrak.
              </p>
            </div>
          </div>

          {/* Filter & Search Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 rounded-xl border border-border bg-bg-elevated p-3 shadow-sm">
            {/* Search Input */}
            <div className="relative flex-1">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Cari perusahaan, teks input, atau Case ID..."
                className="w-full rounded-lg border border-border bg-bg-subtle pl-9 pr-3 py-1.5 text-[12px] text-text-primary placeholder:text-text-muted outline-none focus:border-border-focus transition-colors"
              />
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
              {/* Verdict Filter */}
              <div className="flex items-center gap-1 border border-border bg-bg-subtle p-1 rounded-lg">
                {(["ALL", "BAHAYA", "WASPADA", "AMAN"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setVerdictFilter(v)}
                    className={cn(
                      "px-2 py-0.5 text-[10px] font-mono font-semibold rounded transition-colors uppercase",
                      verdictFilter === v
                        ? "bg-text-primary text-bg-elevated"
                        : "text-text-muted hover:text-text-primary"
                    )}
                  >
                    {v}
                  </button>
                ))}
              </div>

              {/* Source Filter */}
              <div className="flex items-center gap-1 border border-border bg-bg-subtle p-1 rounded-lg">
                {(["ALL", "text", "image", "url"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSourceFilter(s)}
                    className={cn(
                      "px-2 py-0.5 text-[10px] font-mono font-semibold rounded transition-colors uppercase",
                      sourceFilter === s
                        ? "bg-text-primary text-bg-elevated"
                        : "text-text-muted hover:text-text-primary"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Cards Aktivitas Verifikasi Inputan User */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {paginatedUserInputs.length > 0 ? (
              paginatedUserInputs.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="relative flex flex-col justify-between rounded-2xl border border-border bg-bg-elevated p-4 shadow-sm transition-all hover:border-border-focus"
                >
                  <div>
                    {/* Header Row: Source Icon, Case ID & Verdict */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-bg-subtle px-2 py-0.5 font-mono text-[10px] uppercase font-semibold text-text-muted">
                          {getSourceIcon(item.source)}
                          {item.source}
                        </span>
                        <span className="font-mono text-[11px] text-text-muted">
                          ID: #{item.case_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <VerdictBadge verdict={item.verdict} />
                        <span className="font-mono text-[11px] font-bold text-text-primary">
                          ({item.risk_score})
                        </span>
                      </div>
                    </div>

                    {/* Company Name */}
                    <h4 className="text-[14px] font-bold text-text-primary">
                      {item.company_name}
                    </h4>

                    {/* Raw Input Content Preview */}
                    <p className="mt-1.5 text-[12px] leading-relaxed text-text-secondary line-clamp-2 bg-bg-subtle/50 p-2.5 rounded-xl border border-border/40 font-mono">
                      {item.raw_input}
                    </p>

                    {/* Extracted Entities Badges */}
                    <div className="mt-3 flex flex-wrap gap-1">
                      {item.extracted_entities.map((entity, idx) => (
                        <span
                          key={idx}
                          className="rounded border border-border bg-bg-subtle px-1.5 py-0.5 font-mono text-[10px] text-text-muted"
                        >
                          {entity}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Footer Row: Timestamp, IP & Button "Lihat Detail" / "Lihat Selengkapnya" at bottom-right corner */}
                  <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between">
                    <div className="flex items-center gap-2 font-mono text-[10px] text-text-muted">
                      <span>{item.created_at}</span>
                      <span>•</span>
                      <span>{item.ip_address}</span>
                    </div>

                    {/* Button Lihat Detail / Lihat Selengkapnya (Pojok Kanan Bawah) */}
                    <button
                      onClick={() => router.push(`/report/${item.case_id}`)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-bg-subtle px-3 py-1.5 text-[12px] font-semibold text-text-primary transition-all hover:border-border-focus hover:bg-text-primary hover:text-bg-elevated active:scale-95 cursor-pointer"
                    >
                      Lihat Detail
                      <ArrowUpRight size={13} weight="bold" />
                    </button>
                  </div>
                </motion.div>
              ))
            ) : (
              <div className="col-span-full py-12 text-center rounded-2xl border border-border bg-bg-elevated p-6">
                <p className="text-[13px] font-medium text-text-muted">
                  Tidak ada data inputan user yang cocok dengan filter pencarian.
                </p>
              </div>
            )}
          </div>

          {/* Kontrol Pagination (6 Konten per Halaman) */}
          {filteredUserInputs.length > 0 && (
            <div className="mt-2 flex items-center justify-between rounded-xl border border-border bg-bg-elevated px-4 py-3 shadow-sm">
              <span className="font-mono text-[11px] text-text-muted">
                Menampilkan {Math.min((currentPage - 1) * ITEMS_PER_PAGE + 1, filteredUserInputs.length)}–
                {Math.min(currentPage * ITEMS_PER_PAGE, filteredUserInputs.length)} dari {filteredUserInputs.length} inputan
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                  title="Halaman sebelumnya"
                >
                  <CaretLeft size={14} weight="bold" />
                </button>

                <div className="flex items-center gap-1 px-2 font-mono text-[12px] font-semibold text-text-primary">
                  <span>{currentPage}</span>
                  <span className="text-text-muted">/</span>
                  <span className="text-text-muted">{totalPages}</span>
                </div>

                <button
                  type="button"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                  title="Halaman selanjutnya"
                >
                  <CaretRight size={14} weight="bold" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
