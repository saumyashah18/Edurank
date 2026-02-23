from backend.database.session import engine
from sqlalchemy import text

def migrate():
    print("[*] Running migration: Adding 'conceptual_gap' to 'transcripts'...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS conceptual_gap BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("[SUCCESS] Column added successfully.")
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")

if __name__ == "__main__":
    migrate()
