from sqlalchemy import Column, String, Integer, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from .base import BaseModel

class Quiz(BaseModel):
    __tablename__ = "quizzes"
    
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String)
    duration_minutes = Column(Integer, default=60)
    total_marks = Column(Integer, default=100)
    total_questions = Column(Integer, default=5)
    password = Column(String)
    is_finalized = Column(Integer, default=0) # 0: Draft, 1: Active
    instructions = Column(Text) # System instructions/Prompt gating
    
    transcripts = relationship("Transcript", back_populates="quiz")
    course = relationship("Course", backref="quizzes")


class Transcript(BaseModel):
    __tablename__ = "transcripts"
    
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    student_name = Column(String)
    enrollment_id = Column(String)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    
    student_answer = Column(Text)
    ai_evaluation = Column(Text) # Store AI reasoning
    score = Column(Float)
    
    # Audit fields
    retrieved_chunk_ids = Column(String) # Comma-separated or JSON list
    time_taken_seconds = Column(Integer)
    
    student = relationship("User")
    quiz = relationship("Quiz", back_populates="transcripts")
    question = relationship("Question")
