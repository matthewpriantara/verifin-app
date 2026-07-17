import sys
import os

# Add parent directory of scripts to python system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgres_client import SessionLocal
from app.database.models import AhuWhitelist

def test_connection():
    print("=== Testing PostgreSQL Connection & Query ===")
    db = SessionLocal()
    try:
        companies = db.query(AhuWhitelist).all()
        print(f"✅ Connection successful! Found {len(companies)} whitelisted companies:")
        for comp in companies:
            print(f"  - [{comp.legal_type}] {comp.company_name} (synced: {comp.synced_at})")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nPlease ensure that:")
        print("  1. Docker Desktop is running.")
        print("  2. Database containers are active (`docker-compose up -d`).")
        print("  3. You have initialized the database (`python scripts/init_db.py`).")
    finally:
        db.close()
    print("=============================================")

if __name__ == "__main__":
    test_connection()
