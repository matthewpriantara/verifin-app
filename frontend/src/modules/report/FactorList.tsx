"use client";

import { motion } from "motion/react";
import { Warning, CheckCircle, Lightbulb } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

type Kind = "risk" | "safe" | "reco";

interface FactorListProps {
  title: string;
  items: string[];
  kind: Kind;
}

const config: Record<Kind, {
  icon: typeof Warning;
  iconClass: string;
  emptyText: string;
  headerClass: string;
}> = {
  risk: {
    icon: Warning,
    iconClass: "text-bahaya-fg",
    emptyText: "Tidak ada faktor risiko terdeteksi.",
    headerClass: "text-bahaya-fg",
  },
  safe: {
    icon: CheckCircle,
    iconClass: "text-aman-fg",
    emptyText: "Tidak ada faktor aman tercatat.",
    headerClass: "text-aman-fg",
  },
  reco: {
    icon: Lightbulb,
    iconClass: "text-accent",
    emptyText: "Tidak ada rekomendasi tambahan.",
    headerClass: "text-text-primary",
  },
};

export function FactorList({ title, items, kind }: FactorListProps) {
  const { icon: Icon, iconClass, emptyText, headerClass } = config[kind];

  return (
    <section className="rounded-xl border border-border bg-bg-elevated p-5">
      <h3 className={cn("text-[13px] font-semibold uppercase tracking-wide", headerClass)}>
        {title}
      </h3>

      {items.length === 0 ? (
        <p className="mt-3 text-[13px] text-text-muted">{emptyText}</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {items.map((item, i) => (
            <motion.li
              key={`${kind}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05, ease: "easeOut" }}
              className="flex gap-2.5 text-[14px]"
            >
              <Icon
                size={15}
                weight="bold"
                className={cn("mt-0.5 shrink-0", iconClass)}
              />
              <span className="leading-relaxed text-text-secondary">{item}</span>
            </motion.li>
          ))}
        </ul>
      )}
    </section>
  );
}
