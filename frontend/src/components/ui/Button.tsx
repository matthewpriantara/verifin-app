import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "outline";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  fullWidth?: boolean;
  size?: "sm" | "md";
}

const variants: Record<Variant, string> = {
  primary:
    "bg-text-primary text-bg-elevated hover:bg-text-secondary disabled:opacity-40",
  secondary:
    "bg-bg-subtle text-text-primary border border-border hover:border-border-focus disabled:opacity-40",
  ghost:
    "bg-transparent text-text-secondary hover:text-text-primary hover:bg-bg-subtle disabled:opacity-40",
  outline:
    "border border-border text-text-secondary hover:border-border-focus hover:text-text-primary disabled:opacity-40",
};

const sizes = {
  md: "h-10 px-4 text-[14px]",
  sm: "h-8 px-3 text-[13px]",
};

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
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text-primary focus-visible:ring-offset-2 focus-visible:ring-offset-bg active:scale-[0.98] disabled:cursor-not-allowed disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
