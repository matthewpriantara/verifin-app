from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

# Create engine for PostgreSQL connection
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Configure database session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()

# FastAPI Dependency for obtaining a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
