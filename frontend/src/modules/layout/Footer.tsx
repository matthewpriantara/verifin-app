"use client";

import { motion } from "motion/react";

export function Footer() {
  return (
    <footer className="overflow-hidden bg-text-primary">
      {/* Top content */}
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 px-4 pt-10 pb-6 text-center sm:px-6">
        <p className="text-[12px] text-bg/50">
          Deteksi penipuan lowongan kerja dengan AI
        </p>
        <div className="flex flex-wrap justify-center gap-1.5">
          {["PaddleOCR", "OSINT", "NetworkX", "SHAP XAI"].map((tech) => (
            <span
              key={tech}
              className="rounded border border-bg/20 px-2 py-0.5 font-mono text-[10px] text-bg/40"
            >
              {tech}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-bg/25">
          Hasil analisis bersifat indikatif, bukan putusan hukum
        </p>
      </div>

      {/* Wordmark full-width — seperti Hermes */}
      <div className="relative w-full overflow-hidden">
        {/* Garis mengalir di balik wordmark */}
        {[30, 65].map((top, i) => (
          <motion.div
            key={top}
            aria-hidden
            className="pointer-events-none absolute h-px w-[200%] bg-gradient-to-r from-transparent via-bg/10 to-transparent"
            style={{ top: `${top}%` }}
            animate={{ x: ["-50%", "0%"] }}
            transition={{
              duration: 12 + i * 4,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        ))}

        <p
          aria-hidden
          className="select-none whitespace-nowrap text-center font-mono leading-none text-bg/[0.07]"
          style={{
            fontSize: "clamp(5rem, 28vw, 22rem)",
            letterSpacing: "-0.04em",
            fontWeight: 900,
          }}
        >
          VERIFIN
        </p>
      </div>
    </footer>
  );
}
