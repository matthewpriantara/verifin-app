"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { cn, normalizeVerdict, verdictLabel, verdictTone } from "@/lib/utils";
import { ShieldCheck, Warning, Question } from "@phosphor-icons/react";

interface RiskMeterProps {
  score: number;
  verdict: string;
}

export function RiskMeter({ score, verdict }: RiskMeterProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = verdictTone(verdict);
  const v = normalizeVerdict(verdict);

  /* Count-up animation */
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    let frame: number;
    const duration = 900;
    const start = performance.now();
    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayed(Math.round(eased * clamped));
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [clamped]);

  const VerdictIcon =
    v === "AMAN" ? ShieldCheck : v === "BAHAYA" ? Warning : Question;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={cn("rounded-xl border p-6", tone.bg, tone.border)}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        {/* Verdict */}
        <div className="flex items-center gap-3">
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl border", tone.border, tone.bg)}>
            <VerdictIcon size={20} weight="bold" className={tone.fg} />
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-text-muted">Verdict</p>
            <p className={cn("text-2xl font-semibold tracking-tight", tone.fg)}>
              {verdictLabel(v)}
            </p>
          </div>
        </div>

        {/* Score */}
        <div className="text-left sm:text-right">
          <p className="text-[11px] font-medium uppercase tracking-widest text-text-muted">Skor Risiko</p>
          <p className={cn("font-mono text-5xl font-semibold tabular-nums", tone.fg)}>
            {displayed}
            <span className="text-xl font-normal text-text-muted">/100</span>
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-5">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-muted">
          <motion.div
            className={cn(
              "h-full rounded-full",
              v === "AMAN"    && "bg-aman-fg",
              v === "WASPADA" && "bg-waspada-fg",
              v === "BAHAYA"  && "bg-bahaya-fg",
              v === "ERROR"   && "bg-text-muted",
            )}
            initial={{ width: "0%" }}
            animate={{ width: `${clamped}%` }}
            transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
          />
        </div>
        <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-wide text-text-muted">
          <span>0 · Aman</span>
          <span>45 · Waspada</span>
          <span>80+ · Bahaya</span>
        </div>
      </div>
    </motion.div>
  );
}
