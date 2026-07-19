"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ImageSquare,
  SpinnerGap,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { cn, REPORT_STORAGE_KEY } from "@/lib/utils";
import { verifyImage, verifyText, verifyUrl } from "@/lib/api";
import type { VerifyResponse } from "@/types/verify";

const STEPS = [
  "Membaca input",
  "Mengekstrak entitas",
  "Menjalankan OSINT",
  "Menganalisis risiko",
];

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

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const attachFile = useCallback((f: File | null) => {
    if (!f) {
      setFile(null);
      setPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      return;
    }
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/webp"];
    if (!allowed.includes(f.type)) {
      setError("Format tidak didukung. Gunakan JPG, PNG, atau WEBP.");
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setError("Ukuran file maksimal 20MB.");
      return;
    }
    setError(null);
    setFile(f);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (loading) return;

    if (!trimmed && !file) {
      setError("Isi teks/link lowongan atau lampirkan gambar dulu.");
      return;
    }
    if (trimmed && trimmed.length < 10 && !file && !trimmed.startsWith("http")) {
      setError("Teks lowongan minimal 10 karakter.");
      return;
    }

    setError(null);
    setLoading(true);
    setStepIndex(0);

    const timers = [
      window.setTimeout(() => setStepIndex(1), 700),
      window.setTimeout(() => setStepIndex(2), 1600),
      window.setTimeout(() => setStepIndex(3), 2800),
    ];

    try {
      let result: VerifyResponse;
      if (file) {
        result = await verifyImage(file);
      } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        result = await verifyUrl(trimmed);
      } else {
        result = await verifyText({ text: trimmed });
      }
      sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(result));
      router.push("/report");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Gagal memproses verifikasi.",
      );
      setLoading(false);
    } finally {
      timers.forEach(clearTimeout);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <div
        className={cn(
          "rounded-xl border bg-surface transition-colors",
          dragOver ? "border-charcoal bg-cream-soft" : "border-border",
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) attachFile(f);
        }}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          placeholder="Tempel teks atau link postingan lowongan (Instagram, LinkedIn, JobStreet), atau lampirkan screenshot gambar di bawah…"
          disabled={loading}
          className="w-full resize-y rounded-t-xl bg-transparent px-4 py-4 text-[15px] leading-relaxed text-charcoal placeholder:text-muted focus:outline-none disabled:opacity-60"
        />

        {file && preview && (
          <div className="flex items-center gap-3 border-t border-border px-4 py-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="Preview lampiran"
              className="h-14 w-14 rounded-md border border-border object-cover"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px] font-medium text-charcoal">
                {file.name}
              </p>
              <p className="text-[12px] text-muted">
                {(file.size / 1024).toFixed(0)} KB · akan dianalisis via OCR
              </p>
            </div>
            <button
              type="button"
              onClick={() => attachFile(null)}
              disabled={loading}
              className="rounded-md p-1.5 text-muted hover:bg-cream-deep hover:text-charcoal disabled:opacity-40"
              aria-label="Hapus lampiran"
            >
              <X size={16} weight="bold" />
            </button>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-border px-3 py-3">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] text-charcoal-soft hover:bg-cream-deep hover:text-charcoal disabled:opacity-40"
            >
              <ImageSquare size={18} weight="bold" />
              Lampirkan gambar
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => attachFile(e.target.files?.[0] ?? null)}
              disabled={loading}
            />
          </div>
          <Button type="submit" disabled={loading || (!text.trim() && !file)}>
            {loading ? (
              <>
                <SpinnerGap size={16} className="animate-spin" />
                Memproses…
              </>
            ) : (
              "Verifikasi"
            )}
          </Button>
        </div>
      </div>

      <p className="mt-2 text-center text-[12px] text-muted">
        Teks atau gambar · JPG/PNG/WEBP maks 20MB · bisa seret file ke kotak
      </p>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-md border border-bahaya-fg/20 bg-bahaya-bg px-3.5 py-2.5 text-[14px] text-bahaya-fg"
        >
          {error}
        </p>
      )}

      {loading && (
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-4">
          <p className="text-[14px] font-medium text-charcoal">
            {STEPS[stepIndex]}…
          </p>
          <div className="mt-3 flex gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={cn(
                  "h-1 flex-1 rounded-full",
                  i <= stepIndex ? "bg-charcoal" : "bg-cream-deep",
                )}
              />
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
