"use client";

import { useRef } from "react";
import { motion } from "motion/react";
import { VerifyBox } from "@/modules/verify/VerifyBox";
import { SearchHistory } from "@/modules/home/SearchHistory";
import {
  Scan,
  MagnifyingGlass,
  Graph,
  Cpu,
  ArrowDown,
  ShieldCheck,
} from "@phosphor-icons/react";

const STEPS = [
  {
    num: "01",
    icon: Scan,
    title: "Ekstraksi Entitas",
    desc: "Teks, gambar, atau URL diproses untuk mengidentifikasi nama perusahaan, nomor HP, email, tautan, alamat, dan besaran gaji.",
    tags: ["PaddleOCR bila gambar", "Hybrid NER", "Entity Extraction"],
  },
  {
    num: "02",
    icon: MagnifyingGlass,
    title: "Validasi OSINT Real-time",
    desc: "Enam kanal publik diperiksa paralel: WHOIS/DNS domain, reputasi nomor, peta OSM, pencarian web, media sosial, dan inspeksi Google Forms bila ada.",
    tags: ["WHOIS/DNS", "Kaspersky Who Calls", "OpenStreetMap", "Web & Social"],
  },
  {
    num: "03",
    icon: Graph,
    title: "Analisis Jaringan Penipuan",
    desc: "Graf NetworkX mencocokkan entitas dengan memori kasus untuk mendeteksi keterhubungan ke penipuan yang pernah dilaporkan.",
    tags: ["NetworkX", "Case Memory", "Fraud Graph"],
  },
  {
    num: "04",
    icon: Cpu,
    title: "Penilaian Risiko & Penjelasan",
    desc: "LLM menyusun verdict AMAN/WASPADA/BAHAYA hanya dari bukti yang terkumpul, lalu Evidence Attribution menunjukkan kontribusi tiap sinyal.",
    tags: ["LLM Reasoning", "Evidence Attribution", "Explainable AI"],
  },
];

/* Titik cahaya mengalir di connector garis */
function FlowConnector({ delay }: { delay: number }) {
  return (
    <div className="relative mx-2 hidden h-0.5 w-12 flex-shrink-0 overflow-hidden bg-border lg:block">
      <motion.div
        className="absolute inset-y-0 w-8 bg-gradient-to-r from-transparent via-text-primary/50 to-transparent"
        animate={{ x: ["-32px", "48px"] }}
        transition={{
          duration: 1.6,
          delay,
          repeat: Infinity,
          repeatDelay: 1.4,
          ease: "easeInOut",
        }}
      />
    </div>
  );
}

function StepCard({
  step,
  index,
}: {
  step: (typeof STEPS)[number];
  index: number;
}) {
  const Icon = step.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="flex h-full flex-col rounded-2xl border border-border bg-bg-elevated p-5 transition-colors hover:border-border-focus"
    >
      <div className="mb-3 flex items-center gap-2.5">
        <motion.div
          initial={{ scale: 0.7, opacity: 0 }}
          whileInView={{ scale: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: index * 0.1 + 0.15 }}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-text-primary"
        >
          <Icon size={15} weight="bold" className="text-bg-elevated" />
        </motion.div>
        <span className="font-mono text-[10px] font-semibold tracking-widest text-text-muted">
          {step.num}
        </span>
      </div>
      <h3 className="text-[15px] font-semibold text-text-primary">{step.title}</h3>
      <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-text-secondary">{step.desc}</p>
      <div className="mt-4 flex flex-wrap gap-1">
        {step.tags.map((tag) => (
          <span
            key={tag}
            className="rounded border border-border bg-bg-subtle px-1.5 py-0.5 font-mono text-[10px] text-text-muted"
          >
            {tag}
          </span>
        ))}
      </div>
    </motion.div>
  );
}

export default function HomePage() {
  const howRef = useRef<HTMLDivElement>(null);

  return (
    <div className="flex flex-1 flex-col">

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="mx-auto flex w-full max-w-6xl flex-col items-center gap-10 px-4 py-14 sm:px-6 sm:py-14 lg:flex-row lg:items-start lg:gap-16 lg:py-20">

        {/* Kiri — headline */}
        <div className="w-full flex-1">
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mb-4 font-mono text-[11px] uppercase tracking-widest text-text-muted"
          >
            Job Risk Platform
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
            className="text-[2rem] font-semibold leading-[1.15] tracking-tight text-text-primary sm:text-5xl lg:text-6xl"
          >
            Tahu sebelum<br />kamu melamar.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
            className="mt-4 max-w-lg text-justify text-[14px] leading-relaxed text-text-secondary sm:mt-5 sm:text-[15px]"
          >
            Lindungi perjalanan karirmu dari bahaya lowongan kerja palsu dan penipuan digital. Verifin memanfaatkan kecerdasan AI dan OSINT untuk memverifikasi profil perusahaan, keabsahan lokasi, nomor kontak, hingga jejak reputasi digital secara instan. Dapatkan rangkuman bukti risiko yang transparan dan dapat diaudit agar kamu bisa melamar kerja dengan percaya diri tanpa rasa cemas.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.22 }}
            className="mt-7 flex flex-wrap gap-x-6 gap-y-4 sm:mt-8 sm:gap-6"
          >
            {[
              { val: "6", unit: "Kanal", label: "Pemeriksaan publik" },
              { val: "4", unit: "Tahap", label: "Analisis Verifin" },
              { val: "Bukti", unit: "dulu", label: "Penjelasan transparan" },
            ].map(({ val, unit, label }) => (
              <div key={label}>
                <p className="font-mono text-xl font-semibold text-text-primary sm:text-2xl">
                  {val}
                  <span className="ml-1 text-[12px] font-normal text-text-muted sm:text-[13px]">{unit}</span>
                </p>
                <p className="text-[11px] text-text-muted sm:text-[12px]">{label}</p>
              </div>
            ))}
          </motion.div>

          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9 }}
            onClick={() => howRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="mt-10 hidden items-center gap-2 rounded-lg border border-border bg-text-primary px-3.5 py-2 text-[12px] font-medium text-white transition-colors hover:border-border-focus hover:text-black hover:bg-bg-elevated lg:flex"
          >
            <motion.span
              animate={{ y: [0, 3, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
            >
              <ArrowDown size={12} weight="bold" />
            </motion.span>
            Lihat cara kerja
          </motion.button>
        </div>

        {/* Kanan — VerifyBox */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className="w-full lg:max-w-md"
        >
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
              <ShieldCheck size={11} weight="bold" className="text-bg-elevated" />
            </div>
            <span className="text-[13px] font-medium text-text-primary">
              Cek risiko lowongan
            </span>
          </div>
          <VerifyBox />
          <SearchHistory />
        </motion.div>
      </section>

      {/* ── Cara kerja ───────────────────────────────────────────────── */}
      <section className="border-t border-border bg-bg-subtle/40 px-4 py-14 sm:px-6 lg:py-20">
        <div ref={howRef} className="mx-auto max-w-6xl scroll-mt-20">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.5 }}
            className="mb-8 text-center sm:mb-10"
          >
            <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">
              Job Risk Infrastructure
            </p>
            <h2 className="mt-2 text-[1.4rem] font-semibold tracking-tight text-text-primary sm:text-3xl">
              Cara Verifin menilai risiko
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">
              Ekstraksi, pemeriksaan publik, pemetaan relasi, dan reasoning dirangkai menjadi satu penilaian yang bisa kamu audit.
            </p>
          </motion.div>

          {/* Cards + connector mengalir */}
          <div className="flex flex-col gap-3 sm:gap-4 lg:flex-row lg:items-stretch lg:justify-between">
            {STEPS.map((step, i) => (
              <div key={step.num} className="flex flex-1 flex-col lg:flex-row lg:items-stretch">
                <div className="w-full lg:w-[220px] xl:w-[240px] flex-shrink-0">
                  <StepCard step={step} index={i} />
                </div>
                {i < STEPS.length - 1 && (
                  <div className="flex items-center justify-center">
                    <FlowConnector delay={i * 0.5} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
