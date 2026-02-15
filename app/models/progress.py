from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base

class DailyProgress(Base):
    __tablename__ = "daily_progress"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    speaking_completed = Column(Boolean, default=False, nullable=False)
    vocabulary_completed = Column(Boolean, default=False, nullable=False)
    writing_completed = Column(Boolean, default=False, nullable=False)
    total_minutes_practiced = Column(Integer, default=0, nullable=False)
    words_learned_count = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, nullable=True)
    exercises_completed_count = Column(Integer, default=0, nullable=False)
    streak_maintained = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="daily_progress")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_date'),
    )
