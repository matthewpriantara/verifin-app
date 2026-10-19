"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
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
  Trash,
  FolderOpen,
} from "@phosphor-icons/react";
import {
  getHistory,
  getServerHistory,
  subscribeHistory,
  removeHistory,
  clearHistory,
  formatTimeAgo,
  cn,
  type HistoryItem,
} from "@/lib/utils";

const ITEMS_PER_PAGE = 3;

const pageVariants = {
  enter: (dir: number) => ({
    opacity: 0,
    x: dir > 0 ? 16 : dir < 0 ? -16 : 0,
  }),
  center: {
    opacity: 1,
    x: 0,
  },
  exit: (dir: number) => ({
    opacity: 0,
    x: dir > 0 ? -16 : dir < 0 ? 16 : 0,
  }),
};

const noopSubscribe = () => () => {};

export function SearchHistory() {
  const router = useRouter();
  const history = useSyncExternalStore(subscribeHistory, getHistory, getServerHistory);
  // Di server riwayat selalu kosong; tahan empty state sampai localStorage terbaca
  const hydrated = useSyncExternalStore(noopSubscribe, () => true, () => false);
  // Perbarui label "x menit lalu" tiap menit
  const [, setTick] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(iv);
  }, []);
  const [currentPage, setCurrentPage] = useState(1);
  const [direction, setDirection] = useState(0);

  const totalPages = Math.max(1, Math.ceil(history.length / ITEMS_PER_PAGE));
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);

  const paginatedItems = history.slice(
    (safeCurrentPage - 1) * ITEMS_PER_PAGE,
    safeCurrentPage * ITEMS_PER_PAGE
  );

  const handlePageChange = (newPage: number) => {
    if (newPage === safeCurrentPage) return;
    setDirection(newPage > safeCurrentPage ? 1 : -1);
    setCurrentPage(newPage);
  };
  // Tanpa case_id laporan tidak tersimpan di server; jangan buka laporan terakhir milik lowongan lain
  const handleSelectHistory = (item: HistoryItem) => {
    if (item.case_id) router.push(`/report/${item.case_id}`);
  };

  const handleRemove = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    removeHistory(id);
  };

  const handleClearAll = () => {
    clearHistory();
  };

  const getVerdictBadge = (verdict: HistoryItem["verdict"], score: number) => {
    switch (verdict) {
      case "BAHAYA":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-bahaya-border bg-bahaya-bg px-2 py-0.5 font-mono text-[11px] font-bold text-bahaya-fg">
            <WarningOctagon size={10} weight="fill" />
            BAHAYA ({score})
          </span>
        );
      case "WASPADA":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-waspada-border bg-waspada-bg px-2 py-0.5 font-mono text-[11px] font-bold text-waspada-fg">
            <Warning size={10} weight="fill" />
            WASPADA ({score})
          </span>
        );
      case "AMAN":
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-aman-border bg-aman-bg px-2 py-0.5 font-mono text-[11px] font-bold text-aman-fg">
            <ShieldCheck size={10} weight="fill" />
            AMAN ({score})
          </span>
        );
    }
  };

  return (
    <div className="mt-5 w-full">
      {/* Header Label */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-text-primary">
            <ClockCounterClockwise size={11} weight="bold" className="text-bg-elevated" />
          </div>
          <span className="text-[13px] font-medium text-text-primary">
            Riwayat verifikasi
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[12px] text-text-muted">
            {hydrated ? `${history.length} lowongan` : ""}
          </span>
          {history.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              className="-my-3 flex h-11 w-11 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bahaya-bg hover:text-bahaya-fg"
              title="Hapus semua riwayat"
              aria-label="Hapus semua riwayat"
            >
              <Trash size={14} weight="bold" />
            </button>
          )}
        </div>
      </div>

      {/* Main Card */}
      <div className="w-full rounded-2xl bg-bg-elevated p-3">
        <div className="overflow-hidden">
          {!hydrated ? (
            <div className="h-24 animate-pulse rounded-xl bg-bg-subtle/60" aria-hidden />
          ) : history.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-bg-subtle">
                <FolderOpen size={18} weight="bold" className="text-text-muted" />
              </div>
              <p className="text-[12px] font-medium text-text-secondary">
                Belum ada riwayat
              </p>
              <p className="mt-0.5 text-[12px] text-text-muted">
                Verifikasi lowongan untuk mulai melacak
              </p>
            </div>
          ) : (
            <AnimatePresence mode="wait" custom={direction} initial={false}>
              <motion.div
                key={safeCurrentPage}
                custom={direction}
                variants={pageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="space-y-1.5"
              >
                {paginatedItems.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectHistory(item)}
                    role={item.case_id ? "button" : undefined}
                    tabIndex={item.case_id ? 0 : undefined}
                    aria-label={item.case_id ? `Buka laporan ${item.title}, ${item.verdict} skor ${item.risk_score}` : undefined}
                    onKeyDown={(e) => {
                      if (e.target !== e.currentTarget) return;
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleSelectHistory(item);
                      }
                    }}
                    className={cn(
                      "group flex items-center justify-between gap-2.5 rounded-xl border border-border/50 bg-bg-subtle/30 px-3 py-2.5 transition-all",
                      item.case_id && "cursor-pointer hover:border-border-focus hover:bg-bg-subtle hover:shadow-xs active:scale-[0.99]",
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <h5 className="text-[13px] font-medium text-text-primary truncate">
                        {item.title}
                      </h5>
                      <p className="text-[12px] text-text-muted truncate mt-0.5">
                        {formatTimeAgo(item.timestamp)} • {item.case_id ? item.entitiesSummary : "Laporan tidak tersimpan, cek ulang lowongannya"}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {getVerdictBadge(item.verdict, item.risk_score)}
                      <button
                        type="button"
                        onClick={(e) => handleRemove(e, item.id)}
                        className="-my-2 flex h-11 w-11 items-center justify-center rounded-md text-text-muted transition-all hover:bg-bahaya-bg hover:text-bahaya-fg sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 focus-visible:opacity-100"
                        title="Hapus riwayat ini"
                        aria-label="Hapus riwayat ini"
                      >
                        <Trash size={14} weight="bold" />
                      </button>
                      <ArrowUpRight size={12} weight="bold" className="hidden text-text-muted opacity-0 transition-opacity group-hover:opacity-100 sm:block" />
                    </div>
                  </div>
                ))}
              </motion.div>
            </AnimatePresence>
          )}
        </div>

        {totalPages > 1 && (
          <div className="mt-2.5 flex items-center justify-between border-t border-border/50 pt-2 px-1">
            <span className="font-mono text-[12px] text-text-muted">
              Halaman {safeCurrentPage} dari {totalPages}
            </span>

            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => handlePageChange(Math.max(currentPage - 1, 1))}
                className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                title="Halaman sebelumnya"
              >
                <CaretLeft size={12} weight="bold" />
              </button>
              <button
                type="button"
                disabled={currentPage === totalPages}
                onClick={() => handlePageChange(Math.min(currentPage + 1, totalPages))}
                className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
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
