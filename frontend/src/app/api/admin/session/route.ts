import { NextResponse } from "next/server";
import { createHash, timingSafeEqual } from "crypto";

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "verifin2026";
const SESSION_SECRET = process.env.ADMIN_SESSION_SECRET ?? "verifin-admin-secret-change-me";

function expectedToken(): string {
  return createHash("sha256").update(`${ADMIN_PASSWORD}:${SESSION_SECRET}`).digest("hex");
}

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export async function GET(request: Request) {
  const cookieHeader = request.headers.get("cookie") || "";
  const match = cookieHeader.match(/(?:^|;\s*)verifin_admin=([^;]+)/);
  const token = match ? decodeURIComponent(match[1]) : "";
  const authed = token !== "" && safeEqual(token, expectedToken());
  return NextResponse.json({ authed });
}
