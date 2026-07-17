"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CircleNotch } from "@phosphor-icons/react";
import { Button } from "@/components/ui/Button";
import { RiskMeter } from "@/components/report/RiskMeter";
import { FactorList } from "@/components/report/FactorList";
import { EntityPanel } from "@/components/report/EntityPanel";
import { EvidencePanel } from "@/components/report/EvidencePanel";
import { REPORT_STORAGE_KEY } from "@/lib/utils";
import type { VerifyResponse } from "@/types/verify";

export default function ReportPage() {
  const [report, setReport] = useState<VerifyResponse | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      try {
        const raw = sessionStorage.getItem(REPORT_STORAGE_KEY);
        setReport(raw ? (JSON.parse(raw) as VerifyResponse) : null);
      } catch {
        setReport(null);
      } finally {
        if (!cancelled) setReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-2 text-charcoal-soft">
        <CircleNotch size={18} className="animate-spin" />
        <span className="text-[14px]">Memuat laporan…</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center sm:px-6">
        <h1 className="text-2xl font-semibold text-charcoal">
          Belum ada laporan
        </h1>
        <p className="mt-2 text-[15px] text-charcoal-soft">
          Kirim lowongan di halaman verifikasi dulu untuk melihat skor risiko.
        </p>
        <div className="mt-6">
          <Link href="/">
            <Button>Ke verifikasi</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[14px] text-charcoal-soft hover:text-charcoal"
        >
          <ArrowLeft size={16} weight="bold" />
          Verifikasi lagi
        </Link>
      </div>

      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight text-charcoal">
          Laporan analisis
        </h1>
        <p className="mt-2 text-[15px] text-charcoal-soft">
          Hasil hybrid OCR / NER / OSINT dan penalaran AI.
          {report.model_used ? (
            <span className="mt-1 block font-mono text-[12px] text-muted">
              Model: {report.model_used}
            </span>
          ) : null}
        </p>
      </header>

      <div className="space-y-5">
        <RiskMeter score={report.risk_score} verdict={report.verdict} />

        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-[15px] font-semibold text-charcoal">Ringkasan</h2>
          <p className="mt-2 text-[15px] leading-relaxed text-charcoal-soft">
            {report.summary || "Tidak ada ringkasan dari model."}
          </p>
        </section>

        <div className="grid gap-5 sm:grid-cols-2">
          <FactorList
            title="Faktor risiko"
            items={report.risk_factors || []}
            kind="risk"
          />
          <FactorList
            title="Faktor aman"
            items={report.safe_factors || []}
            kind="safe"
          />
        </div>

        <FactorList
          title="Rekomendasi"
          items={report.recommendations || []}
          kind="reco"
        />

        <EntityPanel entities={report.entities} />
        <EvidencePanel osint={report.osint} />
      </div>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/">
          <Button>Verifikasi lowongan lain</Button>
        </Link>
      </div>
    </div>
  );
}
