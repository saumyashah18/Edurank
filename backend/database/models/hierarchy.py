from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import BaseModel

class Chapter(BaseModel):
    __tablename__ = "chapters"
    
    title = Column(String, nullable=False)
    order = Column(Integer)
    course_id = Column(Integer, ForeignKey("courses.id"))
    
    course = relationship("Course", back_populates="chapters")
    sections = relationship("Section", back_populates="chapter", cascade="all, delete-orphan")

class Section(BaseModel):
    __tablename__ = "sections"
    
    title = Column(String, nullable=False)
    order = Column(Integer)
    chapter_id = Column(Integer, ForeignKey("chapters.id"))
    
    chapter = relationship("Chapter", back_populates="sections")
    subsections = relationship("Subsection", back_populates="section", cascade="all, delete-orphan")

class Subsection(BaseModel):
    __tablename__ = "subsections"
    
    title = Column(String, nullable=False)
    order = Column(Integer)
    section_id = Column(Integer, ForeignKey("sections.id"))
    
    section = relationship("Section", back_populates="subsections")
    materials = relationship("RawMaterial", back_populates="subsection", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="subsection", cascade="all, delete-orphan")

class RawMaterial(BaseModel):
    __tablename__ = "raw_materials"
    
    content = Column(Text, nullable=False)
    source_type = Column(String) # e.g., "pdf", "docx"
    subsection_id = Column(Integer, ForeignKey("subsections.id"))
    
    subsection = relationship("Subsection", back_populates="materials")
