import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privasi" };

// Isi halaman ini harus mengikuti perilaku sistem yang sebenarnya (backend/app). Ubah bersamaan
// bila alur penyimpanan atau pihak ketiga berubah.
const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Data yang disimpan saat kamu memeriksa lowongan",
    items: [
      "Teks lowongan (maksimal 2.000 karakter pertama), atau teks hasil pembacaan poster dan tautan.",
      "Entitas yang terbaca: nama perusahaan, nomor HP, email, tautan, alamat, dan gaji.",
      "Hasil pemeriksaan sumber publik, skor, dan alasannya. Data ini dipakai untuk membuka ulang laporan, mempercepat pemeriksaan lowongan yang sama, dan mencocokkan nomor atau email dengan kasus lain.",
      "Gambar poster yang kamu unggah dihapus setelah selesai dibaca dan tidak disimpan.",
    ],
  },
  {
    title: "Data yang disimpan saat kamu mengirim laporan komunitas",
    items: [
      "Isian formulir: nama perusahaan, nomor, email, tautan, jenis modus, kronologi, dan gambar bukti bila diunggah.",
      "Alamat IP pengirim, untuk mencegah laporan berulang. IP dan catatan moderator hanya terlihat oleh admin.",
      "Laporan baru tampil ke publik dan dipakai sebagai bukti setelah disetujui admin.",
    ],
  },
  {
    title: "Pihak lain yang menerima sebagian data",
    items: [
      "Model bahasa (LLM) eksternal menerima teks lowongan untuk ekstraksi dan penalaran. Sebelum dikirim, nomor HP, bagian depan email, NIK, dan nomor rekening diganti token.",
      "Kaspersky Who Calls menerima nomor HP yang diperiksa.",
      "GetContact menerima nomor HP yang diperiksa. Verifin hanya memakai jumlah tag dan label spam; nama pemilik dan isi tag tidak disimpan atau ditampilkan. Layanan ini uji coba dan bisa dimatikan.",
      "OpenStreetMap (Nominatim) menerima alamat atau wilayah yang tertulis di lowongan.",
      "Mesin pencari SearXNG yang dijalankan tim menerima nama perusahaan dan nomor.",
      "Situs pada tautan lowongan dibuka oleh server Verifin, bukan oleh perangkatmu.",
    ],
  },
  {
    title: "Yang tidak dilakukan Verifin",
    items: [
      "Tidak ada akun, login, atau pelacakan iklan.",
      "Riwayat di halaman beranda disimpan di browser kamu sendiri dan bisa dihapus kapan saja dari tombol hapus di daftar riwayat.",
      "Pencarian publik di halaman Cari hanya menampilkan ringkasan kasus, tanpa teks lowongan, nomor, atau email.",
    ],
  },
  {
    title: "Penyimpanan",
    items: [
      "Belum ada penghapusan otomatis berbasis waktu. Data disimpan sampai dihapus oleh tim.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="text-balance text-2xl font-semibold tracking-tight text-text-primary sm:text-[28px]">
        Privasi dan data
      </h1>
      <p className="mt-3 text-[14px] leading-relaxed text-text-secondary">
        Halaman ini menjelaskan data apa yang disimpan Verifin, untuk apa, dan siapa saja yang ikut menerimanya.
      </p>
      <div className="mt-8 space-y-8">
        {SECTIONS.map((section) => (
          <section key={section.title}>
            <h2 className="text-[16px] font-semibold text-text-primary">{section.title}</h2>
            <ul className="mt-3 space-y-2">
              {section.items.map((item) => (
                <li key={item} className="flex gap-2.5 text-[14px] leading-relaxed text-text-secondary">
                  <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
