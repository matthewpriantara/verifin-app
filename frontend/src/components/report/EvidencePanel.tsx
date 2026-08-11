import type { OsintPayload } from "@/types/verify";
import { cn } from "@/lib/utils";
import {
  Globe,
  Phone,
  Buildings,
  ShareNetwork,
  Warning,
  CheckCircle,
} from "@phosphor-icons/react/dist/ssr";

interface EvidencePanelProps {
  osint?: OsintPayload | null;
}

function SectionRow({ label, icon: Icon, children }: {
  label: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-border py-4 first:border-t-0 first:pt-0">
      <div className="mb-2 flex items-center gap-1.5">
        <Icon size={12} weight="bold" className="text-accent" />
        <p className="text-[11px] font-semibold uppercase tracking-widest text-text-muted">
          {label}
        </p>
      </div>
      <div className="text-[13px] leading-relaxed text-text-secondary">
        {children}
      </div>
    </div>
  );
}

function Flag({ text, kind }: { text: string; kind: "risk" | "safe" }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium",
      kind === "risk"
        ? "bg-bahaya-bg text-bahaya-fg"
        : "bg-aman-bg text-aman-fg",
    )}>
      {kind === "risk"
        ? <Warning size={10} weight="bold" />
        : <CheckCircle size={10} weight="bold" />}
      {text}
    </span>
  );
}

export function EvidencePanel({ osint }: EvidencePanelProps) {
  if (!osint) {
    return (
      <section className="rounded-xl border border-border bg-bg-elevated p-5">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-text-primary">
          Bukti OSINT
        </h3>
        <p className="mt-3 text-[13px] text-text-muted">
          Tidak ada payload OSINT pada respons ini.
        </p>
      </section>
    );
  }

  const domain    = osint.domain ?? {};
  const emailSec  = osint.email_security ?? {};
  const phones    = osint.phones ?? [];
  const companies = osint.companies ?? [];
  const web       = osint.web;
  const social    = osint.social;

  return (
    <section className="rounded-xl border border-border bg-bg-elevated p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[13px] font-semibold uppercase tracking-wide text-text-primary">
            Bukti OSINT
          </h3>
          <p className="mt-0.5 text-[12px] text-text-muted">
            Data dari sumber nyata — bukan rekaan model AI
          </p>
        </div>
        {osint.evidence_policy?.mode && (
          <span className="shrink-0 rounded-full border border-border px-2.5 py-1 text-[10px] font-mono text-text-muted">
            {osint.evidence_policy.mode}
          </span>
        )}
      </div>

      <div className="mt-4">
        {/* Domain */}
        <SectionRow label="Domain & Email" icon={Globe}>
          <ul className="space-y-1 font-mono text-[12px]">
            <li>
              Umur domain:{" "}
              <span className="text-text-primary">
                {String(domain.age_years ?? domain.created_at ?? "tidak diketahui")}
                {domain.is_new ? " (baru, < 90 hari)" : ""}
              </span>
            </li>
            <li>
              SPF:{" "}
              <span className={emailSec.spf_active ? "text-aman-fg" : "text-text-muted"}>
                {emailSec.spf_active ? "aktif" : "tidak ada"}
              </span>
              {" · "}
              DMARC:{" "}
              <span className={emailSec.dmarc_active ? "text-aman-fg" : "text-text-muted"}>
                {emailSec.dmarc_active ? "aktif" : "tidak ada"}
              </span>
            </li>
          </ul>
        </SectionRow>

        {/* Phones */}
        {phones.length > 0 && (
          <SectionRow label="Reputasi Nomor HP/WA" icon={Phone}>
            <ul className="space-y-2">
              {phones.map((p, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-text-primary">{p.phone ?? "—"}</span>
                  {p.reported_fraud && <Flag text="Dilaporkan penipuan" kind="risk" />}
                  {p.found === false && <Flag text="Tidak ditemukan" kind="safe" />}
                  {p.summary && (
                    <span className="text-[12px] text-text-muted">{p.summary}</span>
                  )}
                </li>
              ))}
            </ul>
          </SectionRow>
        )}

         {/* Company public-web summary */}
         {companies.length > 0 && (
          <SectionRow label="Profil Perusahaan dari Web Publik" icon={Buildings}>
            <ul className="space-y-1">
              {companies.map((c, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-text-primary">
                    {String(c.name ?? c.company_name ?? "—")}
                  </span>
                  {typeof c.stats === "object" && c.stats !== null && (
                    <span className="text-[11px] text-text-muted">
                      {String((c.stats as Record<string, unknown>).public_mentions ?? 0)} jejak publik
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </SectionRow>
        )}

        {/* Web evidence */}
        {web?.websites && web.websites.length > 0 && (
          <SectionRow label="Website & Web Evidence" icon={Globe}>
            <ul className="space-y-2">
              {web.websites.map((w, i) => (
                <li key={i}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn(
                      "font-mono text-[12px]",
                      w.ok ? "text-text-primary" : "text-text-muted line-through",
                    )}>
                      {w.url}
                    </span>
                    {!w.ok && <Flag text="Tidak dapat diakses" kind="risk" />}
                  </div>
                  {w.snippet && (
                    <p className="mt-1 text-[12px] text-text-muted">{w.snippet}</p>
                  )}
                  {(w.risk_flags ?? []).map((f) => (
                    <Flag key={f} text={f} kind="risk" />
                  ))}
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(web.risk_flags ?? []).map((f) => <Flag key={f} text={f} kind="risk" />)}
              {(web.safe_flags ?? []).map((f) => <Flag key={f} text={f} kind="safe" />)}
            </div>
          </SectionRow>
        )}

        {/* Social media */}
         {social && (
          <SectionRow label="Social Media OSINT" icon={ShareNetwork}>
            <div className="space-y-2">
              {social.social_searches && social.social_searches.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[11px] text-text-muted">Status pencarian per platform</p>
                  {social.social_searches.map((search, i) => (
                    <div key={`${search.platform ?? "platform"}-${i}`} className="flex items-center justify-between gap-2 rounded-md bg-bg-subtle px-2.5 py-1.5">
                      <span className="text-[12px] capitalize text-text-secondary">{(search.platform ?? "social media").replace("_", " ")}</span>
                      <span className={cn(
                        "font-mono text-[10px] font-semibold",
                        search.status === "FOUND" ? "text-aman-fg" : search.status === "UNAVAILABLE" ? "text-bahaya-fg" : "text-text-muted",
                      )}>
                        {search.status ?? "UNKNOWN"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {!social.found && (
                <p className="text-text-muted">Tidak ada jejak relevan ditemukan di media sosial.</p>
              )}
              {social.found && (
                <>
                  {(social.posts ?? []).map((p, i) => (
                    <p key={i} className="rounded-md bg-bg-subtle px-3 py-2 text-[12px] text-text-secondary">
                      {p.snippet}
                    </p>
                  ))}
                  {(social.profiles ?? []).map((p, i) => (
                    <a
                      key={i}
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block text-text-primary underline underline-offset-2 hover:text-text-secondary"
                    >
                      @{p.username}{p.title ? ` - ${p.title}` : ""}
                    </a>
                  ))}
                  {(social.risk_flags ?? []).map((f) => (
                    <Flag key={f} text={f} kind="risk" />
                  ))}
                </>
              )}
            </div>
          </SectionRow>
        )}
      </div>
    </section>
  );
}
