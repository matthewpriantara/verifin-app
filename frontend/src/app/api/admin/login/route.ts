import { NextResponse } from "next/server";
import { ADMIN_COOKIE, adminConfigured, expectedAdminToken, safeEqual } from "@/lib/adminAuth";

// Password dibaca dari env SERVER-SIDE (tanpa prefix NEXT_PUBLIC_),
// sehingga tidak pernah dibundle ke client.
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

// Batas percobaan login per IP: 5 kali gagal dalam 15 menit. Disimpan di memori proses.
const MAX_FAILS = 5;
const WINDOW_MS = 15 * 60 * 1000;
const failures = new Map<string, number[]>();

function clientIp(request: Request): string {
  return (
    request.headers.get("cf-connecting-ip") ||
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    "unknown"
  );
}

function recentFailures(ip: string, now: number): number[] {
  const list = (failures.get(ip) || []).filter((t) => now - t < WINDOW_MS);
  failures.set(ip, list);
  return list;
}

export async function POST(request: Request) {
  if (!adminConfigured() || !ADMIN_PASSWORD) {
    return NextResponse.json(
      { ok: false, detail: "Konfigurasi server admin belum lengkap di .env." },
      { status: 500 }
    );
  }

  const ip = clientIp(request);
  const now = Date.now();
  const fails = recentFailures(ip, now);
  if (fails.length >= MAX_FAILS) {
    const retryAfter = Math.ceil((WINDOW_MS - (now - fails[0])) / 1000);
    return NextResponse.json(
      { ok: false, detail: `Terlalu banyak percobaan. Coba lagi dalam ${Math.ceil(retryAfter / 60)} menit.` },
      { status: 429, headers: { "Retry-After": String(retryAfter) } }
    );
  }

  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, detail: "Body tidak valid." }, { status: 400 });
  }

  const pw = body.password ?? "";
  if (!safeEqual(pw, ADMIN_PASSWORD)) {
    fails.push(now);
    return NextResponse.json({ ok: false, detail: "Password salah." }, { status: 401 });
  }

  failures.delete(ip);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_COOKIE, expectedAdminToken() as string, {
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
  res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}
