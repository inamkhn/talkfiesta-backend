from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SQLEnum, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class PromptType(str, enum.Enum):
    ESSAY = "ESSAY"
    EMAIL = "EMAIL"
    STORY = "STORY"
    OPINION = "OPINION"
    DESCRIPTION = "DESCRIPTION"

class WritingPrompt(Base):
    __tablename__ = "writing_prompts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    day_number = Column(Integer, nullable=False)  # 1-21
    cycle_number = Column(Integer, default=1, nullable=False)  # 1-5
    difficulty_level = Column(String, nullable=False)  # BEGINNER, INTERMEDIATE, ADVANCED
    prompt_title = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    prompt_type = Column(SQLEnum(PromptType), nullable=False)
    target_word_count = Column(Integer, nullable=False)
    time_limit_minutes = Column(Integer, nullable=True)
    focus_areas = Column(JSON, nullable=False)  # ["grammar", "structure", "vocabulary"]
    writing_tips = Column(JSON, nullable=False)  # [tips]
    sample_outline = Column(Text, nullable=True)
    learning_resources = Column(JSON, nullable=False)  # [{type, title, url, duration}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    submissions = relationship("WritingSubmission", back_populates="prompt")
    
    __table_args__ = (
        UniqueConstraint('day_number', 'cycle_number', name='uq_writing_day_cycle'),
    )

class WritingSubmission(Base):
    __tablename__ = "writing_submissions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_id = Column(String, ForeignKey("writing_prompts.id"), nullable=False, index=True)
    daily_activity_id = Column(String, ForeignKey("daily_activities.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    time_spent_seconds = Column(Integer, nullable=False)
    grammar_score = Column(Float, nullable=False)  # 0-100
    structure_score = Column(Float, nullable=False)  # 0-100
    vocabulary_score = Column(Float, nullable=False)  # 0-100
    coherence_score = Column(Float, nullable=False)  # 0-100
    overall_score = Column(Float, nullable=False)  # 0-100
    grammar_errors = Column(JSON, nullable=False)  # [{type, position, suggestion}]
    vocabulary_suggestions = Column(JSON, nullable=False)  # [{word, alternatives}]
    structure_feedback = Column(Text, nullable=False)
    ai_feedback = Column(JSON, nullable=False)  # {strengths, improvements, tips}
    revision_count = Column(Integer, default=0, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_edited_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="writing_submissions")
    prompt = relationship("WritingPrompt", back_populates="submissions")
    daily_activity = relationship("DailyActivity", back_populates="writing_submissions")
