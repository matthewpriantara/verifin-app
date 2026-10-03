# Verifin App — Codebase Guidelines & Context

Repositori ini adalah implementasi kode aplikasi **Verifin: Platform Deteksi Lowongan Kerja Palsu Berbasis AI & OSINT**.

## Hubungan dengan Dokumen Lomba (`gemastik19`)

- Repositori ini terhubung dengan repositori berkas lomba di: `../gemastik19` (atau parent path `/Users/fizualstd/Documents/GitHub/_LOMBA/gemastik19`).
- Segala spesifikasi fitur, batasan sistem, dan target kriteria merujuk pada berkas finalis di `../gemastik19/berkas-finalis/` dan `../gemastik19/proposal-verifin/`.

---

## Pembagian Kerja & Branch Tim

- **`origin/main`:** Branch utama untuk deployment bersama.
- **`hafidz` / `origin/hafidz` (User saat ini):** Core pipeline (`backend/app/api/v1/verify/pipeline.py`), OSINT modules (`phone_validator.py`, `company_validator.py`, `whois_handler.py`), LLM reasoning & scoring.
- **`akmal/dev`:** OCR poster recognition, Instagram scraper, NER extraction.
- **`matthew/dev` & `matthew/fix-frontend`:** Frontend Next.js UI, layout, styling, Admin page.

## Aturan Git
- Hindari commit langsung ke `main` lokal tanpa menyelaraskan dengan `origin/main`.
- Kerjakan perubahan pada branch `hafidz`.
