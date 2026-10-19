"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  CaretLeft,
  CaretRight,
  Info,
  MagnifyingGlass,
  ShieldCheck,
  Warning,
  WarningOctagon,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { searchCases } from "@/lib/api";
import type { CaseQueryKind, CaseSearchResponse, CaseSummary } from "@/types/verify";
import { Skeleton } from "@/components/ui/Skeleton";

const PAGE_SIZE = 10;

const FILTERS = [
  { value: "", label: "Semua" },
  { value: "BAHAYA", label: "Bahaya" },
  { value: "WASPADA", label: "Waspada" },
  { value: "AMAN", label: "Aman" },
] as const;

const SOURCE_LABEL: Record<string, string> = {
  text: "Teks",
  image: "Poster",
  url: "Link postingan",
};

const MATCH_LABEL: Record<CaseQueryKind, string> = {
  company: "nama perusahaan",
  phone: "nomor HP",
  email: "email",
  url: "link postingan",
};

const VERDICT_STYLE = {
  BAHAYA: { cls: "border-bahaya-border bg-bahaya-bg text-bahaya-fg", Icon: WarningOctagon },
  WASPADA: { cls: "border-waspada-border bg-waspada-bg text-waspada-fg", Icon: Warning },
  AMAN: { cls: "border-aman-border bg-aman-bg text-aman-fg", Icon: ShieldCheck },
} as const;

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

export default function SearchCasesPage() {
  return (
    <Suspense fallback={<ResultsSkeleton />}>
      <SearchCasesInner />
    </Suspense>
  );
}

function SearchCasesInner() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const verdict = params.get("verdict") ?? "";
  const page = Math.max(0, Number(params.get("page") ?? "1") - 1 || 0);

  const [input, setInput] = useState(q);
  // Samakan isi kotak pencarian saat URL berubah lewat tombol back/forward browser.
  const [syncedQ, setSyncedQ] = useState(q);
  if (q !== syncedQ) {
    setSyncedQ(q);
    setInput(q);
  }
  // Hasil disimpan bersama kunci permintaannya; selama kunci belum cocok, artinya masih memuat.
  const requestKey = `${q}|${verdict}|${page}`;
  const [result, setResult] = useState<{ key: string; data?: CaseSearchResponse; error?: string } | null>(null);
  const loading = result?.key !== requestKey;
  const data = loading ? null : (result?.data ?? null);
  const error = loading ? "" : (result?.error ?? "");

  // Kata kunci, filter, dan halaman disimpan di URL supaya bisa dibagikan
  // dan posisi halaman tetap sama saat kembali dari laporan.
  const pushParams = (nextQ: string, nextVerdict: string, nextPage = 0) => {
    const qs = new URLSearchParams();
    if (nextQ.trim()) qs.set("q", nextQ.trim());
    if (nextVerdict) qs.set("verdict", nextVerdict);
    if (nextPage > 0) qs.set("page", String(nextPage + 1));
    const s = qs.toString();
    router.push(s ? `/cari?${s}` : "/cari", { scroll: false });
  };

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/");
  };

  useEffect(() => {
    const ctrl = new AbortController();
    const key = `${q}|${verdict}|${page}`;
    searchCases({ q, verdict, limit: PAGE_SIZE, skip: page * PAGE_SIZE, signal: ctrl.signal })
      .then((d) => setResult({ key, data: d }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setResult({ key, error: e.message || "Gagal memuat riwayat." });
      });
    return () => ctrl.abort();
  }, [q, verdict, page]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    pushParams(input, verdict);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const searching = q.trim().length > 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8 lg:py-10">
      <div className="mb-6 border-b border-border-focus/40 pb-4">
        <button
          type="button"
          onClick={goBack}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-text-primary px-3.5 py-2 text-[13px] font-semibold text-bg-elevated shadow-sm transition-all hover:bg-text-secondary active:scale-[0.98]"
        >
          <ArrowLeft size={15} weight="bold" /> Kembali
        </button>
      </div>

      <header className="max-w-2xl">
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-text-primary sm:text-[28px]">
          Cari loker yang sudah pernah dicek
        </h1>
        <p className="mt-2 text-[14px] leading-relaxed text-text-secondary">
          Ketik nama perusahaan, nomor WhatsApp, email, atau tempel link postingannya. Kalau lowongan itu
          pernah dianalisis pengguna lain, hasilnya langsung muncul tanpa perlu menunggu pemeriksaan ulang.
        </p>
      </header>

      <form onSubmit={submit} className="mt-6 flex gap-2" role="search">
        <label htmlFor="cari-loker" className="sr-only">
          Kata kunci pencarian
        </label>
        <div className="relative min-w-0 flex-1">
          <MagnifyingGlass
            size={16}
            weight="bold"
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            id="cari-loker"
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Nama perusahaan, nomor WA, email, atau link postingan"
            maxLength={300}
            className="h-11 w-full rounded-xl border border-border bg-bg-elevated pl-10 pr-3 text-[14px] text-text-primary placeholder:text-text-muted focus:border-border-focus focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="h-11 shrink-0 rounded-xl bg-text-primary px-4 text-[14px] font-semibold text-bg-elevated transition-opacity hover:opacity-90 active:scale-[0.98]"
        >
          Cari
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Saring hasil">
        {FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            aria-pressed={verdict === f.value}
            onClick={() => pushParams(q, f.value)}
            className={cn(
              "min-h-11 rounded-lg border px-3.5 text-[13px] font-medium transition-colors",
              verdict === f.value
                ? "border-text-primary bg-text-primary text-bg-elevated"
                : "border-border bg-bg-elevated text-text-secondary hover:border-border-focus hover:text-text-primary",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <p className="mt-5 flex gap-2 rounded-xl bg-bg-subtle px-3.5 py-3 text-[12.5px] leading-relaxed text-text-secondary">
        <Info size={16} weight="bold" className="mt-0.5 shrink-0 text-text-muted" />
        <span>
          Hasil ini menilai <strong className="font-semibold text-text-primary">isi lowongan yang pernah dianalisis</strong>,
          bukan perusahaannya. Penipu sering memakai nama perusahaan asli. Kalau teks, nomor, atau link yang kamu
          terima berbeda, cek ulang lowongan itu.
        </span>
      </p>

      <section className="mt-6" aria-live="polite">
        <div className="mb-2.5 flex items-baseline justify-between gap-3">
          <h2 className="text-[13px] font-medium text-text-primary">
            {searching ? "Hasil pencarian" : "Terakhir dicek"}
          </h2>
          {data && !loading && !data.too_short && (
            <span className="font-mono text-[11px] text-text-muted">{data.total} lowongan</span>
          )}
        </div>

        {loading ? (
          <ResultsSkeleton />
        ) : error ? (
          <p className="rounded-xl border border-bahaya-border bg-bahaya-bg px-4 py-3 text-[13px] text-bahaya-fg">
            {error}
          </p>
        ) : data?.too_short ? (
          <p className="rounded-xl border border-border bg-bg-elevated px-4 py-5 text-[13px] text-text-secondary">
            Kata kunci terlalu pendek. Ketik minimal 3 huruf nama perusahaan, atau minimal 8 digit nomor HP.
          </p>
        ) : data && data.cases.length === 0 ? (
          <EmptyState searching={searching} />
        ) : (
          <ul className="divide-y divide-border/60 overflow-hidden rounded-2xl border border-border bg-bg-elevated">
            {data?.cases.map((c) => <ResultRow key={c.id} item={c} />)}
          </ul>
        )}

        {data && !loading && data.total > 0 && (
          <nav className="mt-3 flex items-center justify-between gap-3" aria-label="Halaman hasil">
            <span className="font-mono text-[11px] text-text-muted">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} dari {data.total}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => pushParams(q, verdict, page - 1)}
                aria-label="Halaman sebelumnya"
                className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-bg-elevated text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary disabled:pointer-events-none disabled:opacity-30"
              >
                <CaretLeft size={14} weight="bold" />
              </button>
              <span className="min-w-[88px] text-center font-mono text-[11px] text-text-muted">
                Halaman {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page + 1 >= totalPages}
                onClick={() => pushParams(q, verdict, page + 1)}
                aria-label="Halaman berikutnya"
                className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-bg-elevated text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary disabled:pointer-events-none disabled:opacity-30"
              >
                <CaretRight size={14} weight="bold" />
              </button>
            </div>
          </nav>
        )}
      </section>
    </div>
  );
}

function ResultRow({ item }: { item: CaseSummary }) {
  const style = VERDICT_STYLE[item.verdict as keyof typeof VERDICT_STYLE];
  const meta = [
    SOURCE_LABEL[item.source ?? ""] ?? null,
    formatDate(item.created_at),
    item.matched_on ? `cocok di ${MATCH_LABEL[item.matched_on]}` : null,
  ].filter(Boolean);

  return (
    <li>
      <Link
        href={`/report/${item.id}`}
        className="group flex items-center justify-between gap-3 px-4 py-3.5 no-underline transition-colors hover:bg-bg-subtle"
      >
        <div className="min-w-0">
          <p className="line-clamp-2 break-words text-[14px] font-medium leading-snug text-text-primary">
            {item.company_name ? `Lowongan atas nama ${item.company_name}` : "Lowongan tanpa nama perusahaan"}
          </p>
          <p className="mt-0.5 truncate text-[12px] text-text-muted">{meta.join(" · ")}</p>
          {item.osint_failed && (
            <p className="mt-1 text-[11.5px] text-waspada-fg">Sebagian pemeriksaan gagal saat itu, sebaiknya cek ulang.</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {style && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-bold",
                style.cls,
              )}
            >
              <style.Icon size={12} weight="fill" />
              {item.verdict} {item.risk_score}
            </span>
          )}
          <ArrowUpRight
            size={14}
            weight="bold"
            className="text-text-muted opacity-0 transition-opacity group-hover:opacity-100"
          />
        </div>
      </Link>
    </li>
  );
}

function EmptyState({ searching }: { searching: boolean }) {
  return (
    <div className="rounded-2xl border border-border bg-bg-elevated px-5 py-8 text-center">
      <p className="text-[14px] font-medium text-text-primary">
        {searching ? "Lowongan ini belum pernah dicek" : "Belum ada riwayat"}
      </p>
      <p className="mx-auto mt-1 max-w-sm text-[12.5px] leading-relaxed text-text-secondary">
        {searching
          ? "Belum pernah dicek bukan berarti aman. Tempel lowongannya ke Verifin untuk diperiksa sekarang."
          : "Riwayat akan muncul setelah ada lowongan yang dianalisis."}
      </p>
      <Link
        href="/"
        className="mt-4 inline-flex rounded-xl bg-text-primary px-4 py-2 text-[13px] font-semibold text-bg-elevated no-underline hover:opacity-90"
      >
        Cek lowongan sekarang
      </Link>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-16 rounded-2xl" />
      ))}
    </div>
  );
}
