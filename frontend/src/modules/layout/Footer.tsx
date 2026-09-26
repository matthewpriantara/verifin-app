"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ShieldCheck } from "@phosphor-icons/react";

export function Footer() {
  return (
    <footer className="relative overflow-hidden bg-text-primary text-bg-elevated/80 pt-10 pb-6">

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        {/* Upper Grid Layout */}
        <div className="grid grid-cols-1 gap-10 md:grid-cols-12 pb-8 border-b border-bg/10">
          
          {/* Col 1: Branding & Description */}
          <div className="md:col-span-5 space-y-4">
            <Link href="/" className="inline-flex items-center gap-2 group">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-bg text-text-primary transition-transform group-hover:scale-105">
                <ShieldCheck size={18} weight="bold" />
              </div>
              <span className="font-mono text-xl font-bold tracking-tight text-bg">
                VERIFIN
              </span>
            </Link>
            <p className="text-[13px] leading-relaxed text-bg/60 max-w-sm">
              Platform verifikasi lowongan kerja terintegrasi. Memanfaatkan OSINT, 
              graf hubungan (Heterogeneous Graph), dan Explainable AI (Evidence Attribution) untuk menciptakan ekosistem pencarian kerja yang aman.
            </p>
          </div>

          {/* Col 2: Navigation Links */}
          <div className="md:col-span-3 space-y-3">
            <h4 className="text-[12px] font-semibold tracking-wider uppercase text-bg">
              Navigasi
            </h4>
            <ul className="space-y-2 text-[13px]">
              <li>
                <Link href="/" className="text-bg/60 hover:text-bg transition-colors">
                  Verifikasi Baru
                </Link>
              </li>
              <li>
                <Link href="/report-job" className="text-bg/60 hover:text-bg transition-colors">
                  Lapor Komunitas
                </Link>
              </li>
              <li>
                <Link href="/admin" className="text-bg/60 hover:text-bg transition-colors">
                  Dashboard Admin
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 3: Tech Stack & System Status */}
          <div className="md:col-span-4 space-y-3.5">
            <h4 className="text-[12px] font-semibold tracking-wider uppercase text-bg">
              Teknologi & Engine
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {["PaddleOCR", "OSINT", "NetworkX", "Evidence Attribution", "LLM Reasoning"].map((tech) => (
                <span
                  key={tech}
                  className="rounded bg-bg/5 border border-bg/10 px-2.5 py-1 font-mono text-[10px] text-bg/70 hover:bg-bg/10 transition-colors"
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
            <p className="text-[12px] text-bg/40 font-medium">
              &copy; {new Date().getFullYear()} VERIFIN. Hak Cipta Dilindungi.
            </p>
            <p className="text-[11px] text-bg/30">
              Dikembangkan sebagai solusi deteksi penipuan kerja cerdas.
            </p>
          </div>
          <p className="text-[11px] md:text-[12px] leading-relaxed text-bg/35 max-w-md md:text-right font-light">
            Disclaimer: Hasil analisis risiko yang disajikan bersifat indikatif 
            dan merupakan hasil pemrosesan AI secara otomatis. Bukan merupakan putusan hukum final.
          </p>
        </div>
      </div>
    </footer>
  );
}
