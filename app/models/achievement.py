from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SQLEnum, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class AchievementCategory(str, enum.Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"
    STREAK = "STREAK"
    COMPLETION = "COMPLETION"

class CriteriaType(str, enum.Enum):
    DAY_COMPLETE = "DAY_COMPLETE"
    SCORE_THRESHOLD = "SCORE_THRESHOLD"
    STREAK = "STREAK"
    PLAN_COMPLETE = "PLAN_COMPLETE"

class Rarity(str, enum.Enum):
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String, nullable=False)
    category = Column(SQLEnum(AchievementCategory), nullable=False)
    criteria_type = Column(SQLEnum(CriteriaType), nullable=False)
    criteria_value = Column(JSON, nullable=False)  # {threshold, count, etc.}
    points = Column(Integer, nullable=False)
    rarity = Column(SQLEnum(Rarity), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user_achievements = relationship("UserAchievement", back_populates="achievement")

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = Column(String, ForeignKey("achievements.id"), nullable=False, index=True)
    unlocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    progress_percentage = Column(Float, default=0.0, nullable=False)  # 0-100
    
    # Relationships
    user = relationship("User", back_populates="user_achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),
    )
