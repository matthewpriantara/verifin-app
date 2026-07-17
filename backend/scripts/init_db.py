import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgres_client import engine, SessionLocal, Base
from app.database.models import AhuWhitelist


def init_db():
    print("=== Initializing PostgreSQL Database ===")

    try:
        print("Creating tables (job_cases, ahu_whitelist)...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        return

    print("Checking whitelist seed data...")
    db = SessionLocal()
    try:
        count = db.query(AhuWhitelist).count()
        if count == 0:
            initial_companies = [
                {"company_name": "PERTAMINA PERSERO", "legal_type": "PT"},
                {"company_name": "TELEKOMUNIKASI INDONESIA", "legal_type": "PT"},
                {"company_name": "BANK RAKYAT INDONESIA", "legal_type": "PT"},
                {"company_name": "BANK CENTRAL ASIA", "legal_type": "PT"},
                {"company_name": "INDOMARCO PRISMATAMA", "legal_type": "PT"},
                {"company_name": "SUMBER ALFARIA TRIJAYA", "legal_type": "PT"},
                {"company_name": "GOJEK TOKOPEDIA", "legal_type": "PT"},
                {"company_name": "MANDIRI SEJAHTERA", "legal_type": "CV"},
            ]
            print(f"Adding {len(initial_companies)} companies to whitelist...")
            for comp in initial_companies:
                db.add(
                    AhuWhitelist(
                        company_name=comp["company_name"],
                        legal_type=comp["legal_type"],
                    )
                )
            db.commit()
            print("Database successfully seeded.")
        else:
            print(f"Whitelist already has {count} entries. Skipping seeding.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

    print("=== Database Initialization Finished ===")


if __name__ == "__main__":
    init_db()
