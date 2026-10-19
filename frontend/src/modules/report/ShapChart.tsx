"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import type { ShapExplanation } from "@/types/verify";

interface ShapChartProps {
  shap: ShapExplanation;
}

const CALIBRATION_KEY = "model_calibration";

function formatSigned(value: number) {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded >= 0 ? "+" : "−"}${Math.abs(rounded).toFixed(1)}`;
}

export function ShapChart({ shap }: ShapChartProps) {
  const contributions = shap.feature_contributions;
  const maxAbs = Math.max(...contributions.map((c) => Math.abs(c.contribution)), 1);
  const totalDelta = contributions.reduce((sum, c) => sum + c.delta, 0);
  const hasCalibration = contributions.some((c) => c.feature_key === CALIBRATION_KEY);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-text-muted">
          Nilai dasar: <span className="font-mono text-text-secondary">{shap.base_value}</span>
        </p>
        <p className="text-[12px] text-text-muted">
          Skor akhir: <span className="font-mono font-semibold text-text-primary">{shap.final_risk_score}/100</span>
        </p>
      </div>

      {/* Bar chart */}
      <div className="space-y-2.5">
        {contributions.map((c, i) => {
          const isRisk = c.impact === "risk";
          const isCalibration = c.feature_key === CALIBRATION_KEY;
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
                <p
                  className={cn("text-[12px] truncate flex-1", isCalibration ? "text-text-muted italic" : "text-text-secondary")}
                  title={c.description}
                >
                  {c.feature}
                </p>
                <span className={cn(
                  "shrink-0 font-mono text-[12px] font-medium",
                  isCalibration ? "text-text-muted" : isRisk ? "text-bahaya-fg" : "text-aman-fg"
                )}>
                  {formatSigned(c.delta)}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-muted">
                <motion.div
                  className={cn(
                    "h-full rounded-full",
                    isCalibration ? "bg-text-muted/60" : isRisk ? "bg-bahaya-fg" : "bg-aman-fg"
                  )}
                  initial={{ width: "0%" }}
                  animate={{ width: `${barWidth}%` }}
                  transition={{ delay: i * 0.06 + 0.1, duration: 0.5, ease: "easeOut" }}
                />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Rekonsiliasi: skor akhir = base + Σ kontribusi */}
      <div className="border-t border-border pt-3">
        <p className="font-mono text-[12px] text-text-muted">
          {shap.base_value} {formatSigned(totalDelta)} ={" "}
          <span className="font-semibold text-text-primary">
            {Math.round(shap.base_value + totalDelta)}
          </span>
          <span className="font-sans"> (nilai dasar + Σ kontribusi)</span>
        </p>
        {hasCalibration && (
          <p className="mt-1 text-[12px] leading-relaxed text-text-muted">
            &ldquo;Penyesuaian Penalaran AI&rdquo; adalah selisih antara skor dari AI dan jumlah bobot bukti terukur.
          </p>
        )}
      </div>
    </div>
  );
}
