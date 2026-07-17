import type { ExtractedEntities } from "@/types/verify";

interface EntityPanelProps {
  entities?: ExtractedEntities | null;
}

const fields: { key: keyof ExtractedEntities; label: string }[] = [
  { key: "companies", label: "Perusahaan" },
  { key: "contacts", label: "Kontak" },
  { key: "emails", label: "Email" },
  { key: "urls", label: "URL" },
  { key: "addresses", label: "Alamat" },
  { key: "salaries", label: "Gaji" },
];

export function EntityPanel({ entities }: EntityPanelProps) {
  if (!entities) {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h3 className="text-[15px] font-semibold text-charcoal">
          Entitas terdeteksi
        </h3>
        <p className="mt-3 text-[14px] text-muted">
          Tidak ada entitas yang diekstrak dari input.
        </p>
      </section>
    );
  }

  const hasAny = fields.some(({ key }) => (entities[key] || []).length > 0);

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h3 className="text-[15px] font-semibold text-charcoal">
        Entitas terdeteksi
      </h3>
      {!hasAny ? (
        <p className="mt-3 text-[14px] text-muted">
          Tidak ada entitas yang diekstrak dari input.
        </p>
      ) : (
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {fields.map(({ key, label }) => {
            const values = entities[key] || [];
            if (values.length === 0) return null;
            return (
              <div key={key}>
                <dt className="text-[12px] font-medium uppercase tracking-wide text-muted">
                  {label}
                </dt>
                <dd className="mt-1.5 space-y-1">
                  {values.map((v) => (
                    <p
                      key={`${key}-${v}`}
                      className="break-all font-mono text-[13px] text-charcoal"
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
