from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SQLEnum, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class PlanType(str, enum.Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"

class PlanStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class ActivityStatus(str, enum.Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    COMPLETED = "COMPLETED"

class UserPlan(Base):
    __tablename__ = "user_plans"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_type = Column(SQLEnum(PlanType), nullable=False)
    status = Column(SQLEnum(PlanStatus), default=PlanStatus.NOT_STARTED, nullable=False)
    current_day = Column(Integer, default=1, nullable=False)
    completion_percentage = Column(Float, default=0.0, nullable=False)
    cycle_number = Column(Integer, default=1, nullable=False)  # 1-5
    cycles_completed = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_plans")
    daily_activities = relationship("DailyActivity", back_populates="user_plan", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'plan_type', 'cycle_number', name='uq_user_plan_cycle'),
    )

class DailyActivity(Base):
    __tablename__ = "daily_activities"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_plan_id = Column(String, ForeignKey("user_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)  # 1-21
    activity_type = Column(SQLEnum(PlanType), nullable=False)
    status = Column(SQLEnum(ActivityStatus), default=ActivityStatus.LOCKED, nullable=False)
    score = Column(Float, nullable=True)  # 0-100
    completed_at = Column(DateTime, nullable=True)
    time_spent_seconds = Column(Integer, default=0, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_plan = relationship("UserPlan", back_populates="daily_activities")
    speaking_submissions = relationship("SpeakingSubmission", back_populates="daily_activity", cascade="all, delete-orphan")
    vocabulary_practice_sessions = relationship("VocabularyPracticeSession", back_populates="daily_activity", cascade="all, delete-orphan")
    writing_submissions = relationship("WritingSubmission", back_populates="daily_activity", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('user_plan_id', 'day_number', name='uq_plan_day'),
    )

class CycleCompletion(Base):
    __tablename__ = "cycle_completions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_number = Column(Integer, nullable=False)  # 1-5
    speaking_completed = Column(Boolean, default=False, nullable=False)
    vocabulary_completed = Column(Boolean, default=False, nullable=False)
    writing_completed = Column(Boolean, default=False, nullable=False)
    speaking_avg_score = Column(Float, nullable=True)
    vocabulary_avg_score = Column(Float, nullable=True)
    writing_avg_score = Column(Float, nullable=True)
    overall_avg_score = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_time_spent_minutes = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="cycle_completions")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'cycle_number', name='uq_user_cycle'),
    )
