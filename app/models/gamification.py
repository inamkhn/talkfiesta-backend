import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(100))
    category = Column(String(50))           # speaking/vocabulary/writing/streak
    requirement_type = Column(String(50))   # count/streak/score
    requirement_value = Column(Integer, nullable=False)
    xp_reward = Column(Integer, default=0)
    rarity = Column(String(20))             # common/rare/epic/legendary
    created_at = Column(DateTime, default=datetime.utcnow)

    user_achievements = relationship("UserAchievement", back_populates="achievement")

    __table_args__ = (Index("idx_achievements_category", "category"),)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(String, ForeignKey("achievements.id"), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    progress = Column(Integer, default=0)

    user = relationship("User", back_populates="user_achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")

    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)


class CycleCompletion(Base):
    __tablename__ = "cycle_completions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    total_xp_earned = Column(Integer, default=0)
    average_score = Column(Float)
    days_taken = Column(Integer)

    user = relationship("User", back_populates="cycle_completions")

    __table_args__ = (Index("idx_cycle_completions_user", "user_id"),)
