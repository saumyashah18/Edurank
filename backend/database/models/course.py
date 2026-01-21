from sqlalchemy import Column, String, ForeignKey, Integer, Enum
import enum
from sqlalchemy.orm import relationship
from .base import BaseModel

class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Course(BaseModel):
    __tablename__ = "courses"
    
    title = Column(String, index=True, nullable=False)
    description = Column(String)
    professor_id = Column(Integer, ForeignKey("users.id"))
    ingestion_status = Column(Enum(IngestionStatus), default=IngestionStatus.PENDING)
    
    professor = relationship("User", backref="courses")
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan")
