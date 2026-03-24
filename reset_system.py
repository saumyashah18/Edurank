import os
import sys
import shutil

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import text
from backend.database.session import engine, init_db

def reset_system():
    # 1. Clear database completely
    print("Dropping all PostgreSQL tables and vectors...")
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'edurank_dev' AND pid <> pg_backend_pid();"))
        conn.commit()
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        # pgvector extension needs to be recreated in the public schema
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    
    # Re-initialize via session.py
    init_db()
    print("Database recreated and seeded with default professor profile.")

    # 2. Clear Uploads folder
    uploads_dir = os.path.join(os.path.dirname(__file__), "backend", "uploads")
    if os.path.exists(uploads_dir):
        print(f"Clearing uploads directory: {uploads_dir}")
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"Failed to delete {item_path}: {e}")
    else:
        print("No uploads directory found to clear.")

if __name__ == "__main__":
    reset_system()
    print("SYSTEM RESET COMPLETE!")
