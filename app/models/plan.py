import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserPlan(Base):
    __tablename__ = "user_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    status = Column(
        Enum("in_progress", "completed", "abandoned", name="plan_status"),
        default="in_progress"
    )
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship(
        "User",
        back_populates="plans",
        foreign_keys=[user_id]
    )
    daily_progresses = relationship("DailyProgress", back_populates="plan")

    __table_args__ = (Index("idx_user_plans_user_status", "user_id", "status"),)


class DailyProgress(Base):
    __tablename__ = "daily_progress"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    plan_id = Column(String, ForeignKey("user_plans.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=True)
    is_complete = Column(Boolean, default=False)
    activities_completed = Column(Integer, default=0)
    xp_earned = Column(Integer, default=0)
    speaking_done = Column(Boolean, default=False)
    vocabulary_done = Column(Boolean, default=False)
    writing_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="daily_progresses")
    plan = relationship("UserPlan", back_populates="daily_progresses")

    __table_args__ = (Index("idx_daily_progress_user_date", "user_id", "date"),)
