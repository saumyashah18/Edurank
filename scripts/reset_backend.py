import os
import shutil
from sqlalchemy import text
from backend.database.session import SessionLocal

def reset_backend():
    print("[*] Starting full backend reset...")
    
    # 1. Wipe Database Tables (PostgreSQL)
    db = SessionLocal()
    try:
        print("[*] Wiping database tables...")
        # Order matters for foreign keys, so we use CASCADE
        tables = [
            "transcripts", "questions", "quizzes", "knowledge_relations", 
            "chunks", "raw_materials", "subsections", "sections", "chapters", 
            "courses", "users"
        ]
        
        for table in tables:
            try:
                db.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                print(f"    - Cleared {table}")
            except Exception as e:
                print(f"    - Skip/Error on {table}: {e}")
        
        db.commit()
        print("[+] Database wiped successfully.")
    except Exception as e:
        print(f"[!] Database wipe failed: {e}")
        db.rollback()
    finally:
        db.close()

    # 2. Clear FAISS Index
    print("[*] Clearing FAISS index...")
    faiss_dir = "faiss_index"
    if os.path.exists(faiss_dir):
        shutil.rmtree(faiss_dir)
        os.makedirs(faiss_dir)
        print("[+] FAISS index cleared.")
    else:
        os.makedirs(faiss_dir)
        print("[+] FAISS index directory created.")

    # 3. Delete Uploads
    print("[*] Deleting uploaded files...")
    uploads_dir = "uploads"
    if os.path.exists(uploads_dir):
        for filename in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"    - Failed to delete {file_path}: {e}")
        print("[+] Uploads directory cleared.")
    else:
        os.makedirs(uploads_dir)
        print("[+] Uploads directory created.")

    print("\n[✔] FULL RESET COMPLETE. The backend is now in a clean state.")

if __name__ == "__main__":
    confirm = input("Are you SURE you want to delete ALL data? (y/n): ")
    if confirm.lower() == 'y':
        reset_backend()
    else:
        print("Reset cancelled.")
