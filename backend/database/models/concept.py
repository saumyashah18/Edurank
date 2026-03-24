from sqlalchemy import Column, String, Integer, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship
from .base import BaseModel

"""
-- Alembic Migration SQL --
-- CREATE TABLE concepts (
--     id SERIAL PRIMARY KEY,
--     course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
--     name VARCHAR NOT NULL,
--     description TEXT,
--     difficulty_level VARCHAR,
--     UNIQUE(course_id, name)
-- );

-- CREATE TABLE concept_relations (
--     id SERIAL PRIMARY KEY,
--     from_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
--     to_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
--     relation_type VARCHAR NOT NULL,
--     UNIQUE(from_concept_id, to_concept_id, relation_type)
-- );

-- CREATE TABLE concept_chunks (
--     id SERIAL PRIMARY KEY,
--     concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
--     chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
--     UNIQUE(concept_id, chunk_id)
-- );

-- CREATE INDEX idx_concepts_course ON concepts(course_id);
-- CREATE INDEX idx_concepts_name ON concepts(lower(name));
"""

class Concept(BaseModel):
    __tablename__ = "concepts"

    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    difficulty_level = Column(String, nullable=True)  # foundational, intermediate, advanced

    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_concept_name_per_course"),
    )

    # Relationships
    concept_chunks = relationship("ConceptChunk", back_populates="concept", cascade="all, delete-orphan")
    source_relations = relationship(
        "ConceptRelation", 
        foreign_keys="[ConceptRelation.from_concept_id]", 
        back_populates="from_concept",
        cascade="all, delete-orphan"
    )
    target_relations = relationship(
        "ConceptRelation", 
        foreign_keys="[ConceptRelation.to_concept_id]", 
        back_populates="to_concept",
        cascade="all, delete-orphan"
    )
    student_states = relationship("StudentConceptState", back_populates="concept", cascade="all, delete-orphan")

class ConceptRelation(BaseModel):
    __tablename__ = "concept_relations"

    from_concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    to_concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # prerequisite, part_of, contrasts_with, leads_to

    __table_args__ = (
        UniqueConstraint("from_concept_id", "to_concept_id", "relation_type", name="uq_concept_relation"),
    )

    from_concept = relationship("Concept", foreign_keys=[from_concept_id], back_populates="source_relations")
    to_concept = relationship("Concept", foreign_keys=[to_concept_id], back_populates="target_relations")

class ConceptChunk(BaseModel):
    __tablename__ = "concept_chunks"

    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("concept_id", "chunk_id", name="uq_concept_chunk"),
    )

    concept = relationship("Concept", back_populates="concept_chunks")
    chunk = relationship("Chunk", backref="concept_links")
