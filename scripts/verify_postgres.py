import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from backend.database.session import SessionLocal, init_db
from backend.database.models.user import User

def verify_postgres():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    print(f"Connecting to: {db_url}")
    
    try:
        # 1. Test engine connection
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            print(f"PostgreSQL Version: {result.fetchone()[0]}")
        
        # 2. Test session and seeded data
        db = SessionLocal()
        user = db.query(User).filter_by(username="professor").first()
        if user:
            print(f"Found seeded user: {user.username} with role {user.role}")
        else:
            print("Professor user not found. Checking if init_db was successful...")
            init_db()
            user = db.query(User).filter_by(username="professor").first()
            if user:
                print(f"Seeded user after manual init: {user.username}")
            else:
                print("Failed to find or seed user.")
        db.close()
        print("Database verification successful!")
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify_postgres()
