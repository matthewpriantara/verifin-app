import {
  FacebookLogo,
  InstagramLogo,
  LinkedinLogo,
  ShareNetwork,
  TiktokLogo,
  TwitterLogo,
} from "@phosphor-icons/react";

// Warna merek dipakai karena ikon mewakili platform pihak ketiga, bukan elemen brand Verifin.
export function SocialPlatformIcon({ platform, size = 16 }: { platform: string; size?: number }) {
  const p = platform.toLowerCase();
  if (p.includes("instagram")) return <InstagramLogo size={size} weight="fill" className="text-pink-500" aria-hidden />;
  if (p.includes("facebook")) return <FacebookLogo size={size} weight="fill" className="text-blue-600" aria-hidden />;
  if (p.includes("linkedin")) return <LinkedinLogo size={size} weight="fill" className="text-blue-700" aria-hidden />;
  if (p.includes("tiktok")) return <TiktokLogo size={size} weight="fill" className="text-text-primary" aria-hidden />;
  if (p.includes("twitter") || p === "x" || p === "x_twitter" || p.includes("x.com"))
    return <TwitterLogo size={size} weight="fill" className="text-sky-500" aria-hidden />;
  return <ShareNetwork size={size} weight="bold" className="text-text-muted" aria-hidden />;
}
