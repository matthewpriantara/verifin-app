import type { OsintPayload } from "@/types/verify";
import { cn } from "@/lib/utils";
import {
  Globe,
  Phone,
  Buildings,
  ShareNetwork,
  Warning,
  CheckCircle,
  InstagramLogo,
  FacebookLogo,
  LinkedinLogo,
  TiktokLogo,
  TwitterLogo,
  MapPin,
  Star,
  Users,
  Heart,
  ChatCircle,
  Eye,
  Calendar,
  Link as LinkIcon,
} from "@phosphor-icons/react/dist/ssr";

interface EvidencePanelProps {
  osint?: OsintPayload | null;
}

function SectionRow({ label, icon: Icon, children, badge }: {
  label: string;
  icon: React.ElementType;
  children: React.ReactNode;
  badge?: string;
}) {
  return (
    <div className="border-t border-border py-5 first:border-t-0 first:pt-0">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent/10">
            <Icon size={14} weight="bold" className="text-accent" />
          </div>
          <p className="text-[12px] font-semibold uppercase tracking-widest text-text-primary">
            {label}
          </p>
        </div>
        {badge && (
          <span className="rounded-full bg-bg-subtle px-2 py-0.5 text-[10px] font-mono text-text-muted">
            {badge}
          </span>
        )}
      </div>
      <div className="text-[13px] leading-relaxed text-text-secondary">
        {children}
      </div>
    </div>
  );
}

function Flag({ text, kind }: { text: string; kind: "risk" | "safe" | "neutral" }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium",
      kind === "risk"
        ? "bg-bahaya-bg text-bahaya-fg border border-bahaya-fg/20"
        : kind === "safe"
        ? "bg-aman-bg text-aman-fg border border-aman-fg/20"
        : "bg-bg-subtle text-text-muted border border-border",
    )}>
      {kind === "risk"
        ? <Warning size={11} weight="fill" />
        : kind === "safe"
        ? <CheckCircle size={11} weight="fill" />
        : null}
      {text}
    </span>
  );
}

function SocialPlatformIcon({ platform }: { platform: string }) {
  const p = platform.toLowerCase();
  if (p.includes("instagram")) return <InstagramLogo size={16} weight="fill" className="text-pink-500" />;
  if (p.includes("facebook")) return <FacebookLogo size={16} weight="fill" className="text-blue-600" />;
  if (p.includes("linkedin")) return <LinkedinLogo size={16} weight="fill" className="text-blue-700" />;
  if (p.includes("tiktok")) return <TiktokLogo size={16} weight="fill" className="text-black" />;
  if (p.includes("twitter") || p.includes("x")) return <TwitterLogo size={16} weight="fill" className="text-sky-500" />;
  return <ShareNetwork size={16} weight="bold" className="text-text-muted" />;
}

function SocialProfileCard({ result }: { result: any }) {
  const url = result.url ?? "";
  const title = result.title ?? "";
  const snippet = result.snippet ?? "";
  
  // Extract platform dari URL
  let platform = "web";
  if (url.includes("instagram.com")) platform = "instagram";
  else if (url.includes("facebook.com")) platform = "facebook";
  else if (url.includes("linkedin.com")) platform = "linkedin";
  else if (url.includes("tiktok.com")) platform = "tiktok";
  else if (url.includes("twitter.com") || url.includes("x.com")) platform = "twitter";

  // Extract followers/posts dari snippet Instagram
  const followersMatch = snippet.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:followers|pengikut)/i);
  const postsMatch = snippet.match(/(\d+(?:[.,]\d+)?)\s*(?:posts|postingan)/i);
  const followingMatch = snippet.match(/(\d+(?:[.,]\d+)?[KkMm]?)\s*(?:following|mengikuti)/i);

  const followers = followersMatch ? followersMatch[1] : null;
  const posts = postsMatch ? postsMatch[1] : null;
  const following = followingMatch ? followingMatch[1] : null;

  // Extract bio dari snippet (setelah "on Instagram:" atau sejenisnya)
  let bio = "";
  const bioMatch = snippet.match(/(?:on Instagram|di Instagram)[:\s]+"([^"]+)"/i);
  if (bioMatch) bio = bioMatch[1];
  else if (snippet.length > 50) bio = snippet.substring(0, 120) + "...";

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-bg-elevated to-bg-subtle/50 p-4 transition-all hover:border-accent/30 hover:shadow-lg">
      {/* Platform badge */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-bg-subtle">
            <SocialPlatformIcon platform={platform} />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              {platform}
            </p>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-[13px] font-medium text-text-primary hover:text-accent hover:underline"
            >
              {title.length > 40 ? title.substring(0, 40) + "..." : title}
            </a>
          </div>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="rounded-md p-1.5 text-text-muted transition-colors hover:bg-bg-subtle hover:text-text-primary"
        >
          <LinkIcon size={14} weight="bold" />
        </a>
      </div>

      {/* Stats grid */}
      {(followers || posts || following) && (
        <div className="mb-3 grid grid-cols-3 gap-2">
          {followers && (
            <div className="rounded-lg bg-bg-subtle/50 px-3 py-2 text-center">
              <div className="flex items-center justify-center gap-1 text-[10px] text-text-muted">
                <Users size={10} weight="bold" />
                <span>Followers</span>
              </div>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">{followers}</p>
            </div>
          )}
          {posts && (
            <div className="rounded-lg bg-bg-subtle/50 px-3 py-2 text-center">
              <div className="flex items-center justify-center gap-1 text-[10px] text-text-muted">
                <Heart size={10} weight="bold" />
                <span>Posts</span>
              </div>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">{posts}</p>
            </div>
          )}
          {following && (
            <div className="rounded-lg bg-bg-subtle/50 px-3 py-2 text-center">
              <div className="flex items-center justify-center gap-1 text-[10px] text-text-muted">
                <Eye size={10} weight="bold" />
                <span>Following</span>
              </div>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">{following}</p>
            </div>
          )}
        </div>
      )}

      {/* Bio */}
      {bio && (
        <div className="rounded-lg bg-bg-subtle/30 px-3 py-2">
          <p className="text-[11px] leading-relaxed text-text-secondary">{bio}</p>
        </div>
      )}

      {/* Verification badge */}
      <div className="mt-3 flex items-center gap-1.5">
        <CheckCircle size={12} weight="fill" className="text-aman-fg" />
        <span className="text-[10px] font-medium text-aman-fg">Jejak publik terverifikasi</span>
      </div>
    </div>
  );
}

function MapsLocationCard({ address, details }: { address: string; details: any }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-gradient-to-br from-bg-elevated to-bg-subtle/50">
      {/* Header */}
      <div className="border-b border-border bg-bg-subtle/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <MapPin size={16} weight="fill" className="text-accent" />
          <p className="text-[12px] font-semibold uppercase tracking-wider text-text-primary">
            Lokasi Terverifikasi
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <p className="text-[13px] font-medium text-text-primary">{address}</p>
        
        {details?.display_name && (
          <p className="mt-2 text-[11px] leading-relaxed text-text-muted">
            {details.display_name}
          </p>
        )}

        {/* Coordinates */}
        {details?.lat && details?.lon && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-bg-subtle/50 px-3 py-2">
            <MapPin size={12} weight="bold" className="text-text-muted" />
            <span className="font-mono text-[11px] text-text-secondary">
              {details.lat.toFixed(6)}, {details.lon.toFixed(6)}
            </span>
          </div>
        )}

        {/* Match level */}
        {details?.match_level && (
          <div className="mt-3">
            <Flag
              text={
                details.match_level === "street"
                  ? "Jalan ditemukan, nomor belum pasti"
                  : details.match_level === "exact"
                  ? "Alamat presisi terkonfirmasi"
                  : "Wilayah ditemukan"
              }
              kind={details.match_level === "exact" ? "safe" : "neutral"}
            />
          </div>
        )}

        {/* Google Maps link */}
        {details?.google_maps_url && (
          <a
            href={details.google_maps_url}
            target="_blank"
            rel="noreferrer"
            className="mt-3 flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-[12px] font-semibold text-white transition-all hover:bg-accent/90 hover:shadow-md"
          >
            <MapPin size={14} weight="bold" />
            Buka di Google Maps
          </a>
        )}
      </div>
    </div>
  );
}

export function EvidencePanel({ osint }: EvidencePanelProps) {
  if (!osint) {
    return (
      <section className="mt-6 rounded-2xl border border-border bg-bg-elevated p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
            <Warning size={20} weight="bold" className="text-accent" />
          </div>
          <div>
            <h3 className="text-[14px] font-bold uppercase tracking-wide text-text-primary">
              Bukti OSINT
            </h3>
            <p className="mt-0.5 text-[12px] text-text-muted">
              Tidak ada payload OSINT pada respons ini.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const domain = (osint.domain ?? {}) as any;
  const emailSec = (osint.email_security ?? {}) as any;
  const phones = (osint.phones ?? []) as any[];
  const companies = (osint.companies ?? []) as any[];
  const web = osint.web as any;
  const social = osint.social as any;
  const addresses = (osint.address_validations ?? []) as any[];

  // Extract social results dari web.searches
  const webSocialResults = (web?.searches ?? [])
    .flatMap((s: any) => s.results ?? [])
    .filter((r: any) => {
      const url = (r.url ?? "").toLowerCase();
      return (
        url.includes("instagram.com") ||
        url.includes("facebook.com") ||
        url.includes("linkedin.com") ||
        url.includes("tiktok.com") ||
        url.includes("threads.net")
      );
    })
    .slice(0, 6); // Top 6 social profiles

  const hasWebSocial = webSocialResults.length > 0;

  return (
    <section className="rounded-2xl border border-border bg-bg-elevated shadow-sm">
      {/* Header */}
      <div className="border-b border-border bg-gradient-to-r from-bg-subtle/50 to-transparent px-6 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
              <CheckCircle size={20} weight="fill" className="text-accent" />
            </div>
            <div>
              <h3 className="text-[14px] font-bold uppercase tracking-wide text-text-primary">
                Bukti OSINT
              </h3>
              <p className="mt-0.5 text-[12px] text-text-muted">
                Data dari sumber nyata — bukan rekaan model AI
              </p>
            </div>
          </div>
          {osint.evidence_policy?.mode && (
            <span className="shrink-0 rounded-full border border-border bg-bg-subtle px-3 py-1 text-[10px] font-mono font-semibold text-text-muted">
              {osint.evidence_policy.mode}
            </span>
          )}
        </div>
      </div>

      <div className="p-6">
        {/* Domain & Email Security */}
        <SectionRow label="Domain & Email Security" icon={Globe} badge="DNS/WHOIS">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-bg-subtle/30 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Umur Domain
              </p>
              <p className="mt-1 font-mono text-[13px] font-semibold text-text-primary">
                {String(domain.age_years ?? domain.created_at ?? "N/A")}
                {domain.is_new && (
                  <span className="ml-2 text-[11px] font-normal text-bahaya-fg">
                    (baru, {"<"}90 hari)
                  </span>
                )}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-bg-subtle/30 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Email Security
              </p>
              <div className="mt-1 flex items-center gap-3">
                <span className={cn(
                  "flex items-center gap-1 text-[12px] font-medium",
                  emailSec.spf_active ? "text-aman-fg" : "text-text-muted"
                )}>
                  {emailSec.spf_active ? <CheckCircle size={12} weight="fill" /> : <Warning size={12} weight="fill" />}
                  SPF
                </span>
                <span className={cn(
                  "flex items-center gap-1 text-[12px] font-medium",
                  emailSec.dmarc_active ? "text-aman-fg" : "text-text-muted"
                )}>
                  {emailSec.dmarc_active ? <CheckCircle size={12} weight="fill" /> : <Warning size={12} weight="fill" />}
                  DMARC
                </span>
              </div>
            </div>
          </div>
        </SectionRow>

        {/* Phone Reputation */}
        {phones.length > 0 && (
          <SectionRow label="Reputasi Nomor HP/WA" icon={Phone} badge="Kaspersky Who Calls">
            <div className="space-y-3">
              {phones.map((p, i) => (
                <div key={i} className="rounded-lg border border-border bg-bg-subtle/30 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-[14px] font-semibold text-text-primary">
                      {p.phone ?? "—"}
                    </span>
                    {p.reported_fraud ? (
                      <Flag text="Dilaporkan penipuan" kind="risk" />
                    ) : (
                      <Flag text="Bersih dari laporan penipuan" kind="safe" />
                    )}
                  </div>
                  {p.summary && (
                    <p className="mt-2 text-[12px] leading-relaxed text-text-muted">{p.summary}</p>
                  )}
                  {p.comments && p.comments.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {p.comments.slice(0, 2).map((c: string, j: number) => (
                        <p key={j} className="text-[11px] text-text-muted">• {c}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </SectionRow>
        )}

        {/* Company Profile */}
        {companies.length > 0 && (
          <SectionRow label="Profil Perusahaan dari Web Publik" icon={Buildings} badge="SERP Analysis">
            <div className="space-y-3">
              {companies.map((c, i) => (
                <div key={i} className="rounded-lg border border-border bg-bg-subtle/30 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[14px] font-semibold text-text-primary">
                      {String(c.name ?? c.company_name ?? "—")}
                    </span>
                    {typeof c.stats === "object" && c.stats !== null && (
                      <span className="rounded-full bg-accent/10 px-3 py-1 text-[11px] font-semibold text-accent">
                        {String((c.stats as Record<string, unknown>).public_mentions ?? 0)} hasil web relevan
                      </span>
                    )}
                  </div>
                  {(c.safe_flags ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(c.safe_flags ?? []).slice(0, 2).map((f: string) => (
                        <Flag key={f} text={f} kind="safe" />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </SectionRow>
        )}

        {/* Location & Maps */}
        {addresses.length > 0 && addresses[0]?.address_details && (
          <SectionRow label="Lokasi & Verifikasi Peta" icon={MapPin} badge="OpenStreetMap">
            <MapsLocationCard
              address={addresses[0].address_input ?? ""}
              details={addresses[0].address_details}
            />
          </SectionRow>
        )}

        {/* Social Media OSINT - Canggih */}
        {hasWebSocial && (
          <SectionRow label="Social Media Intelligence" icon={ShareNetwork} badge={`${webSocialResults.length} profil ditemukan`}>
            <div className="space-y-3">
              <p className="text-[12px] text-text-muted">
                Jejak digital publik terverifikasi dari berbagai platform media sosial:
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {webSocialResults.map((result: any, i: number) => (
                  <SocialProfileCard key={i} result={result} />
                ))}
              </div>

              {/* Platform status summary */}
              {social?.social_searches && social.social_searches.length > 0 && (
                <div className="mt-4 rounded-lg border border-border bg-bg-subtle/30 p-4">
                  <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Status Pencarian per Platform
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {social.social_searches.map((search: any, i: number) => (
                      <div
                        key={`${search.platform ?? "platform"}-${i}`}
                        className="flex items-center justify-between rounded-md bg-bg-elevated px-3 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <SocialPlatformIcon platform={search.platform ?? ""} />
                          <span className="text-[12px] font-medium capitalize text-text-secondary">
                            {(search.platform ?? "social").replace("_", " ")}
                          </span>
                        </div>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-mono font-bold",
                            search.status === "FOUND"
                              ? "bg-aman-bg text-aman-fg"
                              : search.status === "UNAVAILABLE"
                              ? "bg-bahaya-bg text-bahaya-fg"
                              : "bg-bg-subtle text-text-muted"
                          )}
                        >
                          {search.status === "FOUND" ? "✓" : search.status === "UNAVAILABLE" ? "✗" : "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </SectionRow>
        )}

        {/* Web Evidence */}
        {web?.websites && web.websites.length > 0 && (
          <SectionRow label="Website & Web Evidence" icon={Globe} badge={`${web.websites.length} situs`}>
            <div className="space-y-3">
              {web.websites.map((w: any, i: number) => (
                <div key={i} className="rounded-lg border border-border bg-bg-subtle/30 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span
                      className={cn(
                        "font-mono text-[13px] font-medium",
                        w.ok ? "text-text-primary" : "text-text-muted line-through"
                      )}
                    >
                      {w.url}
                    </span>
                    {!w.ok && <Flag text="Tidak dapat diakses" kind="risk" />}
                  </div>
                  {w.snippet && (
                    <p className="mt-2 text-[12px] leading-relaxed text-text-muted">{w.snippet}</p>
                  )}
                  {(w.risk_flags ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(w.risk_flags ?? []).map((f: string) => (
                        <Flag key={f} text={f} kind="risk" />
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div className="flex flex-wrap gap-2">
                {(web.risk_flags ?? []).map((f: string) => (
                  <Flag key={f} text={f} kind="risk" />
                ))}
                {(web.safe_flags ?? []).map((f: string) => (
                  <Flag key={f} text={f} kind="safe" />
                ))}
              </div>
            </div>
          </SectionRow>
        )}
      </div>
    </section>
  );
}
