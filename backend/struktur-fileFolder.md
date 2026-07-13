verifin-backend/
├── docker-compose.yml              # Orchestration database (Neo4j, PostgreSQL, Redis)
├── .env                            # Environment variables
├── .env.example                    # Template env
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image untuk backend service
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # Konfigurasi global (database, settings)
│   ├── constants.py                # Konstanta dan enum
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── verify/             # Endpoint verifikasi
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   └── schema.py       # Request/Response models
│   │   │   ├── dashboard/          # Endpoint dashboard & admin
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   └── schema.py
│   │   │   └── health/
│   │   │       └── router.py       # Health check endpoint
│   │
│   ├── services/                   # Business logic & AI services
│   │   ├── __init__.py
│   │   ├── ocr.py                  # PaddleOCR integration
│   │   ├── ner.py                  # IndoBERT NER extraction
│   │   ├── osint/
│   │   │   ├── __init__.py
│   │   │   ├── whois_handler.py    # Domain WHOIS check
│   │   │   ├── email_security.py   # SPF/DMARC verification
│   │   │   ├── phone_validator.py  # Phone reputation check
│   │   │   ├── address_validator.py # Location verification
│   │   │   └── company_validator.py # PT legality check
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── hermes_reasoner.py  # Ollama/Hermes integration
│   │   │   └── prompt_builder.py   # Structured prompt engineering
│   │   ├── xai/
│   │   │   ├── __init__.py
│   │   │   └── shap_explainer.py   # SHAP value interpretation
│   │   └── graph/
│   │       ├── __init__.py
│   │       └── neo4j_handler.py    # Neo4j operations
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── neo4j_client.py         # Neo4j connection pool
│   │   ├── postgres_client.py      # PostgreSQL ORM (SQLAlchemy)
│   │   ├── redis_client.py         # Redis cache client
│   │   └── models.py               # SQLAlchemy models
│   │
│   ├── workers/                    # Celery async tasks
│   │   ├── __init__.py
│   │   ├── tasks.py                # Task definitions
│   │   └── scrapers.py             # Web scraper tasks
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                 # Authentication middleware
│   │   └── error_handler.py        # Global error handling
│   │
│   └── utils/
│       ├── __init__.py
│       ├── encryption.py           # SHA-256 hashing untuk data sensitif
│       ├── logger.py               # Logging utility
│       └── validators.py           # Input validation helpers
│
├── scripts/
│   ├── init_db.py                  # Initialize database schema
│   ├── seed_data.py                # Populate seed data
│   └── load_models.py              # Download & cache AI models
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── conftest.py                 # pytest fixtures
│
├── logs/                           # Log directory (gitignored)
├── models/                         # Cached AI models (gitignored)
└── README.md