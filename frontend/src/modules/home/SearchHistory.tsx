"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import {
  ClockCounterClockwise,
  ArrowUpRight,
  ShieldCheck,
  Warning,
  WarningOctagon,
  CaretLeft,
  CaretRight,
} from "@phosphor-icons/react";

export interface HistoryItem {
  id: string;
  title: string;
  verdict: "AMAN" | "WASPADA" | "BAHAYA";
  risk_score: number;
  timeAgo: string;
  entitiesSummary: string;
}

const DUMMY_HISTORY: HistoryItem[] = [
  {
    id: "hist-001",
    title: "Lowongan Admin Chat Telegram & WA - CS Online PT Sukses Sejahtera",
    verdict: "BAHAYA",
    risk_score: 88,
    timeAgo: "10 menit lalu",
    entitiesSummary: "PT Sukses Sejahtera • Telegram",
  },
  {
    id: "hist-002",
    title: "https://careers.tokopedia.com/job/senior-frontend-engineer",
    verdict: "AMAN",
    risk_score: 12,
    timeAgo: "2 jam lalu",
    entitiesSummary: "PT Tokopedia • Official Portal",
  },
  {
    id: "hist-003",
    title: "Dibutuhkan Staff Entry Data Input Gaji 7-10 Juta/Bulan Tanpa Pengalaman",
    verdict: "WASPADA",
    risk_score: 58,
    timeAgo: "Kemarin",
    entitiesSummary: "Staff Entry Data • Form WA",
  },
  {
    id: "hist-004",
    title: "Lowongan kerja PT Pertamina (Persero) Rekrutmen Bersama BUMN 2026",
    verdict: "AMAN",
    risk_score: 5,
    timeAgo: "2 hari lalu",
    entitiesSummary: "PT Pertamina • BUMN Official",
  },
  {
    id: "hist-005",
    title: "Tawaran Kerja Freelance Transkrip Audio Komisi Rp 500rb/Hari deposit awal",
    verdict: "BAHAYA",
    risk_score: 92,
    timeAgo: "3 hari lalu",
    entitiesSummary: "Deposit Tunai • Rekening Perorangan",
  },
  {
    id: "hist-006",
    title: "Lowongan Customer Service Shopee Express Jakarta Barat Shift Malam",
    verdict: "WASPADA",
    risk_score: 45,
    timeAgo: "4 hari lalu",
    entitiesSummary: "Shopee Express • Form Google Forms",
  },
];

const ITEMS_PER_PAGE = 3;

export function SearchHistory() {
  const router = useRouter();
  const [history] = useState<HistoryItem[]>(DUMMY_HISTORY);
  const [currentPage, setCurrentPage] = useState(1);

  const totalPages = Math.ceil(history.length / ITEMS_PER_PAGE);

  const paginatedItems = history.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handleSelectHistory = () => {
    router.push("/report");
  };

  const getVerdictBadge = (verdict: HistoryItem["verdict"], score: number) => {
    switch (verdict) {
      case "BAHAYA":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-bahaya-border bg-bahaya-bg px-2 py-0.5 font-mono text-[9px] font-bold text-bahaya-fg">
            <WarningOctagon size={10} weight="fill" />
            BAHAYA ({score})
          </span>
        );
      case "WASPADA":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-waspada-border bg-waspada-bg px-2 py-0.5 font-mono text-[9px] font-bold text-waspada-fg">
            <Warning size={10} weight="fill" />
            WASPADA ({score})
          </span>
        );
      case "AMAN":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-aman-border bg-aman-bg px-2 py-0.5 font-mono text-[9px] font-bold text-aman-fg">
            <ShieldCheck size={10} weight="fill" />
            AMAN ({score})
          </span>
        );
    }
  };

  return (
    <div className="mt-5 w-full">
      {/* Header Label di luar box (matching 'Cek risiko lowongan') */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
            <ClockCounterClockwise size={11} weight="bold" className="text-bg-elevated" />
          </div>
          <span className="text-[13px] font-medium text-text-primary">
            Riwayat verifikasi
          </span>
        </div>
        <span className="font-mono text-[10px] text-text-muted">
          {history.length} Total
        </span>
      </div>

      {/* Main Card Box */}
      <div className="w-full rounded-2xl border border-border bg-bg-elevated p-3">
        {/* List items compact minimalis (Maksimal 3 per halaman dengan Animasi Transisi) */}
        <div className="min-h-[160px] overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentPage}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="space-y-1.5"
            >
              {paginatedItems.map((item) => (
                <div
                  key={item.id}
                  onClick={handleSelectHistory}
                  className="group flex cursor-pointer items-center justify-between gap-2.5 rounded-xl border border-border/50 bg-bg-subtle/30 px-3 py-2 transition-all hover:border-border-focus hover:bg-bg-subtle"
                >
                  <div className="min-w-0 flex-1">
                    <h5 className="text-[11.5px] font-medium text-text-primary truncate group-hover:text-text-primary">
                      {item.title}
                    </h5>
                    <p className="text-[10px] text-text-muted truncate mt-0.5">
                      {item.timeAgo} • {item.entitiesSummary}
                    </p>
                  </div>

                  {/* Indikator Kategori (Rata Kanan) */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {getVerdictBadge(item.verdict, item.risk_score)}
                    <ArrowUpRight size={12} weight="bold" className="text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </div>
              ))}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer Pagination Minimalis (3 riwayat per halaman) */}
        {totalPages > 1 && (
          <div className="mt-2.5 flex items-center justify-between border-t border-border/50 pt-2 px-1">
            <span className="font-mono text-[10px] text-text-muted">
              Halaman {currentPage} dari {totalPages}
            </span>

            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                className="flex h-6 w-6 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                title="Halaman sebelumnya"
              >
                <CaretLeft size={12} weight="bold" />
              </button>
              <button
                type="button"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
                className="flex h-6 w-6 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                title="Halaman selanjutnya"
              >
                <CaretRight size={12} weight="bold" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
