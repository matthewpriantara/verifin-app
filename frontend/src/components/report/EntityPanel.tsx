import type { ExtractedEntities } from "@/types/verify";
import {
  Buildings,
  Phone,
  EnvelopeSimple,
  Link,
  MapPin,
  Money,
} from "@phosphor-icons/react/dist/ssr";

interface EntityPanelProps {
  entities?: ExtractedEntities | null;
}

const FIELDS: {
  key: keyof ExtractedEntities;
  label: string;
  icon: React.ElementType;
}[] = [
  { key: "companies", label: "Perusahaan",  icon: Buildings },
  { key: "contacts",  label: "Kontak/HP",   icon: Phone },
  { key: "emails",    label: "Email",        icon: EnvelopeSimple },
  { key: "urls",      label: "URL",          icon: Link },
  { key: "addresses", label: "Alamat",       icon: MapPin },
  { key: "salaries",  label: "Gaji",         icon: Money },
];

export function EntityPanel({ entities }: EntityPanelProps) {
  const hasAny = entities && FIELDS.some(({ key }) => (entities[key] || []).length > 0);

  return (
    <section className="rounded-xl border border-border bg-bg-elevated p-5">
      <h3 className="text-[13px] font-semibold uppercase tracking-wide text-text-primary">
        Entitas Terdeteksi
      </h3>
      <p className="mt-1 text-[12px] text-text-muted">
        Diekstrak via Regex NER struktural dari teks/OCR
      </p>

      {!hasAny ? (
        <p className="mt-4 text-[13px] text-text-muted">
          Tidak ada entitas yang diekstrak dari input.
        </p>
      ) : (
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {FIELDS.map(({ key, label, icon: Icon }) => {
            const values = entities?.[key] || [];
            if (values.length === 0) return null;
            return (
              <div key={key} className="space-y-1.5">
                <dt className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                  <Icon size={11} weight="bold" />
                  {label}
                </dt>
                <dd className="space-y-1">
                  {values.map((v) => (
                    <p
                      key={`${key}-${v}`}
                      className="break-all rounded-md bg-bg-subtle px-2.5 py-1.5 font-mono text-[12px] text-text-secondary"
                    >
                      {v}
                    </p>
                  ))}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}
