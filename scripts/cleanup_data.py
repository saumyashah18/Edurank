import os
import sys
import shutil
from sqlalchemy import text
from typing import List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.session import engine, SessionLocal, init_db
from backend.database.models.base import Base

def cleanup_system():
    print("\n" + "="*50)
    print("   AIssociate SYSTEM CLEANUP & RESET")
    print("="*50 + "\n")

    # 1. Clear database completely
    print("[1/3] Dropping and recreating PostgreSQL database schema...")
    with engine.connect() as conn:
        try:
            # Terminate other connections
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'edurank_dev' AND pid <> pg_backend_pid();"))
            conn.commit()
            
            # Wipe everything
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            
            # Re-enable pgvector
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            print("      -> Schema wiped and vector extension re-enabled.")
        except Exception as e:
            print(f"      [!] Schema reset failed: {e}")
            return

    # 2. Re-import ALL models and create tables
    print("[2/3] Re-initializing tables and seeding default data...")
    # Import everything to ensure it's registered with Base.metadata
    from backend.database.models.user import User
    from backend.database.models.course import Course, Document
    from backend.database.models.hierarchy import Chapter, Section, Subsection, RawMaterial
    from backend.database.models.chunk import Chunk, KnowledgeRelation
    from backend.database.models.concept import Concept, ConceptRelation, ConceptChunk
    from backend.database.models.question import Question
    from backend.database.models.transcript import Quiz, Transcript
    
    # Actually create the tables
    Base.metadata.create_all(bind=engine)
    
    # Run the seed logic from session.py
    init_db()
    print("      -> Tables recreated and default professor/course seeded.")

    # 3. Clear Uploads folder
    print("[3/3] Clearing uploads directory...")
    # Prioritize root uploads/ folder
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    
    if os.path.exists(uploads_dir):
        files_deleted = 0
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                    files_deleted += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    files_deleted += 1
            except Exception as e:
                print(f"      [!] Failed to delete {item}: {e}")
        print(f"      -> {files_deleted} items removed from {uploads_dir}")
    else:
        # Fallback to backend/uploads if root doesn't exist
        uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "uploads"))
        if os.path.exists(uploads_dir):
            shutil.rmtree(uploads_dir)
            os.makedirs(uploads_dir)
            print(f"      -> Backend uploads directory cleared.")
        else:
            print("      -> No uploads directory found.")

    print("\n" + "="*50)
    print("   SYSTEM RESET COMPLETE! (Clean state)")
    print("="*50 + "\n")

if __name__ == "__main__":
    confirm = input("Are you SURE you want to delete ALL data and documents? (y/n): ")
    if confirm.lower() == 'y':
        cleanup_system()
    else:
        print("Cleanup cancelled.")
