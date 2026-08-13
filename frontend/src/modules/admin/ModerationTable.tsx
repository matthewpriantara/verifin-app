"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  CheckCircle,
  XCircle,
  Warning,
  Globe,
  Buildings,
  LinkSimple,
  Clock,
  FunnelSimple,
  ChatText,
  Eye,
  CalendarBlank,
  ImageSquare,
  ArrowSquareOut,
} from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { CommunityReport, ReportStatus, ReportType } from "@/types/admin";
import { fetchCommunityReports, reviewCommunityReport } from "@/lib/api";

/* ── Helpers ──────────────────────────────────────────────────────────────── */
const REPORT_TYPE_LABEL: Record<string, string> = {
  biaya_travel:        "Penipuan Biaya & Travel",
  perusahaan_fiktif:   "Perusahaan Fiktif",
  tppo_eksploitasi:    "Indikasi TPPO & Eksploitasi",
  pencurian_data_scam: "Pencurian Data & Task Scam",
};

const reportTypeLabel = (t: string) => REPORT_TYPE_LABEL[t] ?? t.replace(/_/g, " ");

const FILTER_OPTIONS: { value: ReportStatus | "all"; label: string }[] = [
  { value: "all",      label: "Semua" },
  { value: "pending",  label: "Menunggu" },
  { value: "approved", label: "Disetujui" },
  { value: "rejected", label: "Ditolak" },
];

/* ── Status badge ─────────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status: ReportStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        status === "pending"  && "bg-waspada-bg text-waspada-fg",
        status === "approved" && "bg-aman-bg text-aman-fg",
        status === "rejected" && "bg-bahaya-bg text-bahaya-fg",
      )}
    >
      {status === "pending"  && <Clock size={10} weight="bold" />}
      {status === "approved" && <CheckCircle size={10} weight="bold" />}
      {status === "rejected" && <XCircle size={10} weight="bold" />}
      {status === "pending"  ? "Menunggu" : status === "approved" ? "Disetujui" : "Ditolak"}
    </span>
  );
}

/* ── Report type badge ────────────────────────────────────────────────────── */
function TypeBadge({ type }: { type: ReportType }) {
  return (
    <span className="inline-flex items-center rounded border border-border bg-bg-subtle px-2 py-0.5 font-mono text-[10px] uppercase text-text-muted">
      {reportTypeLabel(type)}
    </span>
  );
}

/* ── Detail Modal ─────────────────────────────────────────────────────────── */
function DetailModal({
  report,
  onClose,
}: {
  report: CommunityReport;
  onClose: () => void;
}) {
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-text-primary/20 px-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 8 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-lg rounded-2xl border border-border bg-bg-elevated p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <Eye size={16} weight="bold" className="text-text-muted" />
            <h3 className="text-[14px] font-bold text-text-primary">Detail Laporan Komunitas</h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-text-muted transition-colors hover:bg-bg-subtle hover:text-text-primary"
          >
            <XCircle size={18} />
          </button>
        </div>

        <div className="flex flex-col gap-4 text-[13px]">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-bg-subtle/50 p-3">
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Perusahaan</span>
              <span className="font-semibold text-text-primary flex items-center gap-1 mt-0.5">
                <Buildings size={12} /> {report.company_name}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Tipe Laporan</span>
              <span className="font-semibold text-text-primary block mt-0.5">
                {reportTypeLabel(report.report_type)}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Pelapor (IP)</span>
              <span className="font-mono text-text-primary flex items-center gap-1 mt-0.5">
                <Globe size={12} /> {report.reporter_ip}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Waktu Submit</span>
              <span className="text-text-primary flex items-center gap-1 mt-0.5">
                <CalendarBlank size={12} /> {new Date(report.created_at).toLocaleString("id-ID")}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Status</span>
              <span className="block mt-0.5"><StatusBadge status={report.status} /></span>
            </div>
            {report.url && (
              <div>
                <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider">Tautan Bukti</span>
                <a
                  href={report.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-text-primary flex items-center gap-1 mt-0.5 underline decoration-dotted hover:text-text-secondary"
                >
                  <LinkSimple size={12} /> Buka Link Bukti
                </a>
              </div>
            )}
          </div>

          {/* Description / Kronologi */}
          <div>
            <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider mb-1">Kronologi Kejadian</span>
            <div className="rounded-xl border border-border bg-bg-elevated p-3 text-[13px] leading-relaxed text-text-secondary max-h-48 overflow-y-auto">
              {report.description || "—"}
            </div>
          </div>

          {/* Bukti Gambar (evidence_file_url) */}
          {report.evidence_file_url && (
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider mb-1.5">Bukti Gambar</span>
              <a
                href={`${report.evidence_file_url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block overflow-hidden rounded-xl border border-border bg-bg-subtle transition-colors hover:border-border-focus"
              >
                <img
                  src={report.evidence_file_url}
                  alt="Bukti komunitas"
                  className="h-48 w-full object-cover"
                />
              </a>
            </div>
          )}

          {/* Case ID (link ke report) */}
          {report.case_id && (
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider mb-1">Terkait Kasus Verifikasi</span>
              <a
                href={`/report/${report.case_id}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3 py-2 font-mono text-[12px] text-text-primary transition-colors hover:border-border-focus"
              >
                <ArrowSquareOut size={12} />
                {report.case_id.slice(0, 8)}…
                <span className="text-text-muted">→ Lihat Laporan</span>
              </a>
            </div>
          )}

          {/* Reviewer Note */}
          {report.reviewer_note && (
            <div>
              <span className="text-[11px] font-medium text-text-muted block uppercase tracking-wider mb-1">Catatan Reviewer</span>
              <div className="flex items-start gap-1.5 rounded-xl border border-border bg-bg-subtle p-3 text-[12px] italic text-text-secondary">
                <ChatText size={14} className="mt-0.5 shrink-0 text-text-muted" />
                <p>{report.reviewer_note}</p>
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-text-primary px-4 py-2 text-[13px] font-semibold text-bg-elevated transition-opacity hover:opacity-90"
          >
            Tutup
          </button>
        </div>
      </motion.div>
    </div>
  );
}

/* ── Note modal ───────────────────────────────────────────────────────────── */
function NoteModal({
  report,
  action,
  onConfirm,
  onCancel,
}: {
  report: CommunityReport;
  action: "approved" | "rejected";
  onConfirm: (note: string) => void;
  onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const isApprove = action === "approved";

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-text-primary/20 px-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 8 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md rounded-2xl border border-border bg-bg-elevated p-5 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2.5">
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg",
              isApprove ? "bg-aman-bg" : "bg-bahaya-bg",
            )}
          >
            {isApprove
              ? <CheckCircle size={16} weight="bold" className="text-aman-fg" />
              : <XCircle size={16} weight="bold" className="text-bahaya-fg" />}
          </div>
          <div>
            <p className="text-[14px] font-semibold text-text-primary">
              {isApprove ? "Setujui laporan?" : "Tolak laporan?"}
            </p>
            <p className="text-[12px] text-text-muted">{report.company_name}</p>
          </div>
        </div>

        <div className="mb-4 rounded-lg border border-border bg-bg-subtle p-3 text-[12px] leading-relaxed text-text-secondary">
          {(report.description || "").length > 120
            ? (report.description || "").slice(0, 120) + "…"
            : report.description || "—"}
        </div>

        <div className="mb-4">
          <label className="mb-1.5 block text-[12px] font-medium text-text-secondary">
            Catatan reviewer <span className="text-text-muted">(opsional)</span>
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder={isApprove ? "Alasan persetujuan..." : "Alasan penolakan..."}
            className="w-full resize-none rounded-lg border border-border bg-bg px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-border-focus"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-border bg-bg-subtle px-3 py-2 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary"
          >
            Batal
          </button>
          <button
            onClick={() => onConfirm(note)}
            className={cn(
              "flex-1 rounded-lg px-3 py-2 text-[13px] font-semibold transition-opacity hover:opacity-90",
              isApprove
                ? "bg-aman-fg text-white"
                : "bg-bahaya-fg text-white",
            )}
          >
            {isApprove ? "Setujui" : "Tolak"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

/* ── Row ──────────────────────────────────────────────────────────────────── */
function ReportRow({
  report,
  index,
  onApprove,
  onReject,
  onViewDetail,
}: {
  report: CommunityReport;
  index: number;
  onApprove: (id: string) => void;
  onReject:  (id: string) => void;
  onViewDetail: (report: CommunityReport) => void;
}) {
  const isPending = report.status === "pending";

  return (
    <motion.tr
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 4 }}
      transition={{ delay: index * 0.04, duration: 0.2 }}
      className="group hover:bg-bg-subtle/60 transition-colors"
    >
      {/* Status */}
      <td className="px-4 py-3 align-top">
        <StatusBadge status={report.status} />
      </td>

      {/* Pelapor (IP) */}
      <td className="px-4 py-3 align-top">
        <div className="flex items-center gap-1.5">
          <Globe size={12} className="shrink-0 text-text-muted" />
          <span className="font-mono text-[12px] text-text-secondary">{report.reporter_ip}</span>
        </div>
      </td>

      {/* Perusahaan */}
      <td className="px-4 py-3 align-top">
        <div className="flex items-center gap-1.5">
          <Buildings size={12} className="shrink-0 text-text-muted" />
          <span className="max-w-[160px] truncate text-[13px] font-medium text-text-primary">
            {report.company_name}
          </span>
        </div>
      </td>

      {/* Tipe */}
      <td className="px-4 py-3 align-top">
        <TypeBadge type={report.report_type} />
      </td>

      {/* Deskripsi */}
      <td className="px-4 py-3 align-top">
        <div className="flex flex-col items-start gap-1">
          <p className="max-w-[240px] text-[12px] leading-relaxed text-text-muted line-clamp-2">
            {report.description || "—"}
          </p>
          <button
            onClick={() => onViewDetail(report)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-text-primary hover:underline"
          >
            <Eye size={11} /> Detail Deskripsi
          </button>
        </div>
        
        {report.url && (
          <a
            href={report.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-[11px] text-text-secondary underline-offset-2 hover:underline"
          >
            <LinkSimple size={10} />
            Bukti
          </a>
        )}
        {report.evidence_file_url && (
          <span className="mt-1 inline-flex items-center gap-1 text-[11px] text-text-secondary">
            <ImageSquare size={10} />
            <a
              href={report.evidence_file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-2 hover:underline"
            >
              Gambar
            </a>
          </span>
        )}
        {report.case_id && (
          <span className="mt-1 inline-flex items-center gap-1 font-mono text-[10px] text-text-muted">
            <ArrowSquareOut size={9} />
            <a href={`/report/${report.case_id}`} className="hover:underline">
              {report.case_id.slice(0, 8)}…
            </a>
          </span>
        )}
        {report.reviewer_note && (
          <div className="mt-1.5 flex items-start gap-1 rounded-md bg-bg-subtle px-2 py-1">
            <ChatText size={10} className="mt-0.5 shrink-0 text-text-muted" />
            <p className="text-[11px] italic text-text-muted">{report.reviewer_note}</p>
          </div>
        )}
      </td>

      {/* Waktu */}
      <td className="px-4 py-3 align-top whitespace-nowrap">
        <span className="text-[12px] text-text-muted">
          {new Date(report.created_at).toLocaleString("id-ID", {
            dateStyle: "short",
            timeStyle: "short",
          })}
        </span>
      </td>

      {/* Aksi */}
      <td className="px-4 py-3 align-top">
        {isPending ? (
          <div className="flex gap-2">
            <button
              onClick={() => onApprove(report.id)}
              className="inline-flex items-center gap-1 rounded-lg border border-aman-border bg-aman-bg px-2.5 py-1.5 text-[12px] font-medium text-aman-fg transition-colors hover:bg-aman-fg hover:text-white"
            >
              <CheckCircle size={12} weight="bold" />
              Setujui
            </button>
            <button
              onClick={() => onReject(report.id)}
              className="inline-flex items-center gap-1 rounded-lg border border-bahaya-border bg-bahaya-bg px-2.5 py-1.5 text-[12px] font-medium text-bahaya-fg transition-colors hover:bg-bahaya-fg hover:text-white"
            >
              <XCircle size={12} weight="bold" />
              Tolak
            </button>
          </div>
        ) : (
          <span className="text-[12px] text-text-muted">
            {report.reviewed_at
              ? new Date(report.reviewed_at).toLocaleDateString("id-ID", { dateStyle: "short" })
              : "—"}
          </span>
        )}
      </td>
    </motion.tr>
  );
}

/* ── Main component ───────────────────────────────────────────────────────── */
export default function ModerationTable() {
  const [reports, setReports] = useState<CommunityReport[]>([]);
  const [filter, setFilter]   = useState<ReportStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [modal, setModal]     = useState<{
    reportId: string;
    action: "approved" | "rejected";
  } | null>(null);
  const [detailModalReport, setDetailModalReport] = useState<CommunityReport | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCommunityReports(undefined, 100)
      .then((rows) => { if (!cancelled) setReports(rows); })
      .catch((err) => { if (!cancelled) setLoadError(err instanceof Error ? err.message : "Gagal memuat laporan."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const pending  = reports.filter((r) => r.status === "pending").length;
  const approved = reports.filter((r) => r.status === "approved").length;
  const rejected = reports.filter((r) => r.status === "rejected").length;

  const filtered = filter === "all"
    ? reports
    : reports.filter((r) => r.status === filter);

  function handleAction(id: string, action: "approved" | "rejected") {
    setModal({ reportId: id, action });
  }

  async function confirmAction(note: string) {
    if (!modal) return;
    try {
      await reviewCommunityReport(modal.reportId, modal.action, note || undefined);
      setReports((prev) =>
        prev.map((r) =>
          r.id === modal.reportId
            ? { ...r, status: modal.action, reviewed_at: new Date().toISOString(), reviewer_note: note || null }
            : r,
        ),
      );
      setModal(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Gagal menyimpan review.");
    }
  }

  const activeReport = modal ? reports.find((r) => r.id === modal.reportId) : null;

  return (
    <div className="flex flex-col gap-4">
      {/* summary bar */}
      {loadError && (
        <div className="rounded-xl border border-bahaya-border bg-bahaya-bg px-4 py-3 text-[13px] text-bahaya-fg">
          {loadError}
        </div>
      )}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Menunggu Review", value: pending,  color: "text-waspada-fg", bg: "bg-waspada-bg border-waspada-border" },
          { label: "Disetujui",       value: approved, color: "text-aman-fg",    bg: "bg-aman-bg border-aman-border" },
          { label: "Ditolak",         value: rejected, color: "text-bahaya-fg",  bg: "bg-bahaya-bg border-bahaya-border" },
        ].map(({ label, value, color, bg }) => (
          <div key={label} className={cn("rounded-xl border p-4", bg)}>
            <p className="text-[11px] font-medium text-text-muted">{label}</p>
            <p className={cn("mt-1 font-mono text-2xl font-semibold tabular-nums", color)}>{value}</p>
          </div>
        ))}
      </div>

      {/* filter row */}
      <div className="flex items-center gap-2">
        <FunnelSimple size={13} className="text-text-muted" />
        <div className="flex gap-1 rounded-lg border border-border bg-bg-subtle p-0.5">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors",
                filter === opt.value
                  ? "bg-bg-elevated text-text-primary shadow-sm"
                  : "text-text-muted hover:text-text-secondary",
              )}
            >
              {opt.label}
              {opt.value !== "all" && (
                <span className="ml-1.5 font-mono text-[10px]">
                  ({opt.value === "pending" ? pending : opt.value === "approved" ? approved : rejected})
                </span>
              )}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[12px] text-text-muted">
          {filtered.length} laporan
        </span>
      </div>

      {/* table */}
      <div className="overflow-hidden rounded-xl border border-border bg-bg-elevated">
        {loading ? (
          <div className="py-16 text-center text-[13px] text-text-muted">Memuat laporan…</div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-[13px] text-text-muted">
            <Warning size={20} className="mx-auto mb-2 opacity-40" />
            Tidak ada laporan dengan status ini
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-border bg-bg-subtle">
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Pelapor (IP)</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Perusahaan</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Tipe</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Deskripsi</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Waktu</th>
                  <th className="px-4 py-3 text-left font-medium text-text-muted">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <AnimatePresence>
                  {filtered.map((report, i) => (
                    <ReportRow
                      key={report.id}
                      report={report}
                      index={i}
                      onApprove={(id) => handleAction(id, "approved")}
                      onReject={(id)  => handleAction(id, "rejected")}
                      onViewDetail={(r) => setDetailModalReport(r)}
                    />
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* action note modal */}
      <AnimatePresence>
        {modal && activeReport && (
          <NoteModal
            report={activeReport}
            action={modal.action}
            onConfirm={confirmAction}
            onCancel={() => setModal(null)}
          />
        )}
      </AnimatePresence>

      {/* view detail info modal */}
      <AnimatePresence>
        {detailModalReport && (
          <DetailModal
            report={detailModalReport}
            onClose={() => setDetailModalReport(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
