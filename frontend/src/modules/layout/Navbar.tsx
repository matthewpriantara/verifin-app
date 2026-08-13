"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, ChatTeardropText, Gauge } from "@phosphor-icons/react";

export function Navbar() {
  const pathname = usePathname();
  const onReport = pathname.startsWith("/report");
  const onHome = pathname === "/";

  // Ambil caseId dari pathname untuk pre-fill form lapor komunitas
  // pathname format: /report/{caseId} atau /report
  const caseId = onReport && pathname.startsWith("/report/")
    ? pathname.split("/report/")[1]
    : undefined;

  const reportJobHref = caseId
    ? `/report-job?caseId=${encodeURIComponent(caseId)}`
    : "/report-job";

  // Tampilkan tombol lapor komunitas di home & report page (kecuali di /report-job sendiri)
  const showLapor = (onReport || onHome) && !pathname.startsWith("/report-job");

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-bg/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 no-underline">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-text-primary">
            <ShieldCheck size={15} weight="bold" className="text-bg-elevated" />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-text-primary">
            Verifin
          </span>
        </Link>

        <div className="flex items-center gap-2">
          {showLapor && (
            <Link
              href={reportJobHref}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:border-border-focus hover:text-text-primary"
            >
              <ChatTeardropText size={13} weight="bold" />
              Lapor komunitas
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
