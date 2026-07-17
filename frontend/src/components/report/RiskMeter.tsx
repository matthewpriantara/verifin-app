import { cn, normalizeVerdict, verdictLabel, verdictTone } from "@/lib/utils";

interface RiskMeterProps {
  score: number;
  verdict: string;
}

export function RiskMeter({ score, verdict }: RiskMeterProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = verdictTone(verdict);
  const v = normalizeVerdict(verdict);

  return (
    <div className={cn("rounded-lg border p-6", tone.bg, tone.border)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[13px] font-medium uppercase tracking-wide text-charcoal-soft">
            Verdict
          </p>
          <p className={cn("mt-1 text-3xl font-semibold tracking-tight", tone.fg)}>
            {verdictLabel(v)}
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-[13px] font-medium uppercase tracking-wide text-charcoal-soft">
            Risk score
          </p>
          <p className={cn("mt-1 font-mono text-4xl font-semibold tabular-nums", tone.fg)}>
            {clamped}
            <span className="text-xl font-medium text-charcoal-soft">/100</span>
          </p>
        </div>
      </div>

      <div className="mt-6">
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface/80">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-500",
              v === "AMAN" && "bg-aman-fg",
              v === "WASPADA" && "bg-waspada-fg",
              v === "BAHAYA" && "bg-bahaya-fg",
              v === "ERROR" && "bg-charcoal-soft",
            )}
            style={{ width: `${clamped}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-[12px] text-charcoal-soft">
          <span>0 Aman</span>
          <span>50 Waspada</span>
          <span>100 Bahaya</span>
        </div>
      </div>
    </div>
  );
}
