"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import {
  ImageSquare,
  X,
  Scan,
  MagnifyingGlass,
  Graph,
  Cpu,
  CheckCircle,
  ArrowRight,
  ClipboardText,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { cn, REPORT_STORAGE_KEY } from "@/lib/utils";
import { verifyImage, verifyText, verifyUrl } from "@/lib/api";
import type { VerifyResponse } from "@/types/verify";

/* ─── URL detection ─────────────────────────────────────────────────────── */
// Cocokkan URL dengan/tanpa skema: bit.ly/x, www.foo.com/a, https://foo.com/a
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
        label: "OCR + Ekstraksi Entitas",
        detail: "PaddleOCR membaca gambar untuk mengekstrak nama perusahaan, HP, email, URL, dan alamat",
      }
    : source === "url"
    ? {
        id: "fetch",
        label: "Ambil Konten + Ekstraksi Entitas",
        detail: "Konten link diambil; OCR berjalan bila ditemukan gambar poster, lalu entitas diekstrak",
      }
    : {
        id: "extract",
        label: "Ekstraksi Entitas",
        detail: "Teks diproses langsung untuk mengekstrak nama perusahaan, HP, email, URL, dan alamat",
      };

  return [
    { ...firstStep, icon: Scan, duration: 1400 },
    {
      id: "osint",
      label: "Pemeriksaan OSINT",
      detail: "WHOIS/DNS, reputasi nomor, OSM, web evidence, media sosial, dan inspeksi Google Forms bila relevan",
      icon: MagnifyingGlass,
      duration: 3200,
    },
    {
      id: "graph",
      label: "Pemetaan Relasi Entitas",
      detail: "Membangun graf koneksi antar entitas yang ditemukan dari sumber publik",
      icon: Graph,
      duration: 1800,
    },
    {
      id: "ai",
      label: "Reasoning + Penjelasan Bukti",
      detail: "Verifin AI menyusun penilaian dari fakta OSINT dan menghitung kontribusi sinyal risiko",
      icon: Cpu,
      duration: 2500,
    },
  ];
}

/* ─── Loading Modal Popup (Horizontal Stepper) ─────────────────────────────── */
function LoadingModal({
  stepIndex,
  dotCount,
  progress,
  steps,
}: {
  stepIndex: number;
  dotCount: number;
  progress: number;
  steps: ReturnType<typeof getSteps>;
}) {
  const currentStep = steps[stepIndex];
  const StepIcon = currentStep?.icon ?? Scan;

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 px-4 backdrop-blur-md"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.94, y: 12 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-4xl overflow-hidden rounded-3xl border border-border bg-bg-elevated shadow-2xl"
      >
        {/* Header */}
        <div className="border-b border-border bg-bg-subtle/40 px-6 py-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-text-primary text-bg-elevated shadow-md">
                <StepIcon size={20} weight="bold" />
                <span className="absolute -inset-1 animate-ping rounded-2xl bg-text-primary opacity-20" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-bold text-text-primary flex items-center gap-2">
                  Proses Verifikasi AI
                  <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                </h3>
                <p className="text-[12px] text-text-muted">
                  Analisis data & bukti OSINT paralel
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 sm:text-right">
              <div className="h-1.5 w-32 overflow-hidden rounded-full bg-bg-muted hidden sm:block">
                <motion.div
                  className="h-full rounded-full bg-text-primary"
                  initial={{ width: "0%" }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
              <span className="font-mono text-xl font-bold text-text-primary">{progress}%</span>
            </div>
          </div>
        </div>

        {/* Horizontal Step Flow with Animated Flow Connectors */}
        <div className="p-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4 md:gap-3">
            {steps.map((step, i) => {
              const Icon = step.icon;
              const isDone = i < stepIndex;
              const isActive = i === stepIndex;
              const isPending = i > stepIndex;
              const isLast = i === steps.length - 1;

              return (
                <div key={step.id} className="relative flex flex-col">
                  {/* Top Node & Horizontal Flow Connector */}
                  <div className="relative mb-3 flex items-center">
                    {/* Step Node Icon */}
                    <div className="relative z-10">
                      <motion.div
                        animate={
                          isActive
                            ? {
                                scale: [1, 1.12, 1],
                                boxShadow: [
                                  "0 0 0px rgba(0,0,0,0)",
                                  "0 0 16px rgba(59,130,246,0.35)",
                                  "0 0 0px rgba(0,0,0,0)",
                                ],
                              }
                            : { scale: 1 }
                        }
                        transition={
                          isActive
                            ? { duration: 2, repeat: Infinity, ease: "easeInOut" }
                            : { duration: 0.2 }
                        }
                        className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl transition-all duration-300",
                          isDone && "bg-aman-fg text-white shadow-sm",
                          isActive && "bg-text-primary text-bg-elevated shadow-lg ring-4 ring-text-primary/20",
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

                    {/* Horizontal Flow Connector Line (Desktop/Tablet) */}
                    {!isLast && (
                      <div className="hidden md:block absolute left-10 right-0 top-1/2 -translate-y-1/2 h-0.5 overflow-hidden bg-bg-muted z-0">
                        {/* Flowing Horizontal Beam Line */}
                        <motion.div
                          className={cn(
                            "h-full w-full origin-left transition-colors duration-500",
                            isDone
                              ? "bg-aman-fg"
                              : isActive
                              ? "bg-gradient-to-r from-text-primary via-amber-500 to-bg-muted"
                              : "bg-transparent"
                          )}
                          initial={{ scaleX: 0 }}
                          animate={{ scaleX: isDone ? 1 : isActive ? 0.7 : 0 }}
                          transition={{ duration: 0.5, ease: "easeInOut" }}
                        />
                        {/* Active Traveling Pulse Light Beam */}
                        {isActive && (
                          <motion.div
                            className="absolute top-0 bottom-0 w-6 bg-white shadow-[0_0_8px_#fff]"
                            animate={{ x: ["-100%", "250%"], opacity: [0, 1, 0] }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                          />
                        )}
                      </div>
                    )}
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
                          }
                        : isDone
                        ? {
                            scale: 1,
                            borderColor: "var(--border)",
                            opacity: 0.85,
                          }
                        : {
                            scale: 1,
                            borderColor: "var(--border)",
                            opacity: 0.5,
                          }
                    }
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className={cn(
                      "relative flex-1 flex flex-col justify-between overflow-hidden rounded-2xl border p-4 transition-shadow",
                      isActive && "shadow-md border-text-primary/80 ring-1 ring-text-primary/20",
                      !isActive && "bg-bg-elevated"
                    )}
                  >
                    {/* Active Step Top Glowing Line Accent */}
                    {isActive && (
                      <motion.div
                        layoutId="activeGlowHorizontal"
                        className="absolute left-0 right-0 top-0 h-1 bg-text-primary"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                      />
                    )}

                    <div>
                      <div className="flex items-center justify-between gap-1 mb-1.5">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                            isDone && "bg-aman-bg text-aman-fg border border-aman-border",
                            isActive && "bg-text-primary text-bg-elevated font-bold animate-pulse",
                            isPending && "bg-bg-muted text-text-muted"
                          )}
                        >
                          {isDone ? "Selesai" : isActive ? "Proses..." : "Menunggu"}
                        </span>
                        <span className="font-mono text-[10px] text-text-muted">Step {i + 1}</span>
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

                      <p className="mt-1.5 text-[11px] leading-relaxed text-text-muted">
                        {step.detail}
                      </p>
                    </div>

                    {/* Active Real-Time Live Pulse */}
                    {isActive && (
                      <div className="mt-3 flex items-center gap-1.5 pt-2 border-t border-border/50">
                        <div className="relative flex h-2 w-2 shrink-0">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-text-primary opacity-75" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-text-primary" />
                        </div>
                        <span className="text-[10px] font-semibold text-text-primary truncate">
                          Aktif real-time...
                        </span>
                      </div>
                    )}
                  </motion.div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer info */}
        <div className="border-t border-border bg-bg-subtle/30 px-6 py-3 text-center">
          <p className="text-[11px] font-medium text-text-muted flex items-center justify-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
            Harap tunggu, Verifin AI sedang memverifikasi bukti OSINT secara mendalam...
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ─── Main Component ────────────────────────────────────────────────────── */
export function VerifyBox() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [dotCount, setDotCount] = useState(0);
  const inputSource: InputSource = file
    ? "image"
    : isPureUrl(text)
    ? "url"
    : "text";
  const steps = getSteps(inputSource);

  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview); };
  }, [preview]);

  useEffect(() => {
    if (!loading) return;
    const iv = setInterval(() => setDotCount((d) => (d + 1) % 4), 380);
    return () => clearInterval(iv);
  }, [loading]);

  useEffect(() => {
    if (!loading) {
      const t = setTimeout(() => setStepIndex(0), 0);
      return () => clearTimeout(t);
    }
    if (stepIndex >= steps.length - 1) return;
    const timer = setTimeout(
      () => setStepIndex((s) => Math.min(s + 1, steps.length - 1)),
      steps[stepIndex]?.duration ?? 2000,
    );
    return () => clearTimeout(timer);
  }, [loading, stepIndex, steps]);

  const attachFile = useCallback((f: File | null) => {
    if (!f) {
      setFile(null);
      setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
      return;
    }
    if (!["image/jpeg", "image/jpg", "image/png", "image/webp"].includes(f.type)) {
      setError("Format tidak didukung. Gunakan JPG, PNG, atau WEBP.");
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setError("Ukuran file maksimal 20 MB.");
      return;
    }
    setError(null);
    setFile(f);
    setPreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(f); });
  }, []);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = text.trim();
    if (!trimmed && !file) {
      setError("Tempel teks lowongan atau lampirkan screenshot terlebih dahulu.");
      return;
    }
    setLoading(true);
    setStepIndex(0);
    try {
      let result: VerifyResponse;
      if (file) {
        result = await verifyImage(file);
      } else if (isPureUrl(trimmed)) {
        result = await verifyUrl(normalizeUrl(trimmed));
      } else {
        result = await verifyText({ text: trimmed, include_raw_text: true });
      }
      sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(result));
       router.push(result.case_id ? `/report/${result.case_id}` : "/report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan saat memproses.");
    } finally {
      setLoading(false);
    }
  }

  const progress = Math.round(((stepIndex + 1) / steps.length) * 100);

  return (
    <>
      {/* Loading modal popup */}
      <AnimatePresence>
        {loading && (
          <LoadingModal stepIndex={stepIndex} dotCount={dotCount} progress={progress} steps={steps} />
        )}
      </AnimatePresence>

      <form onSubmit={handleSubmit} className="w-full space-y-3">
        {/* Input area */}
        <div
          className={cn(
            "relative rounded-xl bg-bg-elevated transition-all duration-200",
            dragOver ? "ring-2 ring-text-primary" : "",
            loading && "pointer-events-none opacity-60",
          )}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); attachFile(e.dataTransfer.files[0] ?? null); }}
        >
          {!file ? (
            <>
              <div className="relative">
                <textarea
                  ref={textareaRef}
                  value={text}
                  onPaste={handleTextareaPaste}
                  onChange={(e) => {
                    setText(e.target.value);
                    // Auto-resize: grow sesuai isi, batasi maks 320px
                    const el = e.target;
                    el.style.height = "auto";
                    el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
                  }}
                  placeholder="Tempel teks lowongan, URL postingan, atau lampirkan screenshot..."
                  rows={5}
                  className="max-h-80 w-full resize-none overflow-y-auto rounded-xl bg-transparent p-4 pb-10 text-[14px] leading-relaxed text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0"
                />
                <button
                  type="button"
                  onClick={handlePaste}
                  title="Tempel teks atau gambar dari clipboard (Paste)"
                  className="absolute right-3 bottom-3 z-10 flex items-center justify-center rounded-md border border-border bg-bg-subtle/80 px-2.5 py-1 text-[11px] font-medium text-text-muted transition-all hover:border-border-focus hover:bg-bg-subtle hover:text-text-primary active:scale-95 shadow-sm"
                >
                  Paste
                </button>
              </div>
              {!text.trim() && (
                <div className="flex items-center justify-between border-t border-border px-3 py-2.5">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] text-text-muted transition-colors hover:bg-bg-subtle hover:text-text-secondary"
                  >
                    <ImageSquare size={14} />
                    Lampirkan gambar
                  </button>
                  <span className="text-[11px] text-text-muted">JPG · PNG · WEBP · maks 20 MB</span>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-start gap-3 p-4">
              {preview && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview} alt="preview" className="h-16 w-16 shrink-0 rounded-lg border border-border object-cover" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-medium text-text-primary">{file.name}</p>
                <p className="mt-0.5 text-[12px] text-text-muted">{(file.size / 1024).toFixed(0)} KB</p>
              </div>
              <button
                type="button"
                onClick={() => attachFile(null)}
                className="rounded-md p-1 text-text-muted transition-colors hover:bg-bg-subtle hover:text-text-primary"
              >
                <X size={14} />
              </button>
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/webp"
          className="hidden"
          onChange={(e) => attachFile(e.target.files?.[0] ?? null)}
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
