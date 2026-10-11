# Verifin App — Codebase Guidelines & Context

Repositori ini adalah implementasi kode aplikasi **Verifin: Platform Deteksi Lowongan Kerja Palsu Berbasis AI & OSINT**.

## Hubungan dengan Dokumen Lomba (`gemastik19`)

- Repositori ini terhubung dengan repositori berkas lomba di: `../gemastik19` (atau parent path `/Users/fizualstd/Documents/GitHub/_LOMBA/gemastik19`).
- Segala spesifikasi fitur, batasan sistem, dan target kriteria merujuk pada berkas finalis di `../gemastik19/berkas-finalis/` dan `../gemastik19/proposal-verifin/`.

---

## Struktur Berkas Proyek

```text
.
├── .github/
│   └── workflows/
│       └── deploy.yml
├── .gitignore
├── AGENTS.md
├── docker-compose.yml
├── backend/
│   ├── .dockerignore
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── Dockerfile
│   ├── evaluasi_classifier.py
│   ├── evaluasi_emscad_full.py
│   ├── latih_tfidf_emscad.py
│   ├── main.py
│   ├── pyrightconfig.json
│   ├── pytest.ini
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── community/
│       │       │   ├── __init__.py
│       │       │   ├── router.py
│       │       │   └── schema.py
│       │       ├── health/
│       │       │   ├── __init__.py
│       │       │   └── router.py
│       │       └── verify/
│       │           ├── __init__.py
│       │           ├── pipeline.py
│       │           ├── router.py
│       │           └── schema.py
│       ├── database/
│       │   ├── models.py
│       │   └── postgres_client.py
│       └── services/
│           ├── __init__.py
│           ├── constants.py
│           ├── db_cache.py
│           ├── hasher.py
│           ├── ner.py
│           ├── ocr.py
│           ├── status_contract.py
│           ├── url_guard.py
│           ├── web_fetcher.py
│           ├── graph/
│           │   ├── __init__.py
│           │   └── fraud_network.py
│           ├── llm/
│           │   ├── __init__.py
│           │   ├── client.py
│           │   ├── entity_extraction.py
│           │   ├── prompt_builder.py
│           │   └── verifin_reasoning.py
│           ├── nlp/
│           │   ├── __init__.py
│           │   └── classifier.py
│           ├── osint/
│           │   ├── __init__.py
│           │   ├── address_validator.py
│           │   ├── ai_extractor.py
│           │   ├── company_validator.py
│           │   ├── gform_inspector.py
│           │   ├── lightpanda_client.py
│           │   ├── phone_validator.py
│           │   ├── platform_providers.py
│           │   ├── query_builder.py
│           │   ├── runner.py
│           │   ├── search_intelligence.py
│           │   ├── searxng_client.py
│           │   ├── social.py
│           │   ├── web_evidence.py
│           │   └── whois_handler.py
│           └── xai/
│               ├── __init__.py
│               └── shap_explainer.py
└── frontend/
    ├── .dockerignore
    ├── .env
    ├── .env.example
    ├── .gitignore
    ├── Dockerfile
    ├── e2e-complete.js
    ├── e2e-final.js
    ├── e2e-retry.js
    ├── e2e-screenshot.js
    ├── eslint.config.mjs
    ├── next.config.ts
    ├── package.json
    ├── pnpm-lock.yaml
    ├── pnpm-workspace.yaml
    ├── postcss.config.mjs
    ├── tsconfig.json
    ├── public/
    │   ├── brand/
    │   │   ├── 1x1_bg_black.svg
    │   │   ├── 1x1_bg_white.svg
    │   │   ├── 1x1_black_bg_transparant.svg
    │   │   ├── 1x1_white_bg_transparant.svg
    │   │   ├── logo_bg_black.svg
    │   │   ├── logo_bg_white.svg
    │   │   ├── logo_black_bg_transparant.svg
    │   │   └── logo_white_bg_transparant.svg
    │   ├── favicon.ico
    │   ├── icon.png
    │   └── icon.svg
    └── src/
        ├── app/
        │   ├── favicon.ico
        │   ├── globals.css
        │   ├── icon.png
        │   ├── icon.svg
        │   ├── layout.tsx
        │   ├── loading.tsx
        │   ├── page.tsx
        │   ├── admin/
        │   │   ├── loading.tsx
        │   │   └── page.tsx
        │   ├── api/
        │   │   └── admin/
        │   │       ├── login/
        │   │       │   └── route.ts
        │   │       └── session/
        │   │           └── route.ts
        │   ├── report/
        │   │   ├── page.tsx
        │   │   └── [caseId]/
        │   │       ├── loading.tsx
        │   │       └── page.tsx
        │   ├── report-job/
        │   │   ├── loading.tsx
        │   │   └── page.tsx
        │   └── verify/
        │       └── page.tsx
        ├── components/
        │   ├── report/
        │   │   ├── EntityPanel.tsx
        │   │   └── EvidencePanel.tsx
        │   └── ui/
        │       ├── Badge.tsx
        │       ├── Button.tsx
        │       ├── Logo.tsx
        │       ├── Skeleton.tsx
        │       └── testimonials-columns-1.tsx
        ├── lib/
        │   ├── admin.ts
        │   ├── api.ts
        │   └── utils.ts
        ├── modules/
        │   ├── admin/
        │   │   ├── AdminPage.tsx
        │   │   ├── ModerationTable.tsx
        │   │   └── ReportChart.tsx
        │   ├── home/
        │   │   ├── HomePage.tsx
        │   │   └── SearchHistory.tsx
        │   ├── layout/
        │   │   ├── Footer.tsx
        │   │   └── Navbar.tsx
        │   ├── report/
        │   │   ├── FactorList.tsx
        │   │   ├── ReportPage.tsx
        │   │   ├── RiskMeter.tsx
        │   │   └── ShapChart.tsx
        │   ├── report-job/
        │   │   └── ReportJobPage.tsx
        │   └── verify/
        │       └── VerifyBox.tsx
        └── types/
            ├── admin.ts
            ├── phosphor.d.ts
            └── verify.ts
```
