import { createHash, createHmac, timingSafeEqual } from "crypto";

// Hanya dipakai di route handler server. Nilai env tanpa prefix NEXT_PUBLIC_ tidak ikut ke bundle browser.
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const SESSION_SECRET = process.env.ADMIN_SESSION_SECRET;

export const ADMIN_COOKIE = "verifin_admin";

export function adminConfigured(): boolean {
  return Boolean(ADMIN_PASSWORD && SESSION_SECRET);
}

export const ADMIN_SESSION_SECONDS = 60 * 60 * 8;

function sign(exp: number): string {
  // Tanda tangan bergantung pada password: mengganti password langsung membatalkan semua sesi.
  const pwHash = createHash("sha256").update(ADMIN_PASSWORD as string).digest("hex");
  return createHmac("sha256", SESSION_SECRET as string).update(`${exp}:${pwHash}`).digest("hex");
}

/** Token sesi `<kedaluwarsa>.<hmac>`. Masa berlaku dicek server, bukan hanya umur cookie. */
export function issueAdminToken(now = Date.now()): string | null {
  if (!ADMIN_PASSWORD || !SESSION_SECRET) return null;
  const exp = Math.floor(now / 1000) + ADMIN_SESSION_SECONDS;
  return `${exp}.${sign(exp)}`;
}

export function verifyAdminToken(token: string, now = Date.now()): boolean {
  if (!ADMIN_PASSWORD || !SESSION_SECRET) return false;
  const [expRaw, sig] = token.split(".");
  const exp = Number(expRaw);
  if (!Number.isFinite(exp) || !sig || exp * 1000 <= now) return false;
  return safeEqual(sig, sign(exp));
}

export function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export function isAdminRequest(request: Request): boolean {
  const cookieHeader = request.headers.get("cookie") || "";
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${ADMIN_COOKIE}=([^;]+)`));
  const token = match ? decodeURIComponent(match[1]) : "";
  return token !== "" && verifyAdminToken(token);
}
