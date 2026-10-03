"use client";

import React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export interface TestimonialItem {
  text: string;
  image: string;
  name: string;
  role: string;
}

export const TestimonialsColumn = (props: {
  className?: string;
  testimonials: TestimonialItem[];
  duration?: number;
}) => {
  return (
    <div className={cn("overflow-hidden", props.className)}>
      <motion.div
        animate={{
          translateY: "-50%",
        }}
        transition={{
          duration: props.duration || 14,
          repeat: Infinity,
          ease: "linear",
          repeatType: "loop",
        }}
        className="flex flex-col gap-4 pb-4"
      >
        {[...new Array(2)].map((_, index) => (
          <React.Fragment key={index}>
            {props.testimonials.map(({ text, image, name, role }, i) => (
              <div
                className="w-full max-w-xs rounded-2xl border border-border bg-bg-elevated p-5 shadow-[0_2px_12px_rgba(44,40,37,0.04)] transition-colors hover:border-border-focus"
                key={`${index}-${i}`}
              >
                <p className="text-[13px] leading-relaxed text-text-secondary">{text}</p>
                <div className="mt-4 flex items-center gap-3 border-t border-border/60 pt-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    width={38}
                    height={38}
                    src={image}
                    alt={name}
                    className="h-9 w-9 rounded-full border border-border object-cover"
                    loading="lazy"
                  />
                  <div className="flex flex-col">
                    <span className="text-[13px] font-semibold text-text-primary">{name}</span>
                    <span className="text-[11px] text-text-muted">{role}</span>
                  </div>
                </div>
              </div>
            ))}
          </React.Fragment>
        ))}
      </motion.div>
    </div>
  );
};

export const MOCK_TESTIMONIALS: TestimonialItem[] = [
  {
    text: "Hampir transfer biaya tiket 1,5 juta untuk panggilan interview BUMN di Bali. Pas dicek di Verifin, statusnya langsung BAHAYA karena email memakai domain gratisan dan nomornya terdeteksi modus travel penipuan.",
    image: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
    name: "Rizky Pratama",
    role: "Fresh Graduate Informatika",
  },
  {
    text: "Fitur pencocokan lokasinya juara. Alamat kantor yang tertera di poster ternyata ruko kosong saat dicek lewat validasi OpenStreetMap dan jejak digital Verifin.",
    image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
    name: "Dimas Wahyu",
    role: "Pencari Kerja & Freelancer",
  },
  {
    text: "Sebagai HR, nama perusahaan kami sering dicatut penipu loker via Telegram. Verifin sangat membantu calon pelamar membedakan kanal rekrutmen resmi dan kontak palsu.",
    image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
    name: "Sarah Anggraini",
    role: "Talent Acquisition Specialist",
  },
  {
    text: "Tinggal tempel link lowongan dari medsos, langsung keluar skor risiko lengkap dengan penjelasan bukti OSINT-nya. Tidak perlu menebak-nebak lagi.",
    image: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
    name: "Kevin Maulana",
    role: "Alumni Tech Bootcamp",
  },
  {
    text: "Sangat edukatif untuk mahasiswa yang baru pertama kali melamar magang. Graf penipuannya memperlihatkan nomor kontak yang sudah sering dilaporkan di kasus lain.",
    image: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
    name: "Nabila Putri",
    role: "Mahasiswi Kampus Merdeka",
  },
  {
    text: "Transparan banget karena ada Evidence Attribution. Kita tahu persis kenapa loker itu diklasifikasikan Waspada atau Bahaya, bukan blackbox AI.",
    image: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80",
    name: "Budi Santoso",
    role: "Career Consultant",
  },
  {
    text: "Biasanya ragu kalau nemu loker admin medsos dengan gaji tidak wajar. Begitu dites lewat fitur scan gambar poster, semua ketidaksesuaian langsung terdeteksi.",
    image: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=150&auto=format&fit=crop&q=80",
    name: "Amanda Citra",
    role: "Jobseeker Community Lead",
  },
  {
    text: "Platform yang sangat dibutuhkan saat maraknya modus loker fiktif berkedok like-and-share YouTube. Bukti digital footprint-nya akurat.",
    image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&auto=format&fit=crop&q=80",
    name: "Fajar Nugraha",
    role: "Pegiat Literasi Digital",
  },
  {
    text: "Proses verifikasinya cepat dan detail. Memberi rasa tenang sebelum mengirimkan CV dan data pribadi ke pihak perekrut.",
    image: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
    name: "Tiara Maharani",
    role: "Fresh Graduate Psikologi",
  },
];

const firstColumn = MOCK_TESTIMONIALS.slice(0, 3);
const secondColumn = MOCK_TESTIMONIALS.slice(3, 6);
const thirdColumn = MOCK_TESTIMONIALS.slice(6, 9);

export function Testimonials({ className }: { className?: string }) {
  return (
    <section className={cn("relative border-t border-border bg-bg px-4 py-16 sm:px-6 lg:py-24", className)}>
      <div className="mx-auto max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          viewport={{ once: true }}
          className="mx-auto mb-10 flex max-w-xl flex-col items-center text-center"
        >
          <span className="rounded-full border border-border bg-bg-elevated px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-text-muted">
            Uji Bukti & Testimoni Pengguna
          </span>

          <h2 className="mt-3 text-[1.4rem] font-semibold tracking-tight text-text-primary sm:text-3xl">
            Dipercaya para pencari kerja & praktisi
          </h2>
          <p className="mt-2 text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">
            Pengalaman nyata mereka yang telah menguji keabsahan lowongan kerja menggunakan Verifin sebelum melamar.
          </p>
        </motion.div>

        {/* 3 Kolom Marquee Vertikal dengan Gradien Mask Halus di Atas & Bawah */}
        <div className="flex justify-center gap-4 sm:gap-6 [mask-image:linear-gradient(to_bottom,transparent,black_15%,black_85%,transparent)] max-h-[580px] overflow-hidden">
          <TestimonialsColumn testimonials={firstColumn} duration={16} />
          <TestimonialsColumn testimonials={secondColumn} className="hidden md:block" duration={22} />
          <TestimonialsColumn testimonials={thirdColumn} className="hidden lg:block" duration={18} />
        </div>
      </div>
    </section>
  );
}

export default Testimonials;
