"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { VerifyBox, type VerifyStage } from "@/modules/verify/VerifyBox";
import { SearchHistory } from "@/modules/home/SearchHistory";
import {
  Scan,
  MagnifyingGlass,
  Graph,
  Gauge,
  ArrowUpRight,
  ArrowDown,
  ShieldCheck,
  Check,
  CircleNotch,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { buttonClass } from "@/components/ui/Button";

// Contoh di tiap langkah diambil dari laporan nyata T4 (lowongan palsu atas nama Pos Indonesia,
// dibantah Pos Indonesia), run 8 di server produksi 20 Okt 2026.
const EXAMPLE_REPORT = "/report/1ec34af5-1ab1-414b-89f1-7dd98b04440e";

const STEPS = [
  {
    num: "01",
    icon: Scan,
    title: "Membaca isi lowongan",
    desc: "Dari teks, poster, atau link, Verifin mengambil nama perusahaan, nomor HP, email, tautan, alamat, dan gaji yang tertulis.",
    tags: ["PaddleOCR", "Hybrid NER"],
  },
  {
    num: "02",
    icon: MagnifyingGlass,
    title: "Cek ke sumber publik",
    desc: "Tujuh pemeriksaan berjalan bersamaan: umur domain, reputasi nomor, alamat di peta, pencarian web, media sosial, artikel bantahan atas nama perusahaan, dan isi Google Form bila ada.",
    tags: ["WHOIS/DNS", "Kaspersky Who Calls", "OpenStreetMap", "SearXNG"],
  },
  {
    num: "03",
    icon: Graph,
    title: "Cocokkan dengan kasus lama",
    desc: "Nomor, email, dan nama yang sama dicocokkan dengan lowongan yang pernah dicek atau dilaporkan sebagai penipuan.",
    tags: ["NetworkX", "Case Memory"],
  },
  {
    num: "04",
    icon: Gauge,
    title: "Skor dan alasannya",
    desc: "AI memberi hasil AMAN, WASPADA, atau BAHAYA dari bukti yang terkumpul, lalu menunjukkan seberapa besar tiap bukti memengaruhi skor.",
    tags: ["LLM Reasoning", "Explainable AI"],
  },
] as const;

const EXAMPLE_BARS = [
  { label: "Penyesuaian penalaran AI", value: 26, ai: true },
  { label: "Daftar hanya via WhatsApp/tautan bio", value: 20, ai: false },
  { label: "Nama BUMN, daftar lewat WhatsApp", value: 15, ai: false },
];

function StepExample({ index }: { index: number }) {
  if (index === 0) {
    return (
      <>
        <div className="flex flex-wrap gap-1.5">
          {["PT Pos Indonesia (Persero)", "Daftar via WhatsApp admin", "Tautan di bio"].map((item) => (
            <span key={item} className="rounded-md border border-border bg-bg-elevated px-2 py-0.5 text-text-primary">
              {item}
            </span>
          ))}
        </div>
        <p className="mt-2 text-text-muted">Tanpa email, situs, atau alamat kantor.</p>
      </>
    );
  }
  if (index === 1) {
    return (
      <>
        <p className="font-medium text-text-primary">[HOAKS] Tautan Lowongan Kerja Pos Indonesia</p>
        <p className="mt-0.5 text-text-muted">komdigi.go.id · 1 dari 5 artikel bantahan atas nama ini</p>
      </>
    );
  }
  if (index === 2) {
    return <p className="text-text-primary">Nama ini belum pernah muncul di kasus lain yang tersimpan di Verifin.</p>;
  }
  return (
    <>
      <span className="inline-flex rounded-md border border-waspada-border bg-waspada-bg px-2 py-0.5 font-semibold text-waspada-fg">
        WASPADA 73
      </span>
      <ul className="mt-2.5 space-y-2">
        {EXAMPLE_BARS.map((bar) => (
          <li key={bar.label}>
            <div className="flex justify-between gap-2">
              <span className={cn("min-w-0", bar.ai ? "italic text-text-muted" : "text-text-primary")}>{bar.label}</span>
              <span className={cn("font-mono", bar.ai ? "text-text-muted" : "text-bahaya-fg")}>+{bar.value}</span>
            </div>
            <span className="mt-1 block h-1 rounded-full bg-border">
              <span
                className={cn("block h-full rounded-full", bar.ai ? "bg-text-muted" : "bg-bahaya-fg")}
                style={{ width: `${(bar.value / 26) * 100}%` }}
              />
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

const EXAMPLE_LABELS = ["Yang terbaca", "Yang ditemukan", "Hasil pencocokan", "Skor akhir"];

/* Langkah menyala bergiliran 01 → 04 seperti pemeriksaan yang sedang berjalan.
   Hanya jalan saat section terlihat dan tab aktif; berhenti saat kursor di atas kartu.
   Gerakan cuma transform dan warna. Untuk "kurangi gerakan" giliran tetap jalan,
   tapi isian garis dan putaran ikon dimatikan lewat motion-reduce. */
function HowItWorks() {
  const listRef = useRef<HTMLOListElement>(null);
  const [active, setActive] = useState(0);
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || paused) return;
    const iv = setInterval(() => {
      if (!document.hidden) setActive((a) => (a + 1) % STEPS.length);
    }, 2600);
    return () => clearInterval(iv);
  }, [visible, paused]);

  return (
    <ol
      ref={listRef}
      className="grid grid-cols-1 lg:grid-cols-4 lg:gap-4"
      onMouseLeave={() => setPaused(false)}
    >
      {STEPS.map((step, i) => {
        const Icon = step.icon;
        const done = i < active;
        const current = i === active;
        const isLast = i === STEPS.length - 1;
        return (
          <li
            key={step.num}
            className="relative flex gap-3 pb-4 last:pb-0 lg:flex-col lg:items-center lg:gap-4 lg:pb-0"
            aria-current={current ? "step" : undefined}
            onMouseEnter={() => {
              setActive(i);
              setPaused(true);
            }}
          >
            {!isLast && (
              // HP: garis tegak ke langkah berikutnya; lg: garis mendatar di atas kartu.
              <span
                aria-hidden
                className="absolute bottom-0 left-[17px] top-10 w-px overflow-hidden bg-border lg:bottom-auto lg:left-[calc(50%+28px)] lg:right-[calc(-50%+12px)] lg:top-[17px] lg:h-px lg:w-auto"
              >
                <span
                  className={cn(
                    "block h-full w-full origin-top bg-text-primary transition-transform duration-700 ease-out motion-reduce:transition-none lg:origin-left",
                    done ? "scale-100" : "scale-y-0 lg:scale-x-0 lg:scale-y-100",
                  )}
                />
              </span>
            )}
            <span
              aria-hidden
              className={cn(
                "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border font-mono text-[12px] font-semibold transition-colors duration-300",
                done && "border-text-primary bg-text-primary text-bg-elevated",
                current && "border-text-primary bg-bg-elevated text-text-primary ring-4 ring-text-primary/10",
                !done && !current && "border-border bg-bg text-text-muted",
              )}
            >
              {done ? (
                <Check size={14} weight="bold" />
              ) : current ? (
                <CircleNotch size={15} weight="bold" className="animate-spin motion-reduce:animate-none" />
              ) : (
                step.num
              )}
            </span>
            <div
              className={cn(
                "flex min-w-0 flex-1 flex-col self-stretch rounded-2xl border bg-bg-elevated p-5 transition-colors duration-300",
                current ? "border-text-primary/50" : "border-border",
              )}
            >
              <h3 className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
                <Icon
                  size={16}
                  weight="bold"
                  aria-hidden
                  className={cn("shrink-0 transition-colors duration-300", current ? "text-text-primary" : "text-text-muted")}
                />
                {step.title}
              </h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{step.desc}</p>
              <div
                className={cn(
                  "mt-4 rounded-xl border p-3 text-[12px] leading-relaxed transition-colors duration-300",
                  current ? "border-text-primary/25 bg-bg-subtle" : "border-border bg-bg-subtle/40",
                )}
              >
                <p className="mb-1.5 text-[11px] font-medium text-text-muted">{EXAMPLE_LABELS[i]}</p>
                <StepExample index={i} />
              </div>
              <div className="mt-auto flex flex-wrap gap-1 pt-3">
                {step.tags.map((tag) => (
                  <span key={tag} className="rounded border border-border bg-bg-subtle px-1.5 py-0.5 font-mono text-[11px] text-text-muted">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* Slogan "Tempel. Tunggu. Tahu." (sama dengan video) sebagai jalur langkah yang
   mengikuti keadaan kotak input: langkah aktif menyala, yang selesai diberi centang. */
const SLOGAN = [
  { word: "Tempel.", desc: "Teks, poster, atau link lowongan" },
  { word: "Tunggu.", desc: "Verifin mengecek ke sumber publik" },
  { word: "Tahu.", desc: "Skor risiko dan alasannya" },
] as const;

const VERDICT_CHIPS = [
  { label: "AMAN", cls: "border-aman-border bg-aman-bg text-aman-fg" },
  { label: "WASPADA", cls: "border-waspada-border bg-waspada-bg text-waspada-fg" },
  { label: "BAHAYA", cls: "border-bahaya-border bg-bahaya-bg text-bahaya-fg" },
];

function SloganSteps({ stage }: { stage: VerifyStage }) {
  // Saat input kosong, sorotan berjalan 01 → 02 → 03 sebagai contoh alur.
  // Cukup satu interval ringan; berhenti saat pengguna mulai mengisi. Untuk "kurangi gerakan"
  // siklus tetap jalan tapi hanya berganti warna: isian garis dan putaran ikon dimatikan lewat motion-reduce.
  const [demo, setDemo] = useState(0);
  useEffect(() => {
    if (stage !== 0) return;
    const iv = setInterval(() => {
      if (!document.hidden) setDemo((d) => (d + 1) % SLOGAN.length);
    }, 1800);
    return () => clearInterval(iv);
  }, [stage]);

  // stage 0: contoh berjalan; 1: langkah 1 selesai, 2 aktif; 2: langkah 2 berjalan
  const current = stage === 0 ? demo : 1;
  return (
    <ol className="mt-5 grid grid-cols-3 gap-2 sm:mt-9 sm:block" aria-label="Cara pakai Verifin">
      {SLOGAN.map((step, i) => {
        const done = i < current;
        const active = i === current;
        const running = active && stage === 2;
        const isLast = i === SLOGAN.length - 1;
        return (
          <li key={step.word} className="relative flex flex-col gap-2 sm:flex-row sm:gap-5 sm:pb-6 sm:last:pb-0" aria-current={active ? "step" : undefined}>
            {!isLast && (
              // HP: garis mendatar ke langkah berikutnya; sm ke atas: garis tegak.
              // Isian garis bergerak lewat transform saja supaya ringan.
              <span
                aria-hidden
                className="absolute left-10 right-0 top-4 h-px overflow-hidden bg-border sm:left-[17px] sm:right-auto sm:top-10 sm:bottom-1 sm:h-auto sm:w-px"
              >
                <span
                  className={cn(
                    "block h-full w-full origin-left bg-text-primary transition-transform duration-700 ease-out sm:origin-top motion-reduce:transition-none",
                    done ? "scale-100" : "scale-x-0 sm:scale-x-100 sm:scale-y-0",
                  )}
                />
              </span>
            )}
            <span
              aria-hidden
              className={cn(
                "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border font-mono text-[12px] font-semibold transition-colors duration-300 sm:h-9 sm:w-9",
                done && "border-text-primary bg-text-primary text-bg-elevated",
                active && "border-text-primary bg-bg-elevated text-text-primary ring-4 ring-text-primary/10",
                !done && !active && "border-border bg-bg text-text-muted",
              )}
            >
              {done ? (
                <Check size={14} weight="bold" />
              ) : running ? (
                <CircleNotch size={15} weight="bold" className="animate-spin motion-reduce:animate-none" />
              ) : (
                `0${i + 1}`
              )}
            </span>
            <div className="min-w-0 sm:pt-0.5">
              <p
                className={cn(
                  "text-[17px] font-semibold leading-tight tracking-tight transition-colors duration-300 sm:text-2xl",
                  done || active ? "text-text-primary" : "text-text-muted",
                )}
              >
                {step.word}
              </p>
              <p className="mt-1 hidden text-[15px] text-text-secondary sm:block">
                {running ? "Sedang mengecek, biasanya sekitar satu menit" : step.desc}
              </p>
              {isLast && (
                <div
                  className={cn(
                    "mt-2.5 hidden flex-wrap gap-1.5 transition-opacity duration-500 sm:flex",
                    active ? "opacity-100" : "opacity-60",
                  )}
                >
                  {VERDICT_CHIPS.map((c) => (
                    <span key={c.label} className={cn("rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-bold", c.cls)}>
                      {c.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function HomePage() {
  const howRef = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState<VerifyStage>(0);
  const handleStage = useCallback((next: VerifyStage) => setStage(next), []);

  return (
    <div className="flex flex-1 flex-col">

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="mx-auto flex w-full max-w-6xl flex-col items-center gap-7 px-4 py-8 sm:px-6 sm:py-14 lg:flex-row lg:items-start lg:gap-16 lg:py-20">

        {/* Kiri — headline */}
        <div className="w-full flex-1">

          {/* Hero tanpa opacity awal: HTML server langsung terbaca walau JS belum termuat */}
          <motion.h1
            initial={{ y: 12 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.5, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
            className="text-[2rem] font-semibold leading-[1.15] tracking-tight text-text-primary sm:text-5xl lg:text-6xl"
          >
            Tahu sebelum<br />kamu melamar.
          </motion.h1>

          <motion.p
            initial={{ y: 8 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.5, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
            className="mt-3 max-w-lg text-[15px] leading-relaxed text-text-secondary sm:mt-5"
          >
            Verifin memeriksa nomor, perusahaan, alamat, dan email di lowongan lewat sumber publik, lalu menjelaskan alasan di balik skornya. Hasilnya penilaian risiko, bukan jaminan legalitas.
          </motion.p>

          <SloganSteps stage={stage} />

          {/* Charcoal seperti "Lapor komunitas", sama dengan "Lihat laporan lengkapnya" (keputusan user). */}
          <button
            type="button"
            onClick={() => howRef.current?.scrollIntoView({ behavior: "smooth" })}
            className={buttonClass({ variant: "primary", className: "mt-10 hidden lg:inline-flex" })}
          >
            <ArrowDown size={14} weight="bold" />
            Lihat cara kerja
          </button>
        </div>

        {/* Kanan — VerifyBox */}
        <motion.div
          initial={{ y: 12 }}
          animate={{ y: 0 }}
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
          <VerifyBox onStageChange={handleStage} />
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
            <h2 className="text-[1.4rem] font-semibold tracking-tight text-text-primary sm:text-3xl">
              Cara Verifin menilai risiko
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">
              Empat langkah yang dijalankan untuk setiap lowongan. Contoh di tiap langkah diambil dari laporan
              nyata: lowongan palsu yang mencatut nama Pos Indonesia.
            </p>
            <Link
              href={EXAMPLE_REPORT}
              className={buttonClass({ variant: "primary", className: "mt-4" })}
            >
              Lihat laporan lengkapnya
              <ArrowUpRight size={14} weight="bold" />
            </Link>
          </motion.div>

          <HowItWorks />

        </div>
      </section>

    </div>
  );
}
