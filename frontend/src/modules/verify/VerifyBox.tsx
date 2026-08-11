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

/* ─── Loading Modal Popup ────────────────────────────────────────────────── */
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 px-4 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 8 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md overflow-hidden rounded-2xl border border-border bg-bg-elevated shadow-2xl"
      >
        {/* Header aktif */}
        <div className="border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-text-primary">
              <StepIcon size={16} weight="bold" className="text-bg-elevated" />
              <span className="absolute inset-0 animate-ping rounded-xl bg-text-primary opacity-20" />
            </div>
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-text-primary">
                {currentStep?.label}
                <span className="font-normal text-text-muted">{".".repeat(dotCount)}</span>
              </p>
              <p className="mt-0.5 text-[12px] text-text-muted">{currentStep?.detail}</p>
            </div>
          </div>
        </div>

        {/* Step list */}
        <div className="divide-y divide-border">
          {steps.map((step, i) => {
            const Icon = step.icon;
            const done = i < stepIndex;
            const active = i === stepIndex;
            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center gap-3 px-5 py-3 transition-colors",
                  active && "bg-bg-subtle",
                  done && "opacity-40",
                )}
              >
                <div
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-md",
                    done && "bg-aman-fg",
                    active && "bg-text-primary",
                    !done && !active && "bg-bg-muted",
                  )}
                >
                  {done ? (
                    <CheckCircle size={11} weight="bold" className="text-white" />
                  ) : (
                    <Icon size={11} weight="bold" className={active ? "text-white" : "text-text-muted"} />
                  )}
                </div>
                <span
                  className={cn(
                    "flex-1 text-[13px]",
                    active ? "font-medium text-text-primary" : "text-text-secondary",
                    done && "text-text-muted",
                  )}
                >
                  {step.label}
                </span>
                {active && (
                  <span className="flex gap-1">
                    {[0, 1, 2].map((j) => (
                      <span
                        key={j}
                        className="h-1 w-1 rounded-full bg-text-primary"
                        style={{ animation: `stepPulse 1.2s ease-in-out ${j * 0.2}s infinite` }}
                      />
                    ))}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div className="px-5 pb-5 pt-4">
          <div className="h-1 w-full overflow-hidden rounded-full bg-bg-muted">
            <motion.div
              className="h-full rounded-full bg-text-primary"
              initial={{ width: "0%" }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-text-muted">
            <span>Verifin AI sedang menganalisis...</span>
            <span className="font-mono">{progress}%</span>
          </div>
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
