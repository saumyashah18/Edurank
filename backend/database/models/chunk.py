from sqlalchemy import Column, String, Integer, ForeignKey, Text, Enum
import enum
from sqlalchemy.orm import relationship
from .base import BaseModel

class ChunkType(enum.Enum):
    SMALL = "S"    # Definitions, facts
    MEDIUM = "M"   # Explanations, reasoning
    LARGE = "L"    # Concept scope, syllabus planning

class Chunk(BaseModel):
    __tablename__ = "chunks"
    
    content = Column(Text, nullable=False)
    chunk_type = Column(Enum(ChunkType), nullable=False)
    vector_id = Column(String, index=True) # Reference to FAISS index
    subsection_id = Column(Integer, ForeignKey("subsections.id"))
    
    subsection = relationship("Subsection", back_populates="chunks")

class KnowledgeRelation(BaseModel):
    __tablename__ = "knowledge_relations"
    
    source_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    relation_type = Column(String, default="connection") # e.g. "critique", "pre-requisite"
    
    source = relationship("Chunk", foreign_keys=[source_id])
    target = relationship("Chunk", foreign_keys=[target_id])
