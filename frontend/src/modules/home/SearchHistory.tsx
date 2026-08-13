"use client";

import { useState, useEffect } from "react";
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
  removeHistory,
  clearHistory,
  formatTimeAgo,
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

export function SearchHistory() {
  const router = useRouter();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [direction, setDirection] = useState(0);

  // Load history dari localStorage saat mount
  useEffect(() => {
    setHistory(getHistory());

    // Listen perubahan localStorage (misal: setelah verifikasi baru, tab lain)
    const handleStorage = () => setHistory(getHistory());
    window.addEventListener("storage", handleStorage);
    window.addEventListener("verifin:history-updated", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("verifin:history-updated", handleStorage);
    };
  }, []);

  // Reset ke halaman 1 kalau history berubah
  useEffect(() => {
    if (currentPage > 1 && (currentPage - 1) * ITEMS_PER_PAGE >= history.length) {
      setCurrentPage(1);
    }
  }, [history.length, currentPage]);

  const totalPages = Math.max(1, Math.ceil(history.length / ITEMS_PER_PAGE));

  const paginatedItems = history.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handlePageChange = (newPage: number) => {
    if (newPage === currentPage) return;
    setDirection(newPage > currentPage ? 1 : -1);
    setCurrentPage(newPage);
  };

  const handleSelectHistory = (item: HistoryItem) => {
    if (item.case_id) {
      router.push(`/report/${item.case_id}`);
    } else {
      router.push("/report");
    }
  };

  const handleRemove = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    removeHistory(id);
    setHistory(getHistory());
  };

  const handleClearAll = () => {
    clearHistory();
    setHistory([]);
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
          <span className="font-mono text-[10px] text-text-muted">
            {history.length} Total
          </span>
          {history.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              className="flex h-5 w-5 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-bahaya-bg hover:text-bahaya-fg"
              title="Hapus semua riwayat"
            >
              <Trash size={11} weight="bold" />
            </button>
          )}
        </div>
      </div>

      {/* Main Card */}
      <div className="w-full rounded-2xl bg-bg-elevated p-3">
        <div className="overflow-hidden">
          {history.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl bg-bg-subtle">
                <FolderOpen size={18} weight="bold" className="text-text-muted" />
              </div>
              <p className="text-[12px] font-medium text-text-secondary">
                Belum ada riwayat
              </p>
              <p className="mt-0.5 text-[10px] text-text-muted">
                Verifikasi lowongan untuk mulai melacak
              </p>
            </div>
          ) : (
            <AnimatePresence mode="wait" custom={direction} initial={false}>
              <motion.div
                key={currentPage}
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
                    className="group flex cursor-pointer items-center justify-between gap-2.5 rounded-xl border border-border/50 bg-bg-subtle/30 px-3 py-2.5 transition-all hover:border-border-focus hover:bg-bg-subtle hover:shadow-xs active:scale-[0.99]"
                  >
                    <div className="min-w-0 flex-1">
                      <h5 className="text-[11.5px] font-medium text-text-primary truncate group-hover:text-text-primary">
                        {item.title}
                      </h5>
                      <p className="text-[10px] text-text-muted truncate mt-0.5">
                        {formatTimeAgo(item.timestamp)} • {item.entitiesSummary}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {getVerdictBadge(item.verdict, item.risk_score)}
                      <button
                        type="button"
                        onClick={(e) => handleRemove(e, item.id)}
                        className="flex h-5 w-5 items-center justify-center rounded-md text-text-muted opacity-0 transition-all hover:bg-bahaya-bg hover:text-bahaya-fg group-hover:opacity-100"
                        title="Hapus riwayat ini"
                      >
                        <Trash size={10} weight="bold" />
                      </button>
                      <ArrowUpRight size={12} weight="bold" className="text-text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                  </div>
                ))}
              </motion.div>
            </AnimatePresence>
          )}
        </div>

        {totalPages > 1 && (
          <div className="mt-2.5 flex items-center justify-between border-t border-border/50 pt-2 px-1">
            <span className="font-mono text-[10px] text-text-muted">
              Halaman {currentPage} dari {totalPages}
            </span>

            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => handlePageChange(Math.max(currentPage - 1, 1))}
                className="flex h-6 w-6 items-center justify-center rounded-lg border border-border bg-bg-subtle text-text-muted transition-colors hover:border-border-focus hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none active:scale-95"
                title="Halaman sebelumnya"
              >
                <CaretLeft size={12} weight="bold" />
              </button>
              <button
                type="button"
                disabled={currentPage === totalPages}
                onClick={() => handlePageChange(Math.min(currentPage + 1, totalPages))}
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
