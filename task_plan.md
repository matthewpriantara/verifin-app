# Task Plan: PostgreSQL Database Configuration for Verifin

## Goal
Configure and initialize the PostgreSQL database (with `pgvector` extension) using SQLAlchemy, setup Docker Compose for local database management (PostgreSQL, Neo4j, and Redis), and configure the backend app environment settings.

## Phases

### Phase 1: Docker Compose Setup
- [x] Create/Update `backend/docker-compose.yml` to orchestrate PostgreSQL (using pgvector image), Neo4j, and Redis.
- [x] Verify Docker Compose service definition validity.

### Phase 2: Environment Variables
- [x] Define environment variables template in `backend/.env.example`.
- [x] Create/Update local `backend/.env` with local dev credentials.

### Phase 3: Global Configuration (`app/config.py`)
- [x] Implement configuration loader in `backend/app/config.py`.
- [x] Expose database credentials (URL, port, username, password, db name).

### Phase 4: Package Dependencies & Postgres Client
- [x] Add `pgvector` to `backend/requirements.txt`.
- [x] Create connection session, engine, and Base declarations in `backend/app/database/postgres_client.py`.

### Phase 5: Database Models (`app/database/models.py`)
- [x] Create SQLAlchemy database models in `backend/app/database/models.py` for `job_cases` and `ahu_whitelist` tables.
- [x] Use `pgvector.sqlalchemy.Vector` for the `embedding` column (384 dimensions).

### Phase 6: Initialization and Database Migration Script
- [x] Create an initialization script `backend/scripts/init_db.py` to create tables and activate pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector`).
- [x] Implement basic seed function to add mock data to `ahu_whitelist` for verification.

### Phase 7: Verification & Testing
- [x] Run the docker-compose services.
- [x] Run `backend/scripts/init_db.py` to initialize tables.
- [x] Write a test script or endpoint integration test to confirm PostgreSQL connections work properly.
