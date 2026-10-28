import type { NextConfig } from "next";

// Tanpa NEXT_PUBLIC_API_URL, frontend memanggil /api/v1 di origin yang sama dan Next meneruskannya
// ke BACKEND_INTERNAL_URL. Dipakai stack home: sebelumnya build home jatuh ke API produksi karena
// nilai bawaan compose, sehingga uji di home ikut menulis ke DB produksi.
const backend = process.env.BACKEND_INTERNAL_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["100.111.60.81"],
  // SSE /verify/stream lewat rewrite: kompresi menahan event sampai respons selesai.
  compress: !backend,
  // Verifikasi berjalan 20–90 dtk; batas proxy bawaan Next 30 dtk membuat rewrite menjawab 500.
  experimental: { proxyTimeout: 180_000 },
  async rewrites() {
    return backend ? [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }] : [];
  },
};

export default nextConfig;
