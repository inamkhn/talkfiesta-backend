from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    event_category = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)
    session_id = Column(String, nullable=False)
    device_info = Column(JSON, nullable=False)  # {browser, os, screen}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="analytics_events")
    
    __table_args__ = (
        Index('idx_event_name_created', 'event_name', 'created_at'),
        Index('idx_user_created', 'user_id', 'created_at'),
    )
