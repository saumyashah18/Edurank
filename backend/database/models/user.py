from sqlalchemy import Column, String, Enum
import enum
from .base import BaseModel

class UserRole(enum.Enum):
    PROFESSOR = "professor"
    STUDENT = "student"

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    full_name = Column(String)
