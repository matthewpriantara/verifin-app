"use client";

import { ArrowUpRight } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { AdminCase } from "@/types/admin";

/* ── helpers ──────────────────────────────────────────────────────────────── */
function groupByDate(cases: AdminCase[]): { label: string; total: number; aman: number; waspada: number; bahaya: number }[] {
  const map = new Map<string, { total: number; aman: number; waspada: number; bahaya: number }>();

  cases.forEach((c) => {
    const d = new Date(c.created_at);
    const label = d.toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
    const prev = map.get(label) ?? { total: 0, aman: 0, waspada: 0, bahaya: 0 };
    const v = c.verdict.toUpperCase();
    map.set(label, {
      total: prev.total + 1,
      aman: prev.aman + (v === "AMAN" ? 1 : 0),
      waspada: prev.waspada + (v === "WASPADA" ? 1 : 0),
      bahaya: prev.bahaya + (v === "BAHAYA" ? 1 : 0),
    });
  });

  return Array.from(map.entries()).map(([label, val]) => ({ label, ...val }));
}

/* ── Bar ──────────────────────────────────────────────────────────────────── */
function Bar({
  aman, waspada, bahaya, total, max, label, index,
}: {
  aman: number; waspada: number; bahaya: number;
  total: number; max: number; label: string; index: number;
}) {
  const pct = (n: number) => max > 0 ? (n / max) * 100 : 0;

  return (
    <div className="flex flex-1 flex-col items-center gap-1.5">
      {/* bar container */}
      <div className="relative flex h-28 w-full max-w-[40px] flex-col-reverse overflow-hidden rounded-md bg-bg-subtle">
        {/* bahaya */}
        <motion.div
          initial={{ scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.5, delay: index * 0.06 + 0.3, ease: [0.16, 1, 0.3, 1] }}
          style={{ height: `${pct(bahaya)}%`, transformOrigin: "bottom" }}
          className="w-full bg-bahaya-fg/80"
        />
        {/* waspada */}
        <motion.div
          initial={{ scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.5, delay: index * 0.06 + 0.2, ease: [0.16, 1, 0.3, 1] }}
          style={{ height: `${pct(waspada)}%`, transformOrigin: "bottom" }}
          className="w-full bg-waspada-fg/70"
        />
        {/* aman */}
        <motion.div
          initial={{ scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.5, delay: index * 0.06 + 0.1, ease: [0.16, 1, 0.3, 1] }}
          style={{ height: `${pct(aman)}%`, transformOrigin: "bottom" }}
          className="w-full bg-aman-fg/70"
        />
      </div>
      {/* total count */}
      <span className="font-mono text-[11px] font-semibold text-text-secondary">{total}</span>
      {/* date label */}
      <span className="text-center font-mono text-[9px] leading-tight text-text-muted">{label}</span>
    </div>
  );
}

/* ── Legend pill ──────────────────────────────────────────────────────────── */
function LegendPill({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-text-muted">
      <span className={`h-2 w-2 rounded-sm ${color}`} />
      {label}
    </span>
  );
}

/* ── Main component ───────────────────────────────────────────────────────── */
export default function ReportChart({
  cases,
  onViewUserInputs,
}: {
  cases: AdminCase[];
  onViewUserInputs?: () => void;
}) {
  const raw = cases.length > 0 ? groupByDate(cases) : [];
  // show last 14 data points max
  const data = raw.slice(-14);
  const max = Math.max(...data.map((d) => d.total), 1);

  const totalAll = data.reduce((s, d) => s + d.total, 0);
  const totalAman = data.reduce((s, d) => s + d.aman, 0);
  const totalWaspada = data.reduce((s, d) => s + d.waspada, 0);
  const totalBahaya = data.reduce((s, d) => s + d.bahaya, 0);

  return (
    <div className="rounded-xl border border-border bg-bg-elevated p-5">
      {/* header */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-text-muted">
            Aktivitas Verifikasi
          </p>
          <p className="mt-0.5 text-[22px] font-semibold tabular-nums text-text-primary">
            {totalAll}
            <span className="ml-1.5 text-[13px] font-normal text-text-muted">total input</span>
          </p>
        </div>

        {/* summary pills */}
        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col items-end">
            <span className="font-mono text-[18px] font-semibold text-aman-fg">{totalAman}</span>
            <span className="text-[10px] text-text-muted">Aman</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="font-mono text-[18px] font-semibold text-waspada-fg">{totalWaspada}</span>
            <span className="text-[10px] text-text-muted">Waspada</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="font-mono text-[18px] font-semibold text-bahaya-fg">{totalBahaya}</span>
            <span className="text-[10px] text-text-muted">Bahaya</span>
          </div>
        </div>
      </div>

      {/* chart */}
      {cases.length === 0 ? (
        <div className="flex h-28 items-center justify-center rounded-md bg-bg-subtle">
          <p className="text-[12px] text-text-muted">
            Belum ada aktivitas verifikasi
          </p>
        </div>
      ) : (
        <div className="flex items-end gap-1 overflow-x-auto pb-1">
          {data.map((d, i) => (
            <Bar key={d.label} {...d} max={max} index={i} />
          ))}
        </div>
      )}

      {/* legend & bottom-right button */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
        <div className="flex flex-wrap gap-3">
          <LegendPill color="bg-aman-fg/70" label="Aman" />
          <LegendPill color="bg-waspada-fg/70" label="Waspada" />
          <LegendPill color="bg-bahaya-fg/80" label="Bahaya" />
        </div>

        {onViewUserInputs && (
          <button
            onClick={onViewUserInputs}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-3 py-1 text-[11px] font-semibold text-text-primary transition-all hover:border-border-focus hover:bg-bg-subtle active:scale-95 cursor-pointer"
          >
            Lihat Detail Inputan User
            <ArrowUpRight size={12} weight="bold" />
          </button>
        )}
      </div>
    </div>
  );
}
