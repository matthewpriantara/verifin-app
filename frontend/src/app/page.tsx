import type { Metadata } from "next";
import { VerifyBox } from "@/components/verify/VerifyBox";

export const metadata: Metadata = {
  title: "Verifin — Verifikasi Lowongan Kerja",
  description:
    "Tempel teks atau unggah screenshot lowongan. Dapatkan skor risiko penipuan secara langsung.",
};

export default function HomePage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 sm:px-6 sm:py-16">
      <div className="mb-8 w-full max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">
          Cek lowongan kerja
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-charcoal-soft">
          Tempel teks atau lampirkan screenshot. Verifin menganalisis risiko
          penipuan lewat OCR, OSINT, dan AI.
        </p>
      </div>
      <VerifyBox />
    </div>
  );
}
