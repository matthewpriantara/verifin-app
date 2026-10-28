import type { OsintPayload } from "@/types/verify";
import { cn } from "@/lib/utils";
import { communityReportedPhones, getPhoneStatus, getcontactLine } from "@/lib/phone-status";
import {
  Globe,
  Phone,
  MagnifyingGlass,
  ShareNetwork,
  Graph,
  Warning,
  CheckCircle,
  ArrowSquareOut,
} from "@phosphor-icons/react/dist/ssr";

interface EvidencePanelProps {
  osint?: OsintPayload | null;
}

interface DomainEvidence {
  domain?: string | null;
  age_years?: number | string | null;
  created_at?: string | null;
  is_new?: boolean | null;
  skipped?: string;
}

interface EmailSecurityEvidence {
  mx_active?: boolean;
  spf_active?: boolean;
  dmarc_active?: boolean;
}

function isJunkSnippet(s?: string): boolean {
  if (!s) return true;
  const low = s.toLowerCase();
  return (
    ["adsbygoogle", "function timer", "setinterval", "window.location", "document.getelementbyid",
      "mutationobserver", "you are being redirected", '{"require":', "could not load"]
      .some((token) => low.includes(token)) ||
    /function\s*\(|var\s+\w+|const\s+\w+/i.test(s) ||
    // selector CSS seperti ".elementor-26052 .elementor-element > .x"
    /(?:\.[\w-]+\s*(?:>|,|\s)\s*){4,}|:not\(|var\(--|\{[^}]*:[^}]*;/.test(s)
  );
}

function websiteLabel(status?: string, ok?: boolean | null): string {
  switch (status) {
    case "AVAILABLE": return "Bisa dibuka";
    case "HTTP_ERROR": return "Situs menjawab error";
    case "NOT_FOUND": return "Domain tidak terdaftar";
    case "BLOCKED": return "Dilindungi anti-bot, isi tidak terbaca";
    case "UNREACHABLE": return "Tidak bisa dibuka saat pemeriksaan";
    default: return ok ? "Bisa dibuka" : "Tidak dapat dibuka";
  }
}

function hostOf(url?: string): string {
  try {
    return new URL(url ?? "").hostname.replace(/^www\./, "");
  } catch {
    return url ?? "";
  }
}

function formatDate(value?: string | null): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
  return new Date(value).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
}

// "14.64" dari WHOIS → "14 tahun"; di bawah setahun ditulis dalam bulan.
function formatDomainAge(domain: DomainEvidence): string {
  const years = typeof domain.age_years === "number" ? domain.age_years : Number(domain.age_years);
  if (!Number.isFinite(years)) return "Tidak diketahui";
  if (years < 1) return `${Math.max(1, Math.round(years * 12))} bulan`;
  return `${Math.floor(years)} tahun`;
}

function Section({ title, icon: Icon, children }: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-border py-5 first:border-t-0 first:pt-0 last:pb-0">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={16} weight="bold" className="text-text-muted" />
        <h4 className="text-[14px] font-semibold text-text-primary">{title}</h4>
      </div>
      <div className="text-[13px] leading-relaxed text-text-secondary">{children}</div>
    </div>
  );
}

function Status({ text, kind }: { text: string; kind: "risk" | "safe" | "neutral" }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[12px] font-medium",
      kind === "risk" && "border-bahaya-border bg-bahaya-bg text-bahaya-fg",
      kind === "safe" && "border-aman-border bg-aman-bg text-aman-fg",
      kind === "neutral" && "border-border bg-bg-subtle text-text-secondary",
    )}>
      {kind === "risk" && <Warning size={12} weight="fill" />}
      {kind === "safe" && <CheckCircle size={12} weight="fill" />}
      {text}
    </span>
  );
}

function ResultLink({ title, url, note }: { title?: string; url?: string; note?: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="group flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-bg-subtle"
    >
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-medium text-text-primary">{title || hostOf(url)}</span>
        <span className="block truncate text-[12px] text-text-muted">{note ? `${note} · ` : ""}{hostOf(url)}</span>
      </span>
      <ArrowSquareOut size={14} className="shrink-0 text-text-muted group-hover:text-text-primary" />
    </a>
  );
}

export function EvidencePanel({ osint }: EvidencePanelProps) {
  if (!osint) {
    return (
      <section className="rounded-2xl border border-border bg-bg-elevated p-5">
        <h3 className="text-[15px] font-semibold text-text-primary">Bukti dari sumber publik</h3>
        <p className="mt-1 text-[13px] text-text-muted">Tidak ada data pemeriksaan untuk laporan ini.</p>
      </section>
    );
  }

  const domain = (osint.domain ?? {}) as DomainEvidence;
  const emailSec = (osint.email_security ?? {}) as EmailSecurityEvidence;
  const phones = osint.phones ?? [];
  const web = osint.web;
  const social = osint.social;
  const scam = web?.scam_check;

  // Hasil pencarian digabung lintas query; URL sama hanya tampil sekali.
  const seen = new Set<string>();
  const results = (web?.searches ?? [])
    .flatMap((s) => s.results ?? [])
    .filter((r) => {
      const key = (r.url ?? "").replace(/\/$/, "");
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  const resultCount = web?.evidence_counts?.relevant_results ?? results.length;
  const searchUnavailable =
    (web?.searches ?? []).length > 0 && (web?.searches ?? []).every((s) => s.status === "UNAVAILABLE");
  // Tautan internal yang sengaja tidak dibuka (perlindungan server) tidak ditampilkan sebagai situs.
  const websites = (web?.websites ?? []).filter((w) => w.url && w.website_status !== "SKIPPED");
  const network = osint.fraud_network;
  const community = network?.community_reports;
  const approvedReports = community?.status === "COMPLETED" ? Number(community.report_count ?? 0) : 0;
  const pendingReports = Number(community?.pending_report_count ?? 0);
  const reportedPhones = communityReportedPhones(community?.reported_phones);
  const otherCases = Number(network?.total_case_count ?? 0);
  const fraudCases = Number(network?.fraud_case_count ?? 0);
  const registered = formatDate(domain.created_at);

  return (
    <section className="rounded-2xl border border-border bg-bg-elevated p-5 sm:p-6">
      <div className="mb-5">
        <h3 className="text-[15px] font-semibold text-text-primary">Bukti dari sumber publik</h3>
        <p className="mt-1 text-[13px] text-text-muted">
          Diambil langsung dari WHOIS, Kaspersky Who Calls, GetContact, OpenStreetMap, dan mesin pencari saat pemeriksaan.
        </p>
      </div>

      {domain.domain && domain.skipped === "free_email" && (
        <Section title="Domain email" icon={Globe}>
          <p>
            Email memakai layanan gratisan (<span className="font-mono text-text-primary">{domain.domain}</span>). Umur domain dan
            pengaturan SPF/DMARC tidak diperiksa karena domain ini bukan milik perusahaan.
          </p>
        </Section>
      )}

      {domain.domain && domain.skipped !== "free_email" && (
        <Section title="Domain email" icon={Globe}>
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-[12px] text-text-muted">Domain</dt>
              <dd className="font-mono text-[13px] text-text-primary">{domain.domain}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-text-muted">Umur domain</dt>
              <dd className="text-[13px] text-text-primary">
                {formatDomainAge(domain)}
                {registered && <span className="text-text-muted"> (terdaftar {registered})</span>}
                {domain.is_new && <span className="ml-1 text-bahaya-fg">· baru, kurang dari 90 hari</span>}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-[12px] text-text-muted">Pengaturan email</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                <Status text={`Server email ${emailSec.mx_active ? "aktif" : "tidak ada"}`} kind={emailSec.mx_active ? "safe" : "neutral"} />
                <Status text={`SPF ${emailSec.spf_active ? "aktif" : "tidak ada"}`} kind={emailSec.spf_active ? "safe" : "neutral"} />
                <Status text={`DMARC ${emailSec.dmarc_active ? "aktif" : "tidak ada"}`} kind={emailSec.dmarc_active ? "safe" : "neutral"} />
              </dd>
            </div>
          </dl>
        </Section>
      )}

      {phones.length > 0 && (
        <Section title="Reputasi nomor" icon={Phone}>
          <ul className="space-y-3">
            {phones.map((p, i) => {
              const status = getPhoneStatus(p, reportedPhones);
              const operator = (p.comments ?? []).find((c) => /operator/i.test(c));
              const getcontact = getcontactLine(p.getcontact);
              return (
                <li key={i} className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <span className="font-mono text-[14px] text-text-primary">{p.phone ?? "-"}</span>
                    {operator && <span className="block text-[12px] text-text-muted">{operator}</span>}
                    {getcontact && <span className="block text-[12px] text-text-muted">{getcontact}</span>}
                  </span>
                  <Status text={status.label} kind={status.kind} />
                </li>
              );
            })}
          </ul>
          {phones.some((p) => p.getcontact?.probe_status) && (
            <p className="mt-3 text-[12px] text-text-muted">
              GetContact memberi jumlah tag, label spam, dan (untuk sebagian nomor) berapa tag yang memuat kata
              penipuan. Nama pemilik dan isi tag tidak ditampilkan atau disimpan. Sinyal ini uji coba.
            </p>
          )}
        </Section>
      )}

      <Section title="Pencarian web" icon={MagnifyingGlass}>
        {searchUnavailable ? (
          <p>Mesin pencari tidak dapat dihubungi saat pemeriksaan, jadi bagian ini belum ada datanya.</p>
        ) : resultCount > 0 ? (
          <>
            <p className="mb-2">{resultCount} hasil menyebut nama perusahaan ini. Ini jejak publik, bukan bukti legalitas.</p>
            <div className="-mx-3">
              {results.slice(0, 5).map((r, i) => (
                <ResultLink
                  key={i}
                  title={r.title}
                  url={r.url}
                  note={r.source_type === "official" ? "Domain sama dengan email/link lowongan" : undefined}
                />
              ))}
            </div>
          </>
        ) : (
          <p>Pencarian tidak menemukan hasil yang menyebut nama perusahaan ini.</p>
        )}
        {(web?.neutral_notes ?? []).map((note, i) => (
          <p key={i} className="mt-2 text-[12px] text-text-muted">{note}</p>
        ))}
      </Section>

      {scam && scam.status && scam.status !== "SKIPPED" && (
        <Section title="Peringatan lowongan palsu atas nama ini" icon={Warning}>
          {scam.status === "UNAVAILABLE" ? (
            <p>Pencarian peringatan tidak dapat dijalankan saat pemeriksaan.</p>
          ) : (scam.results ?? []).length > 0 ? (
            <>
              <p className="mb-2">
                {(scam.results ?? []).length} artikel memperingatkan lowongan palsu yang memakai nama ini. Nama ini pernah dicatut,
                jadi pastikan lowongan lewat kanal resmi perusahaan.
              </p>
              <div className="-mx-3">
                {(scam.results ?? []).slice(0, 4).map((r, i) => (
                  <ResultLink key={i} title={r.title} url={r.url} />
                ))}
              </div>
            </>
          ) : (
            <p>Tidak ditemukan artikel peringatan atau bantahan yang menyebut nama ini.</p>
          )}
        </Section>
      )}

      {social && (social.profiles ?? []).length > 0 && (
        <Section title="Media sosial" icon={ShareNetwork}>
          {social.found_by_name_only && (
            <p className="mb-2">
              Akun di bawah ditemukan lewat pencarian nama dan tidak ditautkan oleh lowongan. Akun ini milik pemilik nama,
              bukan bukti bahwa lowongan berasal darinya.
            </p>
          )}
          <div className="-mx-3">
            {(social.profiles ?? []).slice(0, 5).map((p, i) => (
              <ResultLink key={i} title={p.title || p.username} url={p.url} />
            ))}
          </div>
        </Section>
      )}

      {network && (
        <Section title="Riwayat Verifin dan laporan komunitas" icon={Graph}>
          {network.status !== "COMPLETED" ? (
            <p>Riwayat kasus tidak dapat diperiksa saat pemeriksaan ini.</p>
          ) : (
            <ul className="space-y-2">
              <li className="flex flex-wrap items-center justify-between gap-2">
                <span>Laporan komunitas yang disetujui admin</span>
                <Status
                  text={approvedReports > 0 ? `${approvedReports} laporan` : "Belum ada"}
                  kind={approvedReports > 0 ? "risk" : "neutral"}
                />
              </li>
              {pendingReports > 0 && (
                <li className="text-[12px] text-text-muted">
                  {pendingReports} laporan lain masih menunggu tinjauan admin dan belum dipakai sebagai bukti.
                </li>
              )}
              <li className="flex flex-wrap items-center justify-between gap-2">
                <span>Nomor, email, atau nama yang sama di lowongan lain</span>
                <Status
                  text={otherCases > 0 ? `${otherCases} kasus${fraudCases > 0 ? `, ${fraudCases} BAHAYA` : ""}` : "Belum pernah muncul"}
                  kind={fraudCases > 0 ? "risk" : "neutral"}
                />
              </li>
              {(network.matched_entities ?? []).slice(0, 4).map((m, i) => (
                <li key={i} className="text-[12px] text-text-muted">
                  <span className="font-mono text-text-secondary">{m.entity_value}</span> muncul di {m.total_appearances} kasus
                  {m.fraud_appearances ? `, ${m.fraud_appearances} di antaranya BAHAYA` : ""}.
                </li>
              ))}
              {(network.syndicate_analysis?.syndicate_alerts ?? []).slice(0, 3).map((a, i) => (
                <li key={`syn-${i}`} className="text-[12px] text-bahaya-fg">{a.detail}</li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {websites.length > 0 && (
        <Section title="Situs yang dibuka" icon={Globe}>
          <ul className="space-y-3">
            {websites.map((w, i) => (
              <li key={i}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <a href={w.url} target="_blank" rel="noreferrer" className="break-all font-mono text-[13px] text-text-primary hover:underline">
                    {w.url}
                  </a>
                  <Status text={websiteLabel(w.website_status, w.ok)} kind={w.website_status === "NOT_FOUND" || w.website_status === "HTTP_ERROR" ? "risk" : "neutral"} />
                </div>
                {w.snippet && !isJunkSnippet(w.snippet) && (
                  <p className="mt-1 line-clamp-3 text-[12px] text-text-muted">{w.snippet}</p>
                )}
                {(w.neutral_notes ?? []).map((note, j) => (
                  <p key={j} className="mt-1 text-[12px] text-text-muted">{note}</p>
                ))}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </section>
  );
}
