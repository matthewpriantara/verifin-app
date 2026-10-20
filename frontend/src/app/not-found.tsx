import Link from "next/link";
import { ArrowLeft, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { buttonClass } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-20 text-center animate-fade-in">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-bg-elevated text-waspada-fg shadow-sm">
        <WarningCircle size={28} weight="duotone" />
      </div>
      <h1 className="mt-5 text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
        Halaman Tidak Ditemukan
      </h1>
      <p className="mt-2.5 max-w-md text-[13px] leading-relaxed text-text-muted sm:text-[14px]">
        Tautan yang kamu buka mungkin salah, telah dipindahkan, atau laporan verifikasi tidak lagi tersedia.
      </p>
      <div className="mt-8 flex items-center gap-3">
        <Link href="/" className={buttonClass()}>
          <ArrowLeft size={14} weight="bold" />
          Kembali ke Beranda
        </Link>
      </div>
    </div>
  );
}
