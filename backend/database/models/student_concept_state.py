from sqlalchemy import Column, String, Integer, ForeignKey, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import BaseModel

"""
-- Alembic Migration SQL --
-- CREATE TABLE student_concept_states (
--     id SERIAL PRIMARY KEY,
--     student_id VARCHAR NOT NULL,
--     quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
--     concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
--     status VARCHAR NOT NULL DEFAULT 'not_tested',
--     confidence FLOAT DEFAULT 0.0,
--     attempts INTEGER DEFAULT 0,
--     misconception TEXT,
--     recommended_action VARCHAR,
--     last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
--     UNIQUE(student_id, quiz_id, concept_id)
-- );
-- CREATE INDEX idx_student_states_student ON student_concept_states(student_id);
"""

class StudentConceptState(BaseModel):
    __tablename__ = "student_concept_states"

    student_id = Column(String, nullable=False, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    
    # Status: not_tested, struggling, partial, demonstrated
    status = Column(String, nullable=False, default="not_tested")
    confidence = Column(Float, default=0.0)  # Rolling average (0.0 - 1.0)
    attempts = Column(Integer, default=0)
    
    misconception = Column(Text, nullable=True)
    recommended_action = Column(String, nullable=True) # drop_to_prerequisite, retry_rephrase, deepen, move_on
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "quiz_id", "concept_id", name="uq_student_quiz_concept"),
    )

    concept = relationship("Concept", back_populates="student_states")
    quiz = relationship("Quiz")
