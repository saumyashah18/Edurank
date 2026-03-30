from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Assuming default DB path or env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./backend/app.db")
# If it's postgres, we might need to adjust, but let's try the local path first if it exists, or check environment.
# The user's metadata suggests a standard setup. Let's look at .env if we fail.

# Using Postgres from .env
DATABASE_URL = "postgresql://postgres:Sam181204@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Check Chunks
    total_chunks = session.execute(text("SELECT COUNT(*) FROM chunks")).scalar()
    print(f"Total Chunks: {total_chunks}")

    # Check Authors from Documents
    print("\n--- IDENTIFIED AUTHORS ---")
    authors = session.execute(text("SELECT DISTINCT author FROM documents WHERE author IS NOT NULL")).fetchall()
    if authors:
        for auth_row in authors:
            auth = auth_row[0]
            count = session.execute(text(
                "SELECT COUNT(*) FROM chunks c JOIN documents d ON c.document_id = d.id WHERE d.author = :auth"
            ), {"auth": auth}).scalar()
            print(f"- {auth}: {count} chunks")
    else:
        print("No authors identified yet.")

    # Check Relations
    print("\n--- KNOWLEDGE RELATIONS ---")
    rel_count = session.execute(text("SELECT COUNT(*) FROM knowledge_relations")).scalar()
    print(f"Total Knowledge Relations: {rel_count}")
    
    if rel_count > 0:
        sample = session.execute(text("SELECT * FROM knowledge_relations LIMIT 5")).fetchall()
        print("Sample Relations:", sample)
        
except Exception as e:
    print(f"Error: {e}")
finally:
    session.close()
