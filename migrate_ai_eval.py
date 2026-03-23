"""
Migration script: Add AI evaluation columns to quizzes and transcripts tables.
Supports both SQLite and PostgreSQL. Safe to run multiple times.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./aissociate.db")

migrations = [
    ("quizzes", "ai_eval_enabled", "BOOLEAN DEFAULT FALSE"),
    ("quizzes", "ai_eval_rubric", "TEXT"),
    ("transcripts", "ai_eval_results", "TEXT"),
]

if DB_URL.startswith("sqlite"):
    import sqlite3
    db_path = DB_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]
    print(f"Migrating SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for table, column, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"  ✅ Added {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"  ⏭️  {table}.{column} already exists, skipping")
            else:
                print(f"  ❌ Error: {e}")
    conn.commit()
    conn.close()

elif DB_URL.startswith("postgresql"):
    import psycopg2
    print(f"Migrating PostgreSQL database...")
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    for table, column, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}")
            print(f"  ✅ Added {table}.{column}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            conn.rollback()
    conn.commit()
    conn.close()

else:
    print(f"Unsupported DB: {DB_URL}")
    exit(1)

print("\nMigration complete!")
