import type { OsintPayload } from "@/types/verify";

interface EvidencePanelProps {
  osint?: OsintPayload | null;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border py-3 first:border-t-0 first:pt-0">
      <p className="text-[12px] font-medium uppercase tracking-wide text-muted">
        {label}
      </p>
      <div className="mt-1.5 text-[14px] leading-relaxed text-charcoal-soft">
        {children}
      </div>
    </div>
  );
}

export function EvidencePanel({ osint }: EvidencePanelProps) {
  if (!osint) {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h3 className="text-[15px] font-semibold text-charcoal">
          Bukti OSINT
        </h3>
        <p className="mt-3 text-[14px] text-muted">
          Tidak ada payload OSINT pada respons ini.
        </p>
      </section>
    );
  }

  const domain = osint.domain || {};
  const emailSec = osint.email_security || {};
  const phones = osint.phones || [];
  const web = osint.web;
  const threads = osint.threads;
  const companies = osint.companies || [];
  const addresses = osint.address_validations || [];

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h3 className="text-[15px] font-semibold text-charcoal">Bukti OSINT</h3>
      <p className="mt-1 text-[13px] text-muted">
        Data mentah dari sumber nyata (bukan rekaan model).{" "}
        {osint.evidence_policy?.social
          ? `Medsos: ${osint.evidence_policy.social}.`
          : null}
      </p>

      <div className="mt-4">
        <Row label="Domain / email">
          <ul className="space-y-1 font-mono text-[13px]">
            <li>
              umur:{" "}
              {String(
                domain.age_years ?? domain.age_days ?? domain.created_at ?? "—",
              )}
              {domain.is_new != null
                ? ` · baru=${String(domain.is_new)}`
                : ""}
              {domain.created_at ? ` · dibuat ${String(domain.created_at)}` : ""}
            </li>
            <li>
              SPF={String(emailSec.spf_active ?? "—")} · DMARC=
              {String(emailSec.dmarc_active ?? "—")}
            </li>
            {domain.error ? (
              <li className="text-bahaya-fg">error: {String(domain.error)}</li>
            ) : null}
          </ul>
        </Row>

        <Row label="Alamat (OSM)">
          {addresses.length === 0 ? (
            <p className="text-muted">Tidak ada validasi alamat.</p>
          ) : (
            <ul className="space-y-2">
              {addresses.map((a, i) => (
                <li key={i} className="text-[13px]">
                  <span className="font-medium text-charcoal">
                    {String(a.address_input || a.address || "—")}
                  </span>
                  <span className="text-muted">
                    {" "}
                    · found=
                    {String(
                      a.address_found ?? a.found ?? a.geocoded ?? "—",
                    )}
                  </span>
                  {a.error ? (
                    <span className="block text-bahaya-fg">
                      {String(a.error)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Row>

        <Row label="Telepon (Kredibel)">
          {phones.length === 0 ? (
            <p className="text-muted">Tidak ada nomor yang dicek.</p>
          ) : (
            <ul className="space-y-2">
              {phones.map((p, i) => (
                <li key={i} className="text-[13px]">
                  <span className="font-mono text-charcoal">
                    {p.phone || "—"}
                  </span>
                  {p.rating != null ? ` · rating ${p.rating}` : ""}
                  {p.review_count != null ? ` · ${p.review_count} review` : ""}
                  {p.reported_fraud ? " · ⚠ dilaporkan penipuan" : ""}
                  {p.url ? (
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-0.5 block text-[12px] text-charcoal underline underline-offset-2"
                    >
                      {p.url}
                    </a>
                  ) : null}
                  {p.error ? (
                    <span className="block text-bahaya-fg">{p.error}</span>
                  ) : null}
                  {p.summary ? (
                    <span className="block text-muted">{p.summary}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Row>

        <Row label="Website / search (Scrapling)">
          {!web ? (
            <p className="text-muted">Tidak ada data web.</p>
          ) : (
            <div className="space-y-2 text-[13px]">
              {(web.websites || []).map((w, i) => (
                <div key={`w-${i}`}>
                  <span className="font-medium text-charcoal">
                    {w.ok ? "OK" : "GAGAL"} · {w.url}
                  </span>
                  {w.title ? (
                    <span className="block text-muted">{w.title}</span>
                  ) : null}
                  {(w.risk_flags || []).map((f) => (
                    <span key={f} className="block text-bahaya-fg">
                      {f}
                    </span>
                  ))}
                </div>
              ))}
              {(web.searches || []).map((s, i) => (
                <div key={`s-${i}`}>
                  <span className="text-charcoal">
                    Search: <span className="font-mono">{s.query}</span>
                  </span>
                  <ul className="mt-1 space-y-1">
                    {(s.results || []).slice(0, 3).map((r, j) => (
                      <li key={j}>
                        {r.url ? (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noreferrer"
                            className="underline underline-offset-2"
                          >
                            {(r.title || r.url).slice(0, 100)}
                          </a>
                        ) : (
                          (r.title || "—").slice(0, 100)
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {web.error ? (
                <p className="text-bahaya-fg">{web.error}</p>
              ) : null}
            </div>
          )}
        </Row>

        <Row label="Perusahaan (jejak publik)">
          {companies.length === 0 ? (
            <p className="text-muted">Tidak ada cek nama PT.</p>
          ) : (
            <ul className="space-y-2 text-[13px]">
              {companies.map((c, i) => {
                const reg = (c.registry || {}) as Record<string, unknown>;
                return (
                  <li key={i}>
                    <span className="font-medium text-charcoal">
                      {String(c.name || "—")}
                    </span>
                    <span className="block text-muted">
                      AHU/OSS per-entitas:{" "}
                      {reg.pt_registry_verified
                        ? "terverifikasi"
                        : "belum terverifikasi"}
                    </span>
                    {Array.isArray(c.risk_flags)
                      ? (c.risk_flags as string[]).map((f) => (
                          <span key={f} className="block text-bahaya-fg">
                            {f}
                          </span>
                        ))
                      : null}
                  </li>
                );
              })}
            </ul>
          )}
        </Row>

        <Row label="Threads">
          {!threads ? (
            <p className="text-muted">Tidak ada data Threads.</p>
          ) : (
            <div className="text-[13px]">
              <p>
                enabled={String(threads.enabled)} · found=
                {String(threads.found)}
              </p>
              {(threads.profiles || []).slice(0, 3).map((p) => (
                <a
                  key={p.url || p.username}
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block underline underline-offset-2"
                >
                  @{p.username} {p.title ? `— ${p.title}` : ""}
                </a>
              ))}
              {(threads.risk_flags || []).map((f) => (
                <span key={f} className="block text-bahaya-fg">
                  {f}
                </span>
              ))}
              {threads.error ? (
                <p className="text-bahaya-fg">{threads.error}</p>
              ) : null}
            </div>
          )}
        </Row>
      </div>
    </section>
  );
}
