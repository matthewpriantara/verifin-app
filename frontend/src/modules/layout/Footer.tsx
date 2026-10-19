"use client";

import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

export function Footer() {
  return (
    <footer className="relative overflow-hidden bg-text-primary text-bg-elevated/80 pt-10 pb-6">

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        {/* Upper Grid Layout */}
        <div className="grid grid-cols-1 gap-10 md:grid-cols-12 pb-8 border-b border-bg/10">

          {/* Col 1: Branding & Description */}
          <div className="md:col-span-5 space-y-4">
            <Link href="/" className="inline-flex min-h-11 items-center group">
              <Logo size="md" inverted />
            </Link>
            <p className="text-[13px] leading-relaxed text-bg/70 max-w-sm">
              Cek lowongan kerja sebelum melamar. Verifin memeriksa nomor, perusahaan, alamat, email,
              dan formulir lewat sumber publik, lalu menjelaskan alasan di balik setiap skor.
            </p>
          </div>

          {/* Col 2: Navigation Links */}
          <div className="md:col-span-3 space-y-3">
            <h4 className="text-[12px] font-semibold tracking-wider uppercase text-bg">
              Navigasi
            </h4>
            <ul className="text-[14px]">
              <li>
                <Link href="/" className="flex min-h-11 items-center text-bg/70 hover:text-bg transition-colors">
                  Cek lowongan
                </Link>
              </li>
              <li>
                <Link href="/cari" className="flex min-h-11 items-center text-bg/70 hover:text-bg transition-colors">
                  Cari loker
                </Link>
              </li>
              <li>
                <Link href="/report-job" className="flex min-h-11 items-center text-bg/70 hover:text-bg transition-colors">
                  Lapor komunitas
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 3: Tech Stack & System Status */}
          <div className="md:col-span-4 space-y-3.5">
            <h4 className="text-[12px] font-semibold tracking-wider uppercase text-bg">
              Sumber & teknologi
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {["PaddleOCR", "SearXNG", "OpenStreetMap", "Kaspersky Who Calls", "WHOIS/RDAP", "NetworkX", "LLM"].map((tech) => (
                <span
                  key={tech}
                  className="rounded bg-bg/5 border border-bg/10 px-2.5 py-1 font-mono text-[11px] text-bg/70 hover:bg-bg/10 transition-colors"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

        </div>

        {/* Lower Disclaimer & Info */}
        <div className="pt-6 flex flex-col-reverse md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <p className="text-[12px] text-bg/60 font-medium">
              &copy; {new Date().getFullYear()} VERIFIN. Hak Cipta Dilindungi.
            </p>
            <p className="text-[12px] text-bg/60">
              Tim Three Achilles · Universitas Gadjah Mada
            </p>
          </div>
          <p className="text-[12px] leading-relaxed text-bg/60 max-w-md md:text-right">
            Hasil Verifin adalah penilaian risiko otomatis dari bukti publik, bukan putusan hukum
            dan bukan jaminan legalitas perusahaan.
          </p>
        </div>
      </div>
    </footer>
  );
}
