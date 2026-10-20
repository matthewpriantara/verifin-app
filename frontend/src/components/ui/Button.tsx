import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "outline";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  fullWidth?: boolean;
  size?: "sm" | "md";
}

const variants: Record<Variant, string> = {
  primary:
    "bg-text-primary text-bg-elevated hover:bg-text-secondary disabled:opacity-40",
  secondary:
    "bg-bg-elevated text-text-primary border border-border-focus/80 hover:border-text-primary hover:bg-bg-subtle shadow-xs disabled:opacity-40",
  danger:
    "bg-bahaya-fg text-white hover:opacity-90 shadow-xs disabled:opacity-40",
  ghost:
    "bg-transparent text-text-secondary hover:text-text-primary hover:bg-bg-subtle disabled:opacity-40",
  outline:
    "border border-border text-text-secondary hover:border-border-focus hover:text-text-primary disabled:opacity-40",
};

const sizes = {
  md: "h-11 px-4 text-[14px]",
  sm: "h-8 px-3 text-[13px]",
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text-primary focus-visible:ring-offset-2 focus-visible:ring-offset-bg active:scale-[0.98] disabled:cursor-not-allowed disabled:pointer-events-none";

// Kelas yang sama untuk <Link>/<a> yang tampil sebagai tombol, supaya tidak menyalin kelas sendiri.
export function buttonClass({
  variant = "primary",
  size = "md",
  fullWidth,
  className,
}: { variant?: Variant; size?: "sm" | "md"; fullWidth?: boolean; className?: string } = {}) {
  return cn(base, variants[variant], sizes[size], fullWidth && "w-full", className);
}

export function Button({
  className,
  variant = "primary",
  fullWidth,
  size = "md",
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClass({ variant, size, fullWidth, className })}
      {...props}
    >
      {children}
    </button>
  );
}
