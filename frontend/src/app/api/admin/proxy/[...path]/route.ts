import { NextResponse } from "next/server";
import { isAdminRequest } from "@/lib/adminAuth";

// Proxy server-side untuk endpoint admin backend. Browser hanya membawa cookie sesi;
// token X-Admin-Token ditambahkan di sini sehingga tidak pernah terlihat di klien.
const API_BASE = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN;

// Hanya endpoint admin yang boleh diteruskan.
const ALLOWED = [/^cases$/, /^community\/reports$/, /^community\/reports\/[0-9a-f-]{36}$/];

async function forward(request: Request, path: string[]) {
  if (!isAdminRequest(request)) {
    return NextResponse.json({ detail: "Sesi admin tidak valid." }, { status: 401 });
  }
  if (!API_BASE || !ADMIN_API_TOKEN) {
    return NextResponse.json({ detail: "API_URL atau ADMIN_API_TOKEN belum diset." }, { status: 500 });
  }
  const joined = path.join("/");
  if (!ALLOWED.some((re) => re.test(joined))) {
    return NextResponse.json({ detail: "Endpoint tidak diizinkan." }, { status: 404 });
  }

  const search = new URL(request.url).search;
  const init: RequestInit = {
    method: request.method,
    headers: { "X-Admin-Token": ADMIN_API_TOKEN, "Content-Type": "application/json" },
    cache: "no-store",
  };
  if (request.method !== "GET") init.body = await request.text();

  const res = await fetch(`${API_BASE}/api/v1/${joined}${search}`, init);
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, { params }: Ctx) {
  return forward(request, (await params).path);
}

export async function PATCH(request: Request, { params }: Ctx) {
  return forward(request, (await params).path);
}
