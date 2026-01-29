import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def fix_postgres_schema():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not db_url.startswith("postgresql"):
        print("DATABASE_URL is not set to PostgreSQL. Skipping SQL schema fix.")
        return

    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("Applying Foreign Key Cascades...")
        
        # 1. Update knowledge_relations table (source_id)
        print("Updating knowledge_relations(source_id)...")
        conn.execute(text("""
            ALTER TABLE knowledge_relations 
            DROP CONSTRAINT IF EXISTS knowledge_relations_source_id_fkey,
            ADD CONSTRAINT knowledge_relations_source_id_fkey 
            FOREIGN KEY (source_id) REFERENCES chunks(id) ON DELETE CASCADE;
        """))
        
        # 2. Update knowledge_relations table (target_id)
        print("Updating knowledge_relations(target_id)...")
        conn.execute(text("""
            ALTER TABLE knowledge_relations 
            DROP CONSTRAINT IF EXISTS knowledge_relations_target_id_fkey,
            ADD CONSTRAINT knowledge_relations_target_id_fkey 
            FOREIGN KEY (target_id) REFERENCES chunks(id) ON DELETE CASCADE;
        """))
        
        # 3. Update questions table (chunk_id)
        print("Updating questions(chunk_id)...")
        conn.execute(text("""
            ALTER TABLE questions 
            DROP CONSTRAINT IF EXISTS questions_chunk_id_fkey,
            ADD CONSTRAINT questions_chunk_id_fkey 
            FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
        """))
        
        # 4. Update questions table (subsection_id)
        print("Updating questions(subsection_id)...")
        conn.execute(text("""
            ALTER TABLE questions 
            DROP CONSTRAINT IF EXISTS questions_subsection_id_fkey,
            ADD CONSTRAINT questions_subsection_id_fkey 
            FOREIGN KEY (subsection_id) REFERENCES subsections(id) ON DELETE CASCADE;
        """))
        
        conn.commit()
        print("Successfully applied Foreign Key Cascades!")

if __name__ == "__main__":
    fix_postgres_schema()
