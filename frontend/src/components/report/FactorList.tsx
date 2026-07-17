import { Warning, CheckCircle, Lightbulb } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

type Kind = "risk" | "safe" | "reco";

interface FactorListProps {
  title: string;
  items: string[];
  kind: Kind;
}

const config: Record<
  Kind,
  { icon: typeof Warning; iconClass: string; empty: string }
> = {
  risk: {
    icon: Warning,
    iconClass: "text-bahaya-fg",
    empty: "Tidak ada faktor risiko yang terdeteksi.",
  },
  safe: {
    icon: CheckCircle,
    iconClass: "text-aman-fg",
    empty: "Tidak ada faktor aman yang tercatat.",
  },
  reco: {
    icon: Lightbulb,
    iconClass: "text-charcoal-soft",
    empty: "Tidak ada rekomendasi tambahan.",
  },
};

export function FactorList({ title, items, kind }: FactorListProps) {
  const { icon: Icon, iconClass, empty } = config[kind];

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h3 className="text-[15px] font-semibold text-charcoal">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-[14px] text-muted">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {items.map((item, i) => (
            <li key={`${kind}-${i}`} className="flex gap-2.5 text-[15px] leading-relaxed">
              <Icon
                size={18}
                weight="bold"
                className={cn("mt-0.5 shrink-0", iconClass)}
              />
              <span className="text-charcoal-soft">{item}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
