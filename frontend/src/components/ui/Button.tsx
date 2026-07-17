import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  fullWidth?: boolean;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-charcoal text-cream-soft hover:bg-charcoal-soft disabled:bg-charcoal/40",
  secondary:
    "bg-surface text-charcoal border border-border hover:bg-cream-deep disabled:opacity-50",
  ghost:
    "bg-transparent text-charcoal-soft hover:text-charcoal hover:bg-cream-deep/60 disabled:opacity-50",
};

export function Button({
  className,
  variant = "primary",
  fullWidth,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2.5 text-[15px] font-medium transition-colors duration-150 active:scale-[0.98] disabled:cursor-not-allowed",
        variants[variant],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
