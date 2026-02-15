from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class PartOfSpeech(str, enum.Enum):
    NOUN = "NOUN"
    VERB = "VERB"
    ADJECTIVE = "ADJECTIVE"
    ADVERB = "ADVERB"
    PRONOUN = "PRONOUN"
    PREPOSITION = "PREPOSITION"
    CONJUNCTION = "CONJUNCTION"
    INTERJECTION = "INTERJECTION"

class VocabularyStatus(str, enum.Enum):
    NEW = "NEW"
    LEARNING = "LEARNING"
    REVIEWING = "REVIEWING"
    MASTERED = "MASTERED"

class ExerciseType(str, enum.Enum):
    FILL_BLANK = "FILL_BLANK"
    MATCHING = "MATCHING"
    USAGE = "USAGE"
    PRONUNCIATION = "PRONUNCIATION"

class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    word = Column(String, unique=True, nullable=False, index=True)
    definition = Column(Text, nullable=False)
    part_of_speech = Column(SQLEnum(PartOfSpeech), nullable=False)
    difficulty_level = Column(String, nullable=False)  # BEGINNER, INTERMEDIATE, ADVANCED
    cefr_level = Column(String, nullable=False)  # A1, A2, B1, B2, C1, C2
    cycle_number = Column(Integer, default=1, nullable=False)  # 1-5
    pronunciation_ipa = Column(String, nullable=False)
    pronunciation_audio_url = Column(String, nullable=True)
    example_sentences = Column(JSON, nullable=False)  # [{sentence, translation}]
    synonyms = Column(JSON, nullable=False)  # [words]
    antonyms = Column(JSON, nullable=False)  # [words]
    usage_tips = Column(Text, nullable=True)
    category = Column(String, nullable=False)  # business, academic, daily, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_vocabulary = relationship("UserVocabulary", back_populates="word")

class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    word_id = Column(String, ForeignKey("vocabulary_words.id"), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)  # 1-21
    status = Column(SQLEnum(VocabularyStatus), default=VocabularyStatus.NEW, nullable=False)
    mastery_level = Column(Integer, default=0, nullable=False)  # 0-5
    times_reviewed = Column(Integer, default=0, nullable=False)
    times_practiced = Column(Integer, default=0, nullable=False)
    last_reviewed_at = Column(DateTime, nullable=True)
    next_review_at = Column(DateTime, nullable=True)
    learned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    mastered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_vocabulary")
    word = relationship("VocabularyWord", back_populates="user_vocabulary")
    practice_sessions = relationship("VocabularyPracticeSession", back_populates="user_vocabulary", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'word_id', name='uq_user_word'),
    )

class VocabularyPracticeSession(Base):
    __tablename__ = "vocabulary_practice_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_vocabulary_id = Column(String, ForeignKey("user_vocabulary.id", ondelete="CASCADE"), nullable=False, index=True)
    daily_activity_id = Column(String, ForeignKey("daily_activities.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_type = Column(SQLEnum(ExerciseType), nullable=False)
    is_correct = Column(String, nullable=False)  # Store as string "true"/"false" for compatibility
    user_answer = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)
    time_taken_seconds = Column(Integer, nullable=False)
    practiced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user_vocabulary = relationship("UserVocabulary", back_populates="practice_sessions")
    daily_activity = relationship("DailyActivity", back_populates="vocabulary_practice_sessions")
