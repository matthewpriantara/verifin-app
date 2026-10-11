import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  className?: string;
  tone?: "neutral" | "aman" | "waspada" | "bahaya";
}

const tones = {
  neutral: "bg-bg-subtle text-text-secondary border border-border",
  aman: "bg-aman-bg text-aman-fg",
  waspada: "bg-waspada-bg text-waspada-fg",
  bahaya: "bg-bahaya-bg text-bahaya-fg",
};

export function Badge({ children, className, tone = "neutral" }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
