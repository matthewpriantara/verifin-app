"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Shield,
  Warning,
  CheckCircle,
  ClockCounterClockwise,
  Buildings,
  ArrowClockwise,
  Eye,
  LockKey,
  SignOut,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { fetchCases, fetchWhitelist, fetchAiStatus } from "@/lib/admin";
import type { AdminCase, WhitelistEntry } from "@/lib/admin";

const ADMIN_SESSION_KEY = "verifin:admin-auth";
const ADMIN_PASSWORD =
  process.env.NEXT_PUBLIC_ADMIN_PASSWORD ?? "verifin123";

/* ─── Login Gate ──────────────────────────────────────────────────────────── */
function LoginGate({ onAuth }: { onAuth: () => void }) {
  const [pw, setPw] = useState("");
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pw === ADMIN_PASSWORD) {
      sessionStorage.setItem(ADMIN_SESSION_KEY, "1");
      onAuth();
    } else {
      setError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
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
            disabled={!pw}
            className="w-full rounded-xl bg-text-primary px-4 py-3 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            Masuk
          </button>
        </motion.form>
      </motion.div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const v = verdict.toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        v === "AMAN"    && "bg-aman-bg text-aman-fg",
        v === "WASPADA" && "bg-waspada-bg text-waspada-fg",
        v === "BAHAYA"  && "bg-bahaya-bg text-bahaya-fg",
        !["AMAN","WASPADA","BAHAYA"].includes(v) && "bg-bg-subtle text-text-muted",
      )}
    >
      {v === "AMAN" && <CheckCircle size={10} weight="bold" />}
      {v === "WASPADA" && <Warning size={10} weight="bold" />}
      {v === "BAHAYA" && <Warning size={10} weight="fill" />}
      {v}
    </span>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg-elevated p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-text-muted">
        {label}
      </p>
      <p className={cn("mt-1.5 font-mono text-3xl font-semibold tabular-nums", color)}>
        {value}
      </p>
    </div>
  );
}

export default function AdminPage() {
  // ── Auth gate ──────────────────────────────────────────────────────────────
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem(ADMIN_SESSION_KEY) === "1") setAuthed(true);
  }, []);

  // ── Data ───────────────────────────────────────────────────────────────────
  const [cases, setCases] = useState<AdminCase[]>([]);
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([]);
  const [aiStatus, setAiStatus] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"cases" | "whitelist">("cases");

  async function load() {
    setLoading(true);
    setError(null);
    // Fetch secara independen agar satu fail tidak block yang lain
    const [casesRes, whitelistRes, statusRes] = await Promise.allSettled([
      fetchCases(100),
      fetchWhitelist(200),
      fetchAiStatus(),
    ]);
    if (casesRes.status === "fulfilled") setCases(casesRes.value);
    else setError(casesRes.reason instanceof Error ? casesRes.reason.message : "Gagal memuat kasus");
    if (whitelistRes.status === "fulfilled") setWhitelist(whitelistRes.value);
    if (statusRes.status === "fulfilled") setAiStatus(statusRes.value);
    setLoading(false);
  }

  useEffect(() => { if (authed) load(); }, [authed]);

  function logout() {
    sessionStorage.removeItem(ADMIN_SESSION_KEY);
    setAuthed(false);
    setCases([]);
    setWhitelist([]);
    setAiStatus(null);
    setError(null);
  }

  // ── Login gate render ──────────────────────────────────────────────────────
  if (!authed) return <LoginGate onAuth={() => setAuthed(true)} />;

  const stats = {
    total:   cases.length,
    aman:    cases.filter((c) => c.verdict === "AMAN").length,
    waspada: cases.filter((c) => c.verdict === "WASPADA").length,
    bahaya:  cases.filter((c) => c.verdict === "BAHAYA").length,
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      {/* Header */}
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
          {/* AI Status */}
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
          {/* Error banner inline */}
          {error && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-waspada-border bg-waspada-bg px-3 py-1.5 text-[12px] font-medium text-waspada-fg">
              <Warning size={12} weight="bold" />
              {error}
            </span>
          )}
          {/* Logout */}
          <button
            onClick={logout}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary"
          >
            <SignOut size={13} />
            Keluar
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-3 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-40"
          >
            <ArrowClockwise
              size={13}
              weight="bold"
              className={loading ? "animate-spin" : ""}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Kasus" value={stats.total} color="text-text-primary" />
        <StatCard label="Aman" value={stats.aman} color="text-aman-fg" />
        <StatCard label="Waspada" value={stats.waspada} color="text-waspada-fg" />
        <StatCard label="Bahaya" value={stats.bahaya} color="text-bahaya-fg" />
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-xl border border-border bg-bg-subtle p-1">
        {(["cases", "whitelist"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "flex-1 rounded-lg px-4 py-2 text-[13px] font-medium transition-colors",
              activeTab === tab
                ? "bg-bg-elevated text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-secondary",
            )}
          >
            {tab === "cases" ? (
              <span className="flex items-center justify-center gap-1.5">
                <ClockCounterClockwise size={13} />
                Riwayat Kasus ({stats.total})
              </span>
            ) : (
              <span className="flex items-center justify-center gap-1.5">
                <Buildings size={13} />
                AHU Whitelist ({whitelist.length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Cases table */}
      {activeTab === "cases" && (
        <div className="rounded-xl border border-border bg-bg-elevated overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-text-muted text-[13px]">
              <ArrowClockwise size={16} className="mr-2 animate-spin" />
              Memuat kasus...
            </div>
          ) : cases.length === 0 ? (
            <div className="py-16 text-center text-[13px] text-text-muted">
              Belum ada kasus yang diverifikasi
            </div>
          ) : (
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
                        {c.company_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-text-muted max-w-[240px] truncate">
                        {c.raw_text_preview || "-"}
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
                          : "-"}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Whitelist table */}
      {activeTab === "whitelist" && (
        <div className="rounded-xl border border-border bg-bg-elevated overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-text-muted text-[13px]">
              <ArrowClockwise size={16} className="mr-2 animate-spin" />
              Memuat whitelist...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border bg-bg-subtle">
                    <th className="px-4 py-3 text-left font-medium text-text-muted">#</th>
                    <th className="px-4 py-3 text-left font-medium text-text-muted">Nama Perusahaan</th>
                    <th className="px-4 py-3 text-left font-medium text-text-muted">Tipe</th>
                    <th className="px-4 py-3 text-left font-medium text-text-muted">Terakhir Sync</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {whitelist.map((w, i) => (
                    <tr key={w.id} className="hover:bg-bg-subtle transition-colors">
                      <td className="px-4 py-3 font-mono text-text-muted">{i + 1}</td>
                      <td className="px-4 py-3 font-medium text-text-primary">{w.company_name}</td>
                      <td className="px-4 py-3">
                        <span className="rounded border border-border px-2 py-0.5 font-mono text-[11px] text-text-secondary">
                          {w.legal_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-text-muted">
                        {new Date(w.synced_at).toLocaleDateString("id-ID")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
