import { createHash, timingSafeEqual } from "crypto";

// Hanya dipakai di route handler server. Nilai env tanpa prefix NEXT_PUBLIC_ tidak ikut ke bundle browser.
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const SESSION_SECRET = process.env.ADMIN_SESSION_SECRET;

export const ADMIN_COOKIE = "verifin_admin";

export function adminConfigured(): boolean {
  return Boolean(ADMIN_PASSWORD && SESSION_SECRET);
}

export function expectedAdminToken(): string | null {
  if (!ADMIN_PASSWORD || !SESSION_SECRET) return null;
  return createHash("sha256").update(`${ADMIN_PASSWORD}:${SESSION_SECRET}`).digest("hex");
}

export function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export function isAdminRequest(request: Request): boolean {
  const exp = expectedAdminToken();
  if (!exp) return false;
  const cookieHeader = request.headers.get("cookie") || "";
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${ADMIN_COOKIE}=([^;]+)`));
  const token = match ? decodeURIComponent(match[1]) : "";
  return token !== "" && safeEqual(token, exp);
}
