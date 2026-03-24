# -- ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS is_processing BOOLEAN DEFAULT FALSE;
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel

class Quiz(BaseModel):
    __tablename__ = "quizzes"
    
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, default=60)
    total_marks = Column(Integer, default=100)
    total_questions = Column(Integer, default=5)
    password = Column(String)
    is_finalized = Column(Integer, default=0)
    instructions = Column(Text) 
    allow_audio = Column(Boolean, default=True)
    ai_eval_enabled = Column(Boolean, default=False)  # Toggle for AI rubric evaluation
    ai_eval_rubric = Column(Text, nullable=True)  # JSON: {"total_marks": N, "criteria": [{"name": ..., "marks": N}]}
    is_processing = Column(Boolean, default=False)
    
    transcripts = relationship("Transcript", back_populates="quiz")
    course = relationship("Course", backref="quizzes")


class Transcript(BaseModel):
    __tablename__ = "transcripts"
    
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    student_name = Column(String)
    enrollment_id = Column(String)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"))
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    
    student_answer = Column(Text)
    ai_evaluation = Column(Text) # Store AI reasoning
    score = Column(Float)
    conceptual_gap = Column(Boolean, default=False)
    ai_eval_results = Column(Text, nullable=True)  # JSON: per-answer rubric evaluation results
    
    # Audit fields
    retrieved_chunk_ids = Column(String) # Comma-separated or JSON list
    time_taken_seconds = Column(Integer)
    
    student = relationship("User")
    quiz = relationship("Quiz", back_populates="transcripts")
    question = relationship("Question", overlaps="transcripts")
