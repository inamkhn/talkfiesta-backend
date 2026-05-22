import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_type = Column(Enum("text", "voice", name="session_type"), default="text")
    scenario_key = Column(String(100), nullable=False)
    scenario_title = Column(String(200), nullable=False)
    user_level = Column(String(10), nullable=False)
    system_prompt = Column(Text, nullable=False)
    max_turns = Column(Integer, default=20)
    max_duration_seconds = Column(Integer, default=300)
    turn_count = Column(Integer, default=0)
    session_audio_url = Column(String(500))
    status = Column(
        Enum("active", "completed", "abandoned", name="session_status"),
        default="active",
        index=True
    )
    overall_score = Column(Integer)
    fluency_rating = Column(String(50))
    confidence_rating = Column(String(50))
    errors_noticed = Column(JSON, default=list)
    strengths = Column(JSON, default=list)
    focus_for_next_time = Column(Text)
    encouragement = Column(Text)
    xp_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="conversation_sessions")
    messages = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.turn_number"
    )

    __table_args__ = (Index("idx_conv_sessions_user_status", "user_id", "status"),)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(Enum("user", "ai", name="message_role"), nullable=False)
    content = Column(Text, nullable=False)
    audio_clip_url = Column(String(500))
    turn_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSession", back_populates="messages")

    __table_args__ = (Index("idx_conv_messages_session_turn", "session_id", "turn_number"),)
