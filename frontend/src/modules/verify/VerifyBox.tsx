"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  ImageSquare,
  X,
  Scan,
  MagnifyingGlass,
  Graph,
  Gauge,
  CheckCircle,
  CircleNotch,
  ArrowRight,
  ListChecks,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button, buttonClass } from "@/components/ui/Button";
import { cn, REPORT_STORAGE_KEY, addHistory, normalizeVerdict } from "@/lib/utils";
import { verifyImage, verifyText, verifyUrlStream } from "@/lib/api";
import type { SSEEvent } from "@/lib/api";
import type { NeedsInput, VerifyResponse } from "@/types/verify";

const URL_RE = /^(?:https?:\/\/)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:\/[^\s]*)?$/i;

function isPureUrl(s: string): boolean {
  const t = s.trim();
  // Murni 1 token & cocok pola domain → dianggap URL (bukan teks campuran)
  return !/\s/.test(t) && URL_RE.test(t);
}
function normalizeUrl(s: string): string {
  const t = s.trim();
  return /^https?:\/\//i.test(t) ? t : `https://${t}`;
}

type InputSource = "text" | "image" | "url";

function getSteps(source: InputSource) {
  const firstStep = source === "image"
    ? {
      id: "ocr",
      label: "Membaca poster",
      detail: "Teks di gambar dibaca, lalu nama perusahaan, nomor HP, email, link, dan alamat diambil",
    }
    : source === "url"
      ? {
        id: "fetch",
        label: "Membuka link",
        detail: "Isi postingan diambil, poster di dalamnya ikut dibaca, lalu data penting diambil",
      }
      : {
        id: "extract",
        label: "Membaca isi lowongan",
        detail: "Nama perusahaan, nomor HP, email, link, dan alamat diambil dari teks",
      };

  return [
    { ...firstStep, icon: Scan, duration: 350 },
    {
      id: "check",
      label: "Memeriksa isi",
      detail: "Lowongan atau bukan, berapa lowongan, dan cukup tidaknya informasi untuk diperiksa",
      icon: ListChecks,
      duration: 1500,
    },
    {
      id: "osint",
      label: "Cek ke sumber publik",
      detail: "Umur domain, reputasi nomor, alamat di peta, pencarian web, media sosial, artikel bantahan, dan Google Form bila ada",
      icon: MagnifyingGlass,
      duration: 5500,
    },
    {
      id: "graph",
      label: "Cocokkan kasus lama",
      detail: "Nomor, email, dan nama dicocokkan dengan lowongan yang pernah dicek atau dilaporkan",
      icon: Graph,
      duration: 1500,
    },
    {
      id: "ai",
      label: "Menyusun skor",
      detail: "Penilaian disusun dari bukti yang terkumpul, beserta pengaruh tiap bukti pada skor",
      icon: Gauge,
      duration: 3000,
    },
  ];
}

function formatElapsed(sec: number): string {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

function InterventionPanel({
  needs,
  onChoose,
  onEdit,
}: {
  needs: NeedsInput;
  onChoose: (choice: "segment" | "force", text?: string) => void;
  onEdit: () => void;
}) {
  const { issue } = needs;
  const segments = issue.segments ?? [];
  const editLabel = issue.kind === "too_short" ? "Tambah info" : "Ganti input";
  return (
    <div className="space-y-4" role="alert">
      <div className="flex items-start gap-3">
        <WarningCircle size={22} weight="fill" className="mt-0.5 shrink-0 text-waspada-fg" aria-hidden />
        <div>
          <h4 className="text-[15px] font-bold text-text-primary">{issue.title}</h4>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">{issue.message}</p>
        </div>
      </div>

      {segments.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {segments.map((seg) => (
            <li key={seg.id} className="flex flex-col justify-between gap-3 rounded-2xl border border-border bg-bg-elevated p-4">
              <div className="min-w-0">
                <p className="truncate text-[14px] font-semibold text-text-primary">{seg.employer}</p>
                {seg.position && <p className="truncate text-[12px] text-text-secondary">{seg.position}</p>}
                {seg.contacts.length > 0 && (
                  <p className="mt-1 break-words font-mono text-[12px] text-text-muted">{seg.contacts.join(" · ")}</p>
                )}
              </div>
              {seg.text ? (
                <button
                  type="button"
                  onClick={() => onChoose("segment", seg.text ?? undefined)}
                  className={buttonClass({ variant: "primary", size: "sm" })}
                >
                  Periksa yang ini
                </button>
              ) : (
                <p className="text-[12px] text-text-muted">Bagian ini tidak bisa dipisahkan otomatis. Tempel teksnya saja.</p>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        {issue.can_force && (
          <button
            type="button"
            onClick={() => onChoose("force")}
            className="min-h-11 text-left text-[13px] text-text-muted underline underline-offset-2 hover:text-text-primary"
          >
            {issue.kind === "multi_job" ? "Periksa semuanya sekaligus" : "Tetap periksa"}
            <span className="block text-[11px] no-underline">Hasilnya diberi catatan dan tidak masuk graf penipuan</span>
          </button>
        )}
        <button
          type="button"
          onClick={onEdit}
          className={buttonClass({ variant: segments.length > 0 ? "secondary" : "primary" })}
        >
          {editLabel}
        </button>
      </div>
    </div>
  );
}

function LoadingModal({
  stepIndex,
  dotCount,
  progress,
  steps,
  onCancel,
  stageMessage,
  realProgress,
  elapsed,
  needs,
  onChoose,
  onEdit,
}: {
  needs?: NeedsInput | null;
  onChoose: (choice: "segment" | "force", text?: string) => void;
  onEdit: () => void;
  stepIndex: number;
  dotCount: number;
  progress: number;
  steps: ReturnType<typeof getSteps>;
  onCancel?: () => void;
  stageMessage?: string;
  /** true hanya untuk URL (SSE): persentase berasal dari tahap yang dilaporkan server. */
  realProgress: boolean;
  elapsed: number;
}) {
  const reduceMotion = useReducedMotion();
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [onCancel]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/90 px-4 py-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="verify-loading-title"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.94, y: 12 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="max-h-[calc(100dvh-2rem)] w-full max-w-4xl overflow-y-auto rounded-3xl border border-border bg-bg-elevated shadow-2xl"
      >
        {/* Header */}
        <div className="border-b border-border bg-bg-subtle/40 px-6 py-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-text-primary text-bg-elevated shadow-md">
                {needs ? (
                  <WarningCircle size={20} weight="bold" />
                ) : (
                  <CircleNotch size={20} weight="bold" className="animate-spin motion-reduce:animate-none" />
                )}
              </div>
              <div className="min-w-0">
                <h3 id="verify-loading-title" className="text-base font-bold text-text-primary">
                  {needs ? "Memeriksa isi: perlu jawabanmu" : "Memeriksa lowongan"}
                </h3>
                <p className="text-[12px] text-text-muted">
                  {needs
                    ? "Pemeriksaan berhenti sebelum cek sumber publik, supaya hasilnya tidak menyesatkan"
                    : elapsed >= 75
                      ? "Masih berjalan. Sebagian sumber publik sedang lambat merespons."
                      : "Biasanya kurang dari satu menit"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 sm:text-right">
              {needs ? null : realProgress ? (
                <>
                  <div className="h-1.5 w-32 overflow-hidden rounded-full bg-bg-muted hidden sm:block">
                    <motion.div
                      className="h-full rounded-full bg-text-primary"
                      initial={{ width: "0%" }}
                      animate={{ width: `${progress}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                  </div>
                  <span className="font-mono text-xl font-bold text-text-primary">{progress}%</span>
                </>
              ) : (
                // Teks/gambar tidak punya progres dari server; waktu berjalan lebih jujur daripada persen tebakan.
                <span className="font-mono text-xl font-bold text-text-primary" aria-label={`Berjalan ${elapsed} detik`}>
                  {formatElapsed(elapsed)}
                </span>
              )}

              <button
                ref={cancelRef}
                type="button"
                onClick={onCancel}
                className={buttonClass({ variant: "dangerSoft", className: "ml-2" })}
              >
                <X size={14} weight="bold" />
                Batal
              </button>
            </div>
          </div>
        </div>

        {needs && (
          <div className="border-b border-border p-6">
            <InterventionPanel needs={needs} onChoose={onChoose} onEdit={onEdit} />
          </div>
        )}

        {/* Horizontal Step Flow with Animated Flow Connectors */}
        <div className={cn("p-6", needs && "hidden md:block opacity-60")}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5 md:gap-3">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const isDone = i < stepIndex;
              const isActive = i === stepIndex && !needs;
              const isWaiting = i === stepIndex && Boolean(needs);
              const isPending = i > stepIndex;
              const isLast = i === steps.length - 1;

              return (
                <div key={step.id} className="relative flex flex-col">
                  {/* Top Node & Horizontal Flow Connector */}
                  <div className="relative mb-3 flex items-center justify-center">
                    {/* Horizontal Flow Connector Line (Desktop/Tablet) */}
                    {!isLast && (
                      <div className="hidden md:block absolute left-1/2 w-full top-1/2 -translate-y-1/2 h-0.5 overflow-hidden bg-border z-0">
                        {/* Flowing Horizontal Beam Line */}
                        <motion.div
                          className={cn(
                            "h-full w-full origin-left transition-colors duration-500",
                            isDone
                              ? "bg-aman-fg"
                              : isActive
                                ? "bg-gradient-to-r from-text-primary via-text-primary/50 to-transparent"
                                : "bg-transparent"
                          )}
                          initial={{ scaleX: 0 }}
                          animate={{ scaleX: isDone ? 1 : isActive ? 0.7 : 0 }}
                          transition={{ duration: 0.5, ease: "easeInOut" }}
                        />
                        {/* Active Traveling Light Beam matching HomePage FlowConnector */}
                        {isActive && !reduceMotion && (
                          <motion.div
                            className="absolute inset-y-0 w-12 bg-gradient-to-r from-transparent via-text-primary/60 to-transparent"
                            animate={{ x: ["-48px", "180%"] }}
                            transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 0.4, ease: "easeInOut" }}
                          />
                        )}
                      </div>
                    )}

                    {/* Step Node Icon (Centered) */}
                    <div className="relative z-10">
                      {/* GPU-composited glowing halo replacement for CPU box-shadow */}
                      {isActive && !reduceMotion && (
                        <motion.div
                          className="absolute inset-0 rounded-2xl bg-text-primary/15"
                          animate={{ scale: [1, 1.25, 1], opacity: [0.6, 0, 0.6] }}
                          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                        />
                      )}
                      <motion.div
                        animate={
                          isActive && !reduceMotion
                            ? { scale: [1, 1.05, 1] }
                            : { scale: 1 }
                        }
                        transition={
                          isActive && !reduceMotion
                            ? { duration: 2, repeat: Infinity, ease: "easeInOut" }
                            : { duration: 0.2 }
                        }
                        className={cn(
                          "relative flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl transition-all duration-300 mx-auto",
                          isDone && "bg-aman-fg text-bg shadow-sm",
                          isActive && "bg-text-primary text-bg-elevated shadow-md ring-4 ring-text-primary/20",
                          isPending && "border border-border bg-bg-subtle text-text-muted opacity-70"
                        )}
                      >
                        {isDone ? (
                          <CheckCircle size={20} weight="fill" />
                        ) : isActive ? (
                          <Icon size={20} weight="bold" />
                        ) : (
                          <Icon size={18} weight="bold" />
                        )}
                      </motion.div>
                    </div>
                  </div>

                  {/* Horizontal Step Card Box */}
                  <motion.div
                    initial={false}
                    animate={
                      isActive
                        ? {
                          scale: 1.02,
                          borderColor: "var(--text-primary)",
                          backgroundColor: "var(--bg-subtle)",
                          opacity: 1,
                        }
                        : isDone
                          ? {
                            scale: 1,
                            borderColor: "var(--border)",
                            backgroundColor: "var(--bg-elevated)",
                            opacity: 1,
                          }
                          : {
                            scale: 1,
                            borderColor: "var(--border)",
                            backgroundColor: "var(--bg-elevated)",
                            opacity: 0.5,
                          }
                    }
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className={cn(
                      "relative flex-1 flex flex-col justify-between overflow-hidden rounded-2xl border p-4 transition-all",
                      isActive ? "border-text-primary/70 bg-bg-subtle shadow-sm" : "border-border bg-bg-elevated"
                    )}
                  >

                    <div>
                      <div className="flex items-center justify-between gap-1 mb-1.5">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                            isDone && "bg-aman-bg text-aman-fg border border-aman-border",
                            isActive && "bg-text-primary text-bg-elevated font-bold motion-safe:animate-pulse",
                            isPending && !isWaiting && "bg-bg-muted text-text-muted",
                            isWaiting && "bg-waspada-bg text-waspada-fg border border-waspada-border"
                          )}
                        >
                          {isDone ? "Selesai" : isActive ? "Proses..." : isWaiting ? "Perlu jawaban" : "Menunggu"}
                        </span>
                        <span className="font-mono text-[11px] text-text-muted">Langkah {i + 1}</span>
                      </div>

                      <h4
                        className={cn(
                          "text-[13px] font-bold leading-tight transition-colors",
                          isActive ? "text-text-primary" : isDone ? "text-text-primary" : "text-text-secondary"
                        )}
                      >
                        {step.label}
                        {isActive && <span className="ml-1 text-text-muted">{".".repeat(dotCount)}</span>}
                      </h4>

                      <p className="mt-1.5 text-[12px] leading-relaxed text-text-muted">
                        {step.detail}
                      </p>
                    </div>
                  </motion.div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer info */}
        <div className="border-t border-border bg-bg-subtle/30 px-6 py-3 text-center">
          <p className="text-[12px] font-medium text-text-muted flex items-center justify-center gap-1.5" aria-live="polite">
            <span className="h-1.5 w-1.5 rounded-full bg-aman-fg motion-safe:animate-pulse" aria-hidden />
            {needs
              ? "Pilih salah satu untuk melanjutkan, atau Batal."
              : stageMessage || "Jangan tutup halaman ini. Hasil muncul otomatis setelah selesai."}
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}

const noopSubscribe = () => () => {};

/** 0 = kosong, 1 = ada teks/gambar, 2 = sedang dianalisis. Dipakai hero "Tempel. Tunggu. Tahu." */
export type VerifyStage = 0 | 1 | 2;

/* ─── Main Component ────────────────────────────────────────────────────── */
export function VerifyBox({ onStageChange }: { onStageChange?: (stage: VerifyStage) => void } = {}) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // Gambar tambahan untuk satu lowongan yang sama (poster halaman 1–2).
  const [extraFiles, setExtraFiles] = useState<File[]>([]);
  const [askSinglePosting, setAskSinglePosting] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [dotCount, setDotCount] = useState(0);
  const [stageMessage, setStageMessage] = useState<string>("");
  const [elapsed, setElapsed] = useState(0);
  const [needs, setNeeds] = useState<NeedsInput | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isDoneRef = useRef(false);
  // true selama kartu intervensi tampil; dibaca di `finally` yang tidak melihat state terbaru.
  const pausedRef = useRef(false);
  // Label tombol pintas baru diketahui setelah mount (platform), supaya HTML server dan klien sama.
  const submitKey = useSyncExternalStore(
    noopSubscribe,
    () => (/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"),
    () => null,
  );
  const inputSource: InputSource = file
    ? "image"
    : isPureUrl(text)
      ? "url"
      : "text";
  const steps = getSteps(inputSource);

  const hasInput = Boolean(file) || text.trim().length > 0;
  useEffect(() => {
    onStageChange?.(loading ? 2 : hasInput ? 1 : 0);
  }, [loading, hasInput, onStageChange]);

  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview); };
  }, [preview]);

  useEffect(() => {
    if (!loading || needs) return;
    const startedAt = Date.now();
    const iv = setInterval(() => {
      setDotCount((d) => (d + 1) % 4);
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 380);

    // Timed step progression HANYA untuk non-SSE (teks & gambar) agar tidak loncat dengan event SSE
    let t1: NodeJS.Timeout | undefined;
    let t2: NodeJS.Timeout | undefined;
    let t3: NodeJS.Timeout | undefined;

    let t4: NodeJS.Timeout | undefined;
    if (inputSource !== "url") {
      // Gambar: OCR + pembacaan AI berjalan dulu (sekitar 15 dtk) sebelum isi bisa diperiksa.
      const offset = inputSource === "image" ? 12000 : 0;
      t1 = setTimeout(() => {
        setStepIndex((prev) => Math.max(prev, 1));
        setStageMessage("Memeriksa apakah ini lowongan dan berapa lowongan di dalamnya...");
      }, 4000 + offset);

      t4 = setTimeout(() => {
        setStepIndex((prev) => Math.max(prev, 2));
        setStageMessage("Mengecek nomor, domain, alamat, dan jejak di web...");
      }, 8000 + offset);

      t2 = setTimeout(() => {
        setStepIndex((prev) => Math.max(prev, 3));
        setStageMessage("Mencocokkan dengan laporan penipuan yang pernah masuk...");
      }, 28000 + offset);

      t3 = setTimeout(() => {
        setStepIndex((prev) => Math.max(prev, 4));
        setStageMessage("Menyusun penilaian dan alasannya...");
      }, 32000 + offset);
    }

    return () => {
      clearInterval(iv);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [loading, inputSource, needs]);

  // Stage mapping: SSE stage name → step index
  // fetch/ocr → 0, ner → 1 (atau 0 untuk text), osint → 2, graph → 3, ai → 4
  // Tapi steps array hanya 4: [extract/ocr, osint, graph, ai]
  // Map: fetch/ocr/ner → 0, osint → 1, graph → 2, ai → 3
  const _sseStageToStep = (stage: string): number => {
    const idx = steps.findIndex((s) => {
      if (stage === "fetch" || stage === "ocr" || stage === "ner") return s.id === "ocr" || s.id === "fetch" || s.id === "extract";
      if (stage === "check") return s.id === "check";
      if (stage === "osint") return s.id === "osint";
      if (stage === "graph") return s.id === "graph";
      if (stage === "ai") return s.id === "ai";
      return false;
    });
    return idx >= 0 ? idx : stepIndex;
  };

  // Simpan hasil verifikasi ke localStorage history
  const _saveToHistory = (result: VerifyResponse, inputLabel?: string) => {
    const verdict = normalizeVerdict(result.verdict);
    if (verdict === "ERROR") return; // tidak simpan jika error

    const companies = result.entities?.companies ?? [];
    const urls = result.entities?.urls ?? [];
    const contacts = result.entities?.contacts ?? [];

    const title = companies[0] || inputLabel || "Lowongan tidak dikenal";
    const entityParts: string[] = [];
    if (companies[0]) entityParts.push(companies[0]);
    if (urls[0]) entityParts.push(urls[0]);
    else if (contacts[0]) entityParts.push(contacts[0]);
    const entitiesSummary = entityParts.join(" • ") || "Tidak ada entitas";

    addHistory({
      id: result.case_id || `local-${Date.now()}`,
      case_id: result.case_id ?? null,
      title: title.slice(0, 120),
      verdict: verdict as "AMAN" | "WASPADA" | "BAHAYA",
      risk_score: result.risk_score,
      entitiesSummary,
    });
  };

  const _handleSSEEvent = (event: SSEEvent) => {
    switch (event.event) {
      case "start":
        setStepIndex(0);
        setStageMessage(event.data.message || "Memulai...");
        break;
      case "stage": {
        const { stage, message } = event.data;
        const idx = _sseStageToStep(stage);
        setStepIndex((prev) => Math.max(prev, idx));
        setStageMessage(message || "");
        break;
      }
      case "done": {
        isDoneRef.current = true;
        const result = event.data.response as VerifyResponse;
        _saveToHistory(result, "URL Lowongan");
        sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(result));
        router.push(result.case_id ? `/report/${result.case_id}` : "/report");
        break;
      }
      case "needs_input":
        if (event.data.needs_input) {
          pausedRef.current = true;
          setStepIndex(1);
          setNeeds(event.data.needs_input);
        }
        break;
      case "error":
        setError(event.data.message || "Analisis gagal. Coba lagi sebentar lagi. Kalau masih gagal, tempel ulang teksnya.");
        break;
    }
  };

  const attachFiles = useCallback((list: File[]) => {
    const accepted = list.filter(
      (f) =>
        ["image/jpeg", "image/jpg", "image/png", "image/webp"].includes(f.type) &&
        f.size <= 20 * 1024 * 1024,
    );
    if (list.length && !accepted.length) {
      setError("Format tidak didukung atau ukuran lebih dari 20 MB. Gunakan JPG, PNG, atau WEBP.");
      return;
    }
    const [first, ...rest] = accepted;
    if (!first) {
      setFile(null);
      setExtraFiles([]);
      setAskSinglePosting(false);
      setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
      return;
    }
    setError(null);
    setFile(first);
    setExtraFiles(rest.slice(0, 4));
    setAskSinglePosting(rest.length > 0);
    setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(first); });
  }, []);

  const attachFile = useCallback((f: File | null) => attachFiles(f ? [f] : []), [attachFiles]);

  const handlePaste = useCallback(async () => {
    try {
      if (navigator.clipboard.read) {
        const clipboardItems = await navigator.clipboard.read();
        for (const item of clipboardItems) {
          const imageType = item.types.find((type) => type.startsWith("image/"));
          if (imageType) {
            const blob = await item.getType(imageType);
            const ext = imageType.split("/")[1] || "png";
            const file = new File([blob], `pasted-image.${ext}`, { type: imageType });
            attachFile(file);
            return;
          }
        }
      }
    } catch {
      // Fallback ke readText jika permisi read() tidak diizinkan atau berisi teks
    }

    try {
      const clipboardText = await navigator.clipboard.readText();
      if (!clipboardText) return;
      setText((prev) => (prev ? `${prev}\n${clipboardText}` : clipboardText));
      if (textareaRef.current) {
        const el = textareaRef.current;
        setTimeout(() => {
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
          el.focus();
        }, 0);
      }
    } catch (err) {
      console.error("Gagal membaca clipboard:", err);
    }
  }, [attachFile]);

  const handleTextareaPaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items;
      if (items) {
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.startsWith("image/")) {
            const imageFile = items[i].getAsFile();
            if (imageFile) {
              e.preventDefault();
              attachFile(imageFile);
              return;
            }
          }
        }
      }
    },
    [attachFile]
  );

  // Stabil (tanpa dependensi) supaya effect di LoadingModal tidak memindah fokus tiap render.
  const handleCancel = useCallback(() => {
    // Batalkan request yang sedang berjalan (SSE untuk URL, fetch untuk teks/gambar)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    pausedRef.current = false;
    setLoading(false);
    setNeeds(null);
    setStepIndex(0);
    setStageMessage("");
  }, []);

  const handleEdit = useCallback(() => {
    pausedRef.current = false;
    setNeeds(null);
    setLoading(false);
    setStepIndex(0);
    setStageMessage("");
    setTimeout(() => textareaRef.current?.focus(), 0);
  }, []);

  /** Hasil akhir sudah ada: modal tetap terbuka sampai halaman laporan termuat. */
  function finish(result: VerifyResponse, inputLabel: string) {
    isDoneRef.current = true;
    setStepIndex(steps.length);
    _saveToHistory(result, inputLabel);
    sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(result));
    setTimeout(() => {
      router.push(result.case_id ? `/report/${result.case_id}` : "/report");
    }, 350);
  }

  /** Respons berhenti di tahap "Memeriksa isi": tampilkan kartu intervensi, jangan buka laporan. */
  function pauseFor(result: VerifyResponse): boolean {
    if (!result.needs_input) return false;
    pausedRef.current = true;
    setStepIndex(1);
    setNeeds(result.needs_input);
    return true;
  }

  async function handleChoice(choice: "segment" | "force", segmentText?: string) {
    if (!needs) return;
    const current = needs;
    pausedRef.current = false;
    setNeeds(null);
    setError(null);
    setStepIndex(2);
    setStageMessage("Mengecek nomor, domain, alamat, dan jejak di web...");
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const result = await verifyText(
        {
          text: (choice === "segment" && segmentText ? segmentText : current.text).slice(0, 10000),
          intervention: choice,
          intervention_kind: current.issue.kind,
          source: current.source,
          source_url: current.source_url,
        },
        controller.signal,
      );
      finish(result, (segmentText || current.text).slice(0, 80));
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError(err instanceof Error ? err.message : "Analisis gagal. Coba lagi sebentar lagi.");
        setLoading(false);
      }
    } finally {
      abortControllerRef.current = null;
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = text.trim();
    if (!trimmed && !file) {
      setError("Tempel teks lowongan atau lampirkan screenshot dulu.");
      return;
    }
    isDoneRef.current = false;
    pausedRef.current = false;
    setNeeds(null);
    setLoading(true);
    setStepIndex(0);
    setElapsed(0);
    setStageMessage("");

    // Buat AbortController untuk SSE stream (bisa di-cancel oleh tombol Batal)
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      if (file) {
        const images = extraFiles.length ? [file, ...extraFiles] : file;
        const result = await verifyImage(images, controller.signal, trimmed || undefined);
        if (!pauseFor(result)) finish(result, file.name);
      } else if (isPureUrl(trimmed)) {
        await verifyUrlStream(
          normalizeUrl(trimmed),
          (event) => { _handleSSEEvent(event); },
          controller.signal,
        );
        // Stream selesai tanpa event "done": koneksi putus di tengah jalan (mis. proxy memutus),
        // kecuali server berhenti untuk bertanya (event needs_input).
        if (!isDoneRef.current && !controller.signal.aborted && !pausedRef.current) {
          setError((prev) => prev ?? "Koneksi ke server terputus sebelum hasil keluar. Coba lagi; hasil yang sudah selesai akan muncul dari riwayat.");
        }
      } else {
        const result = await verifyText({ text: trimmed, include_raw_text: true }, controller.signal);
        if (!pauseFor(result)) finish(result, trimmed.slice(0, 80));
      }
    } catch (err) {
      if (isDoneRef.current) {
        return;
      }
      // AbortError = user klik Batal, jangan tampilkan error
      if (err instanceof DOMException && err.name === "AbortError") {
        // silent — sudah di-handle oleh handleCancel
      } else {
        const rawMsg = err instanceof Error ? err.message : "Analisis gagal. Coba lagi sebentar lagi. Kalau masih gagal, tempel ulang teksnya.";
        const displayMsg =
          rawMsg === "Failed to fetch" || rawMsg.includes("Failed to fetch")
            ? "Gagal terhubung ke server verifikasi. Periksa koneksi internetmu atau coba lagi sebentar lagi."
            : rawMsg;
        setError(displayMsg);
      }
    } finally {
      abortControllerRef.current = null;
      if (!isDoneRef.current && !pausedRef.current) {
        setLoading(false);
      }
    }
  }

  const progress = Math.min(100, Math.round((Math.min(stepIndex + 1, steps.length) / steps.length) * 100));

  return (
    <>
      {/* Loading modal popup */}
      <AnimatePresence>
        {loading && (
          <LoadingModal
            stepIndex={stepIndex}
            dotCount={dotCount}
            progress={progress}
            steps={steps}
            onCancel={handleCancel}
            stageMessage={stageMessage}
            realProgress={inputSource === "url"}
            elapsed={elapsed}
            needs={needs}
            onChoose={handleChoice}
            onEdit={handleEdit}
          />
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit} className="w-full space-y-3">
        {/* Input area */}
        <div
          className={cn(
            "relative rounded-xl border border-transparent bg-bg-elevated transition-colors duration-200 focus-within:border-border-focus",
            dragOver ? "ring-2 ring-text-primary" : "",
            loading && "pointer-events-none opacity-60",
          )}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            attachFiles(Array.from(e.dataTransfer.files));
          }}
        >
          {!file ? (
            <>
              <div className="relative">
                <textarea
                  ref={textareaRef}
                  value={text}
                  onPaste={handleTextareaPaste}
                  onKeyDown={(e) => {
                    // Enter tetap baris baru (teks lowongan biasanya banyak baris); Ctrl/⌘ + Enter mengirim.
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      e.currentTarget.form?.requestSubmit();
                    }
                  }}
                  aria-keyshortcuts="Control+Enter Meta+Enter"
                  onChange={(e) => {
                    setText(e.target.value);
                    if (error) setError(null);
                    // Auto-resize: grow sesuai isi, batasi maks 320px
                    const el = e.target;
                    el.style.height = "auto";
                    el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
                  }}
                  placeholder="Tempel teks lowongan, URL postingan, atau lampirkan screenshot..."
                  rows={5}
                  className="max-h-80 w-full resize-none overflow-y-auto rounded-xl bg-transparent p-4 text-[14px] leading-relaxed text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0"
                />
              </div>
              {/* Baris aksi di bawah textarea, tidak menimpa teks yang sudah diketik */}
              <div className="flex items-center justify-between gap-2 border-t border-border px-2 py-1.5">
                {!text.trim() ? (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex min-h-11 items-center gap-2 whitespace-nowrap rounded-md px-2.5 text-[13px] text-text-secondary transition-colors hover:bg-bg-subtle hover:text-text-primary"
                  >
                    <ImageSquare size={16} />
                    Lampirkan gambar
                  </button>
                ) : (
                  <span className="px-2.5 text-[12px] text-text-muted">
                    {text.trim().length} karakter
                    {submitKey && <span className="hidden sm:inline"> · {submitKey} + Enter untuk kirim</span>}
                  </span>
                )}
                <button
                  type="button"
                  onClick={handlePaste}
                  title="Tempel teks atau gambar dari clipboard"
                  className="flex min-h-11 items-center justify-center whitespace-nowrap rounded-md border border-border bg-bg-subtle/80 px-3.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-border-focus hover:bg-bg-subtle hover:text-text-primary active:scale-95 shadow-none outline-none ring-0"
                >
                  Tempel
                </button>
              </div>
              {!text.trim() && (
                <p className="border-t border-border px-4 py-2 text-[12px] text-text-muted">
                  Gambar: JPG, PNG, atau WEBP, maks 20 MB
                </p>
              )}
            </>
          ) : (
            <div className="space-y-2 p-4">
              <div className="flex items-start gap-3">
                {preview && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={preview} alt="preview" className="h-16 w-16 shrink-0 rounded-lg border border-border object-cover" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium text-text-primary">{file.name}</p>
                  <p className="mt-0.5 text-[12px] text-text-muted">
                    {(file.size / 1024).toFixed(0)} KB
                    {extraFiles.length > 0 && ` · +${extraFiles.length} gambar`}
                  </p>
                  {text.trim() && (
                    <p className="mt-1 text-[12px] text-aman-fg">
                      ✓ Disertai catatan teks tambahan ({text.trim().length} karakter)
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => attachFile(null)}
                  aria-label="Hapus gambar"
                  className="flex h-11 w-11 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bg-subtle hover:text-text-primary"
                >
                  <X size={14} />
                </button>
              </div>
              {askSinglePosting && (
                <div className="rounded-lg border border-border bg-bg-subtle px-3 py-2.5">
                  <p className="text-[13px] text-text-primary">
                    Apakah {extraFiles.length + 1} gambar ini satu lowongan?
                  </p>
                  <p className="mt-0.5 text-[12px] text-text-muted">
                    Contoh: poster halaman 1 dan 2. Satu pemeriksaan untuk satu lowongan.
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button type="button" size="sm" onClick={() => setAskSinglePosting(false)}>
                      Ya, satu lowongan
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setExtraFiles([]);
                        setAskSinglePosting(false);
                      }}
                    >
                      Bukan, pakai gambar pertama
                    </Button>
                  </div>
                </div>
              )}
              {!askSinglePosting && extraFiles.length > 0 && (
                <p className="text-[12px] text-text-muted">
                  {extraFiles.length + 1} gambar dibaca sebagai satu lowongan yang sama.
                </p>
              )}
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/webp"
          className="hidden"
          multiple
          onChange={(e) => {
            attachFiles(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />

        <Button
          type="submit"
          disabled={loading || (!text.trim() && !file)}
          fullWidth
          className="gap-2"
        >
          {loading ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Menganalisis...
            </>
          ) : (
            <>
              Verifikasi Sekarang
              <ArrowRight size={14} weight="bold" />
            </>
          )}
        </Button>

        <AnimatePresence>
          {error && (
            <motion.p
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="rounded-lg border border-bahaya-border bg-bahaya-bg px-4 py-3 text-[13px] text-bahaya-fg"
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>
      </form>
    </>
  );
}
