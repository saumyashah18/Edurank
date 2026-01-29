import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models.base import Base

load_dotenv()

# Use SQLite for local development by default, or Postgres if specified
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./edurank.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # SQLite-specific connect_args are only needed for SQLite
    **({"connect_args": {"check_same_thread": False}} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {})
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

def init_db():
    # Import all models here to ensure they are registered with Base
    from .models.user import User
    from .models.course import Course
    from .models.hierarchy import Chapter, Section, Subsection, RawMaterial
    from .models.chunk import Chunk, KnowledgeRelation
    from .models.question import Question
    from .models.transcript import Quiz, Transcript
    
    Base.metadata.create_all(bind=engine)
    
    # Seed default data
    db = SessionLocal()
    from .models.user import UserRole
    if not db.query(User).filter_by(username="professor").first():
        prof = User(username="professor", email="prof@edu.rank", hashed_password="hashed", role=UserRole.PROFESSOR)

        db.add(prof)
        db.commit()
        course = Course(title="General Course", description="Default syllabus container", professor_id=prof.id)

        db.add(course)
        db.commit()
    db.close()

