from sqlalchemy import Column, String, Enum
import enum
from .base import BaseModel

class UserRole(enum.Enum):
    PROFESSOR = "professor"
    STUDENT = "student"

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    firebase_uid = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True) # Optional if using Firebase
    role = Column(Enum(UserRole), default=UserRole.PROFESSOR)
    full_name = Column(String)
