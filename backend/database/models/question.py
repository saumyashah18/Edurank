from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum
import enum
from sqlalchemy.orm import relationship
from .base import BaseModel

class QuestionStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REWORDING = "needs_reword"

class Question(BaseModel):
    __tablename__ = "questions"
    
    question_text = Column(Text, nullable=False)
    ideal_answer = Column(Text, nullable=False)
    status = Column(Enum(QuestionStatus), default=QuestionStatus.PENDING)
    difficulty = Column(String)
    
    # Ranking fields
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)

    
    # Track source for grounding
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"))
    subsection_id = Column(Integer, ForeignKey("subsections.id", ondelete="CASCADE"))
    
    chunk = relationship("Chunk")
    subsection = relationship("Subsection", overlaps="questions")
