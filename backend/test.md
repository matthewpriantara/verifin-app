# Verifin API — Test Cases

Base URL: `http://localhost:8000`

## Jalankan server

```bash
cd ~/Documents/GitHub/_LOMBA/gemastik19/verifin-app
git pull origin main
cd backend && source .venv311/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Test 1 — PT. Visionary Internasional Solution (WASPADA expected)

Loker debt collector remote, email Gmail, no alamat fisik, legalitas tidak terverifikasi.

```bash
curl -s -X POST http://localhost:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "PT. Visionary Internasional Solution (PT. VIS)\nmembuka lowongan\nDesk Collection Operator\n\nBesaran Gaji: 2,8 - 9 Juta\nLokasi Kerja: Bebas/Remote Work\n\nEmail: ptvismajubersama@gmail.com\nNo. Telepon: +628976927852"
  }' | python3 -m json.tool
```

**Expected:**
- `verdict`: `WASPADA`
- `risk_score`: ~52
- `phones[0].category`: `NETRAL`
- `phones[0].checked`: `true`
- `platform_hits.instagram`: `true`
- `feature_contributions`: terisi (no_address + free_email_only)

---

## Test 2 — Admin Finance & Stock Part Time Jogja (AMAN expected)

Loker part time UMKM lokal, kontak WA, jobdesk jelas, no red flag.

```bash
curl -s -X POST http://localhost:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "HIRING PART TIME – Admin Finance & Stock (Jogja)\n\nJobdesk:\n- Rekap pemasukan & pengeluaran\n- Stock opname\n- Tutup buku 2 mingguan/bulanan\n- Membuat laporan keuangan sederhana\n\nSyarat:\n- Teliti, jujur, bertanggung jawab\n- Menguasai Excel/Google Sheets\n- Paham pembukuan dasar\n- Diutamakan mahasiswa/lulusan Akuntansi atau Manajemen\n- Berdomisili di Jogja\n\nSistem kerja: Part time (±2 kali/bulan)\nFee dibahas saat interview\n\nKirim CV via WhatsApp: 081914784704"
  }' | python3 -m json.tool
```

**Expected:**
- `verdict`: `AMAN` atau `WASPADA` ringan
- `risk_score`: < 40
- Tidak ada `risk_factors` terkait biaya/data sensitif

---

## Test 3 — Sushi Yay! Outlet Crew Jogja (AMAN expected)

Loker F&B brand lokal, lokasi fisik jelas (Godean & Seturan), kualifikasi wajar, ada shortlink CV.

```bash
curl -s -X POST http://localhost:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "WE ARE HIRING – Sushi Yay! Team\n\nPosisi: Kitchen (Spv, Lead, Cook Crew, Cook Helper, Steward), Service (Manager Store, Leader, Cashier, Crew of Service)\n\nLokasi: Godean Yogyakarta & Seturan Yogyakarta\n\nKualifikasi:\n- Usia minimal 18 tahun\n- Pendidikan min SMA/SMK\n- Non pengalaman untuk Crew of Service & Steward\n- Pengalaman 6 bulan untuk Cook Helper\n- Pengalaman 1 tahun untuk Cashier dan Cook Crew\n- Pengalaman 2 tahun untuk Leader, Supervisor, Store Manager\n\nHubungi: 0851-7415-6091 (Kayla)\nKirim CV: bit.ly/FormLamaranKerjayaygroup"
  }' | python3 -m json.tool
```

**Expected:**
- `verdict`: `AMAN` atau `WASPADA` ringan
- `risk_score`: < 35
- `entities.addresses`: terisi (Godean / Seturan Yogyakarta)
- Tidak ada fraud flags

---

## Checklist pipeline per response

| Field | Cek |
|-------|-----|
| `verdict` | Bukan `ERROR` |
| `risk_score` | > 0 (kecuali memang aman) |
| `model_used` | `claude-sonnet-4.6 (Forensic Reasoning)` |
| `phones[].checked` | `true` jika ada nomor HP |
| `phones[].category` | `NETRAL` / `BERBAHAYA` / `SPAM` (bukan null) |
| `feature_contributions` | Tidak kosong `[]` |
| `waterfall_chart` | Cumulative sesuai risk_score |
| `shap_explanation.verdict` | Sama dengan top-level `verdict` |
| `osint.timing.osint_parallel_sec` | < 15s |
