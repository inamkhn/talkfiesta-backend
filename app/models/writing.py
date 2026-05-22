import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class WritingPrompt(Base):
    __tablename__ = "writing_prompts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    cycle = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    prompt = Column(Text, nullable=False)
    min_words = Column(Integer, default=50)
    max_words = Column(Integer, default=300)
    grammar_focus = Column(String(100))
    difficulty = Column(String(20))
    tips = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_writing_prompts_user_cycle_day", "user_id", "cycle", "day"),
        Index("idx_writing_prompts_cycle_day", "cycle", "day"),
    )


class WritingSubmission(Base):
    __tablename__ = "writing_submissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    prompt_id = Column(String, ForeignKey("writing_prompts.id"), nullable=False)
    content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    overall_score = Column(Integer)
    grammar_score = Column(Integer)
    vocabulary_score = Column(Integer)
    coherence_score = Column(Integer)
    grammar_errors = Column(JSON, default=list)
    vocabulary_suggestions = Column(JSON, default=list)
    feedback = Column(Text)
    improvement_tips = Column(JSON, default=list)
    encouragement = Column(Text)
    passed = Column(Boolean, default=False)
    xp_earned = Column(Integer, default=0)
    is_revised = Column(Boolean, default=False)
    revision_of = Column(String, ForeignKey("writing_submissions.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    analysed_at = Column(DateTime)

    user = relationship("User", back_populates="writing_submissions")
    prompt = relationship("WritingPrompt")

    __table_args__ = (Index("idx_writing_submissions_user", "user_id"),)
