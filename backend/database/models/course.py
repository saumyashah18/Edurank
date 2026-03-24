# -- ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_ingesting BOOLEAN DEFAULT FALSE;
from sqlalchemy import Column, String, ForeignKey, Integer, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from .base import BaseModel


# -- No migration needed: ingestion_status is a VARCHAR, new values
# -- are valid immediately.

# INGESTION STATUS FLOW (two phases):
#
# Phase A — Document pipeline (blocking, ~2 min):
#   PENDING → VALIDATING → EXTRACTING → (OCR_PROCESSING)
#   → CHUNKING → EMBEDDING → COMPLETED
#   Quiz is available in rotation mode from COMPLETED onwards.
#
# Phase B — Concept extraction (background, ~14 min):
#   CONCEPT_EXTRACTION → FULLY_READY
#   Adaptive quiz engine activates at FULLY_READY.
#   If Phase B fails: status = FAILED, ingestion_error is set.
#
# Frontend display guide:
#   COMPLETED        → "Ready for quizzing"  (green)
#   CONCEPT_EXTRACTION → "Building concept graph..." (blue, spinner)
#   FULLY_READY      → "Fully optimised"  (green, star)
#   FAILED           → show ingestion_error  (red)
class IngestionStatus:
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    EXTRACTING = "EXTRACTING"
    OCR_PROCESSING = "OCR_PROCESSING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    COMPLETED = "COMPLETED"
    CONCEPT_EXTRACTION = "CONCEPT_EXTRACTION"
    FULLY_READY = "FULLY_READY"
    FAILED = "FAILED"


class Course(BaseModel):
    __tablename__ = "courses"

    title = Column(String, index=True, nullable=False)
    description = Column(String)
    professor_id = Column(Integer, ForeignKey("users.id"))
    ingestion_status = Column(String, default=IngestionStatus.PENDING)
    ingestion_error = Column(Text, nullable=True)  # Human-readable error message
    is_ingesting = Column(Boolean, default=False)

    professor = relationship("User", backref="courses")
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan")
    concepts = relationship("Concept", backref="course", cascade="all, delete-orphan")

class Document(BaseModel):
    __tablename__ = "documents"

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    ingestion_status = Column(String, default=IngestionStatus.PENDING)
    ingestion_error = Column(Text, nullable=True)
    is_ingesting = Column(Boolean, default=False)
    
    course = relationship("Course", backref="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
