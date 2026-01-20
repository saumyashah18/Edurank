from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel

class Course(BaseModel):
    __tablename__ = "courses"
    
    title = Column(String, index=True, nullable=False)
    description = Column(String)
    professor_id = Column(Integer, ForeignKey("users.id"))
    
    professor = relationship("User", backref="courses")
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan")
