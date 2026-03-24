import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from .models.base import Base

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/edurank_dev"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

# Enable pgvector extension on startup
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

def init_db():
    from .models.user import User
    from .models.course import Course
    from .models.hierarchy import Chapter, Section, Subsection, RawMaterial
    from .models.chunk import Chunk, KnowledgeRelation
    from .models.question import Question
    from .models.transcript import Quiz, Transcript

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        from .models.user import UserRole
        if not db.query(User).filter_by(username="professor").first():
            prof = User(
                username="professor",
                email="prof@edu.rank",
                hashed_password="hashed",
                role=UserRole.PROFESSOR
            )
            db.add(prof)
            db.commit()
            course = Course(
                title="General Course",
                description="Default syllabus container",
                professor_id=prof.id
            )
            db.add(course)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[init_db] Seed data already exists or error: {e}")
    finally:
        db.close()
