# Proposal & Arsitektur Sistem: Verifin (Hybrid Architecture v2)

## 1. Visi

Verifin adalah platform verifikasi lowongan kerja berbasis Hybrid AI Architecture yang menggabungkan:

- Rules-Based Orchestrator
- OSINT
- Local LLM (Hermes via Ollama)
- Knowledge Graph
- AI Case Memory
- Explainable AI

Tujuan utama adalah memberikan verifikasi real-time sekaligus membuat sistem yang semakin pintar setiap kali ada kasus baru.

---

# 2. Prinsip Arsitektur

## Real-Time Layer
Menangani permintaan pengguna secara deterministik.

Pipeline:

User → OCR → IndoBERT NER → Rules Engine → Live OSINT → Hermes → Dashboard

LLM tidak memilih tool.

---

## Background Intelligence Layer

Berjalan asynchronous menggunakan worker.

- Job Scraper
- Government Sync
- Domain Hunter
- Reputation Hunter
- Pattern Hunter
- Knowledge Builder

Semua agent memperkaya Knowledge Graph tanpa mengganggu request pengguna.

---

# 3. AI Case Memory

## Tujuan

Menghindari investigasi berulang pada kasus yang sama atau sangat mirip.

## Konsep

Setiap hasil investigasi disimpan sebagai sebuah Case.

Case berisi:

- Input asli
- Teks normalisasi
- Entity
- Hasil OSINT
- Hasil Hermes
- Risk Score
- Confidence
- Timestamp

---

# 4. Storage Architecture

## PostgreSQL

Menjadi database utama (Single Source of Truth).

Menyimpan:

- User
- Cases
- OCR Result
- Entity
- OSINT Result
- Hermes Result
- Audit Log
- Feedback

Jika menggunakan pgvector:

- Embedding setiap kasus
- Semantic Search

---

## Neo4j

Knowledge Graph.

Node:

- Company
- Phone
- Domain
- Address
- Email
- Job Posting
- User Report

Relationship:

- USES_PHONE
- USES_DOMAIN
- LOCATED_AT
- RELATED_TO
- REPORTED_BY

---

## Redis

Fast Cache.

Digunakan untuk:

- Fingerprint cache
- Session cache
- Queue
- Rate limit

TTL dapat diatur (misalnya 7 hari).

---

# 5. Semantic Case Memory

Alur:

1. User upload.
2. OCR.
3. NER.
4. Fingerprint.
5. Redis Lookup.

Jika ditemukan:

Return hasil sebelumnya.

Jika tidak:

Cari kemiripan menggunakan pgvector.

Jika similarity tinggi (misal >95%):

Reuse hasil investigasi.

Jika tidak ada:

Jalankan investigasi penuh.

---

# 6. Live Investigation Pipeline

User

↓

OCR (PaddleOCR)

↓

NER (IndoBERT)

↓

Rules Engine

↓

OSINT Collector

- WHOIS
- AHU
- Maps
- SPF/DMARC
- Reputation Lookup

↓

Hermes (Ollama)

↓

Risk Score

↓

Neo4j

↓

PostgreSQL

↓

Redis Cache

↓

Dashboard

---

# 7. Background Workers

## Government Sync

Sinkronisasi data AHU, OSS, BP2MI ke database lokal.

## Job Scraper

Mengambil lowongan dari berbagai portal.

## Domain Hunter

Mendeteksi domain recruitment baru.

## Reputation Hunter

Mengumpulkan reputasi nomor HP, email, rekening.

## Pattern Hunter

Clustering pada Neo4j untuk menemukan pola sindikat.

## Knowledge Builder

Menggunakan Hermes untuk merangkum pola scam baru dan memperbarui knowledge base.

---

# 8. Peran Hermes

Hermes hanya digunakan untuk:

- Reasoning
- Risk Assessment
- Explainable AI
- Recommendation
- Knowledge Summary

Hermes TIDAK:

- OCR
- Scraping
- Memilih tool
- Workflow orchestration

---

# 9. Arsitektur Ringkas

Frontend (Next.js)

↓

Backend API

↓

Rules-Based Orchestrator

↓

OCR + IndoBERT

↓

Redis Cache

↓

Fingerprint + Semantic Search

↓

Live OSINT

↓

Hermes

↓

Storage

- PostgreSQL
- Neo4j
- Redis
- pgvector

↓

Dashboard

Background:

Celery Workers

↓

Job Scraper
Government Sync
Domain Hunter
Reputation Hunter
Pattern Hunter
Knowledge Builder

↓

Knowledge Graph

---

# 10. Keunggulan

- Latensi rendah.
- Token LLM lebih hemat.
- Reuse investigasi lama.
- Semantic similarity.
- Knowledge Graph terus berkembang.
- Mudah diskalakan.
- Production-ready.
- Cocok untuk Gemastik maupun implementasi nyata.

---

# 11. Rekomendasi Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Frontend | Next.js |
| Backend | FastAPI / NestJS |
| OCR | PaddleOCR |
| NER | IndoBERT |
| Rules | Python Rules Engine |
| LLM | Ollama + Hermes |
| Relational DB | PostgreSQL |
| Semantic Search | pgvector |
| Graph DB | Neo4j |
| Cache & Queue | Redis |
| Worker | Celery |
| GNN | PyTorch Geometric |
| Explainable AI | SHAP |

---

# 12. Kesimpulan

Verifin menggunakan Hybrid AI Architecture dengan pemisahan yang jelas antara Rules Engine, Live OSINT, AI Reasoning, Background Intelligence, dan AI Case Memory. Pendekatan ini memungkinkan sistem memberikan respons cepat, mengurangi investigasi yang berulang, serta membangun basis pengetahuan yang terus berkembang seiring bertambahnya laporan pengguna.
