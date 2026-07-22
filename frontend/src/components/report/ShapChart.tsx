"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import type { ShapExplanation } from "@/types/verify";

interface ShapChartProps {
  shap: ShapExplanation;
}

export function ShapChart({ shap }: ShapChartProps) {
  const contributions = shap.feature_contributions.slice(0, 7);
  const maxAbs = Math.max(...contributions.map((c) => Math.abs(c.contribution)), 1);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-text-muted">
          Base nilai: <span className="font-mono text-text-secondary">{shap.base_value}</span>
        </p>
        <p className="text-[11px] text-text-muted">
          Skor akhir: <span className="font-mono font-semibold text-text-primary">{shap.final_risk_score}/100</span>
        </p>
      </div>

      {/* Bar chart */}
      <div className="space-y-2.5">
        {contributions.map((c, i) => {
          const isRisk = c.impact === "risk";
          const barWidth = (Math.abs(c.contribution) / maxAbs) * 100;
          return (
            <motion.div
              key={c.feature_key}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06, duration: 0.35 }}
              className="space-y-1"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-[12px] text-text-secondary truncate flex-1" title={c.feature}>
                  {c.feature}
                </p>
                <span className={cn(
                  "shrink-0 font-mono text-[11px] font-medium",
                  isRisk ? "text-bahaya-fg" : "text-aman-fg"
                )}>
                  {isRisk ? "+" : "-"}{Math.abs(c.contribution).toFixed(1)}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-muted">
                <motion.div
                  className={cn("h-full rounded-full", isRisk ? "bg-bahaya-fg" : "bg-aman-fg")}
                  initial={{ width: "0%" }}
                  animate={{ width: `${barWidth}%` }}
                  transition={{ delay: i * 0.06 + 0.1, duration: 0.5, ease: "easeOut" }}
                />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Formula */}
      <p className="border-t border-border pt-3 text-[11px] text-text-muted">
        Formulasi SHAP: f(x) = {shap.base_value} + &Sigma;(&phi;<sub>i</sub>) = {shap.final_risk_score}
      </p>
    </div>
  );
}
