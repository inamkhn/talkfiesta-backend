from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class EnglishLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class PrimaryGoal(str, enum.Enum):
    FLUENCY = "FLUENCY"
    EXAM = "EXAM"
    BUSINESS = "BUSINESS"
    TRAVEL = "TRAVEL"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)  # Nullable for OAuth users
    google_id = Column(String, unique=True, nullable=True, index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    avatar_url = Column(String, nullable=True)
    english_level = Column(SQLEnum(EnglishLevel), default=EnglishLevel.B1, nullable=False)
    primary_goal = Column(SQLEnum(PrimaryGoal), default=PrimaryGoal.FLUENCY, nullable=False)
    streak_days = Column(Integer, default=0, nullable=False)
    total_practice_minutes = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String, nullable=True)
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user_plans = relationship("UserPlan", back_populates="user", cascade="all, delete-orphan")
    speaking_submissions = relationship("SpeakingSubmission", back_populates="user", cascade="all, delete-orphan")
    user_vocabulary = relationship("UserVocabulary", back_populates="user", cascade="all, delete-orphan")
    writing_submissions = relationship("WritingSubmission", back_populates="user", cascade="all, delete-orphan")
    user_achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    daily_progress = relationship("DailyProgress", back_populates="user", cascade="all, delete-orphan")
    analytics_events = relationship("AnalyticsEvent", back_populates="user", cascade="all, delete-orphan")
    cycle_completions = relationship("CycleCompletion", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
