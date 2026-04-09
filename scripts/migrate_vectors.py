import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_vectors():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        return

    print(f"[*] Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            print("[*] Checking 'chunks' table for 'embedding' column...")
            
            # Check current dimension
            check_sql = text("""
                SELECT atttypmod 
                FROM pg_attribute 
                WHERE attrelid = 'chunks'::regclass 
                AND attname = 'embedding';
            """)
            result = conn.execute(check_sql).fetchone()
            
            if result:
                # pgvector typmod for Vector(dim) is dim
                current_dim = result[0]
                print(f"[*] Current embedding dimension: {current_dim}")
                
                if current_dim == 4096:
                    print("[!] Column already has dimension 4096. No migration needed.")
                    return
                
                print(f"[*] Migrating dimension {current_dim} -> 4096...")
                print("[*] WARNING: This will set all existing embeddings to NULL.")
                
                # We need to drop and recreate the column or cast it. 
                # Recreating is safer for pgvector typemod changes.
                conn.execute(text("ALTER TABLE chunks DROP COLUMN embedding;"))
                conn.execute(text("ALTER TABLE chunks ADD COLUMN embedding vector(4096);"))
                conn.commit()
                print("[+] Migration successful: 'chunks.embedding' is now vector(4096).")
            else:
                print("[!] Column 'embedding' not found in 'chunks' table.")
                
    except Exception as e:
        print(f"[!] Migration failed: {e}")

if __name__ == "__main__":
    migrate_vectors()
