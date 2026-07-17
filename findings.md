# Findings: Verifin Database Configuration

## Stack Components & Versions
- **Backend framework**: FastAPI
- **ORM**: SQLAlchemy==2.0.28
- **PostgreSQL Driver**: psycopg2-binary==2.9.9
- **Required Extension**: `pgvector` for semantic search (384-dimensional vectors)

## PostgreSQL Schema Requirements (from PRD)
### Table: `job_cases`
- `id`: UUID (Primary Key)
- `raw_text_hash`: VARCHAR(64) (Unique, SHA-256 hash of sanitized job post text)
- `embedding`: VECTOR(384) (Representing job description text)
- `verdict`: VARCHAR(10) (AMAN, WASPADA, BAHAYA)
- `risk_score`: INT (0 to 100)
- `llm_output`: JSONB (reasons, risk_factors, safe_factors, recommendations, explainable_ai)
- `osint_failed`: BOOLEAN
- `created_at`: TIMESTAMP

### Table: `ahu_whitelist`
- `id`: SERIAL (Primary Key)
- `company_name`: VARCHAR(255)
- `legal_type`: VARCHAR(10) (PT or CV)
- `synced_at`: TIMESTAMP

## Infrastructure Details
- **Docker Image for Postgres**: `pgvector/pgvector:16-pgvector` (official image that includes pgvector pre-installed)
- **Default Port**: 5432
- **Redis Port**: 6379
- **Neo4j Port**: 7474 (HTTP) / 7687 (Bolt)
