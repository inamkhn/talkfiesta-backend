import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Date, Text, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True) # Allows global defaults if ever needed, but targets specific users
    cycle = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    position_in_day = Column(Integer, nullable=False)
    word = Column(String(100), nullable=False, index=True)
    phonetic = Column(String(100))
    part_of_speech = Column(String(20))
    definition = Column(Text, nullable=False)
    example_sentences = Column(JSON, nullable=False)
    synonyms = Column(JSON, default=list)
    antonyms = Column(JSON, default=list)
    collocations = Column(JSON, default=list)
    memory_tip = Column(Text)
    register = Column(String(20))
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_vocabulary_words_user_cycle_day", "user_id", "cycle", "day"),)


class VocabularyProgress(Base):
    __tablename__ = "vocabulary_progress"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    word_id = Column(String, ForeignKey("vocabulary_words.id"), nullable=False)
    times_practiced = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    mastery_level = Column(Integer, default=0)
    last_practiced = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="vocabulary_progress")
    word = relationship("VocabularyWord")

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
        Index("idx_vocabulary_progress_user_word", "user_id", "word_id"),
    )


class VocabularySRS(Base):
    __tablename__ = "vocabulary_srs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    word_id = Column(String, ForeignKey("vocabulary_words.id"), nullable=False)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=0)
    repetitions = Column(Integer, default=0)
    mastery_level = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    next_review_date = Column(Date, nullable=True)
    last_reviewed = Column(Date)
    is_mastered = Column(Boolean, default=False)
    mastered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="vocabulary_srs")
    word = relationship("VocabularyWord")

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_srs"),
        Index("idx_srs_user_review_date", "user_id", "next_review_date"),
        Index("idx_srs_user_mastered", "user_id", "is_mastered"),
    )
