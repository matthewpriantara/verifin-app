"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import Image from "next/image";

export function Navbar() {
  const pathname = usePathname();
  const onReport = pathname.startsWith("/report");

  return (
    <header className="border-b border-border bg-cream">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-charcoal no-underline"
        >
          <Image 
          src="/images/logo-verifin.png" 
          alt="Verifin" 
          width={100} 
          height={100} />
        </Link>

        {onReport && (
          <Link
            href="/"
            className={cn(
              "rounded-md px-3 py-1.5 text-[14px] text-charcoal-soft transition-colors hover:bg-cream-deep hover:text-charcoal",
            )}
          >
            Verifikasi baru
          </Link>
        )}
      </div>
    </header>
  );
}
