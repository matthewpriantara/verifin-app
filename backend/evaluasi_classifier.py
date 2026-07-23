"""
Evaluasi Layer-1 Fraud Classifier Verifin (classify_text) pada dataset berlabel.

JUJUR: Karena dataset EMSCAD tidak tersedia lokal saat eksekusi, evaluasi ini
memakai dataset berlabel yang disusun dari pola loker nyata:
  - Kelas AMAN (0): loker valid (gaya PT VIS, Sushi Yay, bimbel, F&B, korporat).
  - Kelas FRAUD (1): loker penipuan (gaya EMSCAD/TPPO/task-scam/deposit).

Metrik: Precision, Recall, F1, ROC-AUC (biner: fraud = BAHAYA/WASPADA sebagai
positif, AMAN sebagai negatif). Latency diukur per-sampel (ms).

Untuk evaluasi skala penuh, ganti SAMPLES dengan isi EMSCAD (kolom description +
label fraudulent), lalu jalankan ulang skrip ini.
"""
from __future__ import annotations
import json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.nlp.classifier import classify_text

# ── Dataset berlabel (text, label) ; label 1 = fraud, 0 = aman ─────────────
AMAN = [
    "PT Bank Central Asia Tbk membuka lowongan Relationship Officer. Minimal S1, pengalaman 1 tahun. Kirim CV ke karir@bca.co.id. Alamat: Menara BCA, Jakarta.",
    "Sushi Yay membuka lowongan Outlet Crew di Seturan & Godean, Yogyakarta. Posisi Kitchen & Service. Hubungi 0851-7415-6091 (Kayla). Kirim CV via bit.ly resmi kami.",
    "PT Visionary Internasional Solution membuka Desk Collection Operator. SMA/D3/S1, 0-2 tahun. Lokasi remote. Email ptvismajubersama@gmail.com, telp +628976927852.",
    "Lembaga bimbel Indonesia College (sejak 1993, Yogyakarta) membuka lowongan Video Editor & Admin. D3/Fresh graduate. Kirim CV, ijazah, lamaran ke hrd.indonesiacollege@gmail.com. Web indonesiacollege.co.id.",
    "PT Gudang Garam Tbk mencari Staff Quality Control. S1 Kimia/Teknik. Benefit BPJS, THR. Lamar melalui portal karir resmi gudanggaram.com. Kediri, Jawa Timur.",
    "Tokopedia membuka Software Engineer (Backend). Min 2 tahun pengalaman Go/Python. Apply via jobs.tokopedia.com. Kantor Jakarta Selatan.",
    "Rumah Sakit Sardjito membuka lowongan Perawat. D3 Keperawatan, STR aktif. Kirim berkas ke HRD RS Sardjito Yogyakarta. Seleksi tertulis & wawancara.",
    "PT Telkom Indonesia Witel Yogyakarta membuka lowongan Teknisi Fiber. SMK TKJ. Lamar via rekrutmen.telkom.co.id. Alamat Jl. Kusumanegara Yogyakarta.",
    "Hotel Tentrem Yogyakarta membuka Front Office Staff. D3 Perhotelan, English aktif. Kirim CV ke hrm@hoteltentrem.com. Walk-in interview setiap Rabu.",
    "Kantor Akuntan Publik membuka Junior Auditor. S1 Akuntansi, IPK min 3.0. Email rekrutmen@kaprekanan.co.id. Jakarta. Ada training bersertifikat.",
    "PT Matahari Department Store membuka Sales Associate. SMA/SMK, ramah, siap shift. Lamar langsung ke toko atau via matahari.co.id/karir.",
    "Startup edutech membuka Content Writer. Fresh graduate welcome. Portofolio wajib. Email hr@edutech.id. Remote, gaji sesuai UMR.",
]
FRAUD = [
    "LOWONGAN LUAR NEGERI GAJI 25-50 JUTA dibayar Dollar! Tanpa pengalaman tanpa ijazah. Tiket & visa ditanggung. Bayar biaya pendaftaran Rp 350.000 dan uang jaminan Rp 1.500.000 ke rekening HRD. WA 081234567890.",
    "Kerja santai dari rumah, gaji 15 juta/minggu, penghasilan tak terbatas! Cukup like & subscribe. Wajib deposit awal untuk buka tugas harian. Bayar paket member 500rb (Silver)/2jt (Gold). Bonus referral 20%.",
    "Dibutuhkan TKI ke Kamboja Myanmar, gaji USD besar. Semua biaya ditanggung. Cukup bayar biaya administrasi & seragam lalu transfer uang jaminan. Daftar via WA, kuota terbatas!",
    "Lowongan Data Entry WFH gaji fantastis 20 juta. Tanpa syarat. Aktivasi akun kerja cukup bayar Rp 500.000 dulu. Langsung kerja hari ini juga tanpa interview.",
    "Jadi reseller sukses penghasilan unlimited! Modal awal hanya 300rb untuk starter kit. Ajak teman dapat komisi 25%. Gaji mingguan jutaan rupiah.",
    "Dicari admin CS online kerja luar negeri, gaji 30 juta. Tidak perlu ijazah. Kirim uang muka 1 juta untuk proses visa kerja gratis. Hubungi admin via Telegram.",
    "Lowongan kerja part time ketik captcha, 5 juta/minggu. Daftar sekarang langsung via WA. Ada biaya pendaftaran 150rb untuk ID member. Gaji cair tiap hari.",
    "PT ABADI MENARI GROUP buka lowongan gaji 40 juta. Kerja dari HP saja. Wajib transfer uang jaminan 2 juta untuk training. Setelah transfer langsung berangkat kerja ke Malaysia.",
    "Kesempatan emas jadi jutawan! Bisnis online tanpa produk. Deposit sekali seumur hidup 1 juta, passive income tiap bulan. Sistem binary, ajak 2 orang dapat bonus.",
    "Lowongan operator judi online luar negeri, gaji dollar tinggi, fasilitas mewah. Semua ditanggung. Cukup bayar biaya medical check up 800rb di awal. Berangkat minggu ini.",
    "Dicari pengetik online, gaji 10 juta tanpa pengalaman. Daftar via link ini. Biaya registrasi 200rb untuk akun premium agar bisa mulai kerja. Garansi uang kembali.",
    "Kerja input data dari rumah, komisi besar tiap hari. Wajib top up saldo dulu untuk unlock tugas VIP. Makin besar top up makin besar komisi. Withdraw kapan saja.",
]
SAMPLES = [(t, 0) for t in AMAN] + [(t, 1) for t in FRAUD]

def main():
    y_true, y_pred, scores, lat = [], [], [], []
    for text, label in SAMPLES:
        t0 = time.perf_counter()
        out = classify_text(text)
        lat.append((time.perf_counter() - t0) * 1000)
        pred = 1 if out["label"] in ("BAHAYA", "WASPADA") else 0
        y_true.append(label); y_pred.append(pred); scores.append(out["nlp_score"])

    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
    p = precision_score(y_true, y_pred, zero_division=0)
    r = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    try: auc = roc_auc_score(y_true, scores)
    except Exception: auc = None
    cm = confusion_matrix(y_true, y_pred).tolist()
    result = {
        "dataset": "Berlabel internal (12 AMAN + 12 FRAUD), pola loker nyata & EMSCAD-style",
        "note": "BUKAN EMSCAD penuh (dataset tidak tersedia lokal). Untuk skala penuh, ganti SAMPLES dgn EMSCAD.",
        "n_samples": len(SAMPLES),
        "positif_fraud": sum(y_true), "negatif_aman": len(y_true)-sum(y_true),
        "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3),
        "roc_auc": round(auc, 3) if auc else None,
        "confusion_matrix_[tn,fp,fn,tp]": cm,
        "latency_ms_avg": round(sum(lat)/len(lat), 2),
        "latency_ms_max": round(max(lat), 2),
        "komponen": "Layer-1 classify_text (rule-based behavioral, bukan LLM)",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out_path = "/Users/fizualstd/Documents/GitHub/_LOMBA/gemastik19/test/hasil-test-raw/evaluasi-emscad.json"
    with open(out_path, "w") as f: json.dump(result, f, ensure_ascii=False, indent=2)
    print("\nDisimpan ke:", os.path.normpath(out_path))

if __name__ == "__main__":
    main()
