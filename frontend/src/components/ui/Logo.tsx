"use client";

import { cn } from "@/lib/utils";
import { ShieldCheck } from "@phosphor-icons/react";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  inverted?: boolean;
  showText?: boolean;
  className?: string;
}

const sizeConfig = {
  sm: {
    container: "h-7 w-7 rounded-lg",
    icon: 15,
    text: "text-[15px] font-semibold tracking-tight text-text-primary",
  },
  md: {
    container: "h-8 w-8 rounded-lg",
    icon: 18,
    text: "text-lg font-bold tracking-tight text-text-primary",
  },
  lg: {
    container: "h-10 w-10 rounded-xl",
    icon: 22,
    text: "text-xl font-bold tracking-tight text-text-primary",
  },
};

export function Logo({
  size = "md",
  inverted = false,
  showText = true,
  className,
}: LogoProps) {
  const currentSize = sizeConfig[size];

  return (
    <div className={cn("inline-flex items-center gap-2.5 select-none", className)}>
      <div
        className={cn(
          "flex items-center justify-center transition-transform group-hover:scale-105",
          currentSize.container,
          inverted
            ? "bg-bg text-text-primary"
            : "bg-text-primary text-bg-elevated"
        )}
      >
        <ShieldCheck size={currentSize.icon} weight="bold" />
      </div>

      {showText && (
        <span
          className={cn(
            currentSize.text,
            inverted && "font-mono text-xl font-bold tracking-tight text-bg"
          )}
        >
          {inverted ? "VERIFIN" : "Verifin"}
        </span>
      )}
    </div>
  );
}
