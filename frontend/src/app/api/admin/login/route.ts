import { NextResponse } from "next/server";
import { createHash, timingSafeEqual } from "crypto";

// Password dibaca dari env SERVER-SIDE (tanpa prefix NEXT_PUBLIC_),
// sehingga tidak pernah dibundle ke client.
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "verifin2026";
const SESSION_SECRET = process.env.ADMIN_SESSION_SECRET ?? "verifin-admin-secret-change-me";

function makeToken(): string {
  // Token = HMAC-like hash dari password + secret. Valid selama password/secret tidak berubah.
  return createHash("sha256").update(`${ADMIN_PASSWORD}:${SESSION_SECRET}`).digest("hex");
}

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export async function POST(request: Request) {
  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, detail: "Body tidak valid." }, { status: 400 });
  }

  const pw = body.password ?? "";
  if (!safeEqual(pw, ADMIN_PASSWORD)) {
    return NextResponse.json({ ok: false, detail: "Password salah." }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("verifin_admin", makeToken(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 jam
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set("verifin_admin", "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}
