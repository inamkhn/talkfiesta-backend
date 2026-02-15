from sqlalchemy import Column, String, Integer, Float, DateTime, Enum as SQLEnum, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base

class DifficultyLevel(str, enum.Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"

class SpeakingExercise(Base):
    __tablename__ = "speaking_exercises"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    day_number = Column(Integer, nullable=False)  # 1-21
    cycle_number = Column(Integer, default=1, nullable=False)  # 1-5
    difficulty_level = Column(SQLEnum(DifficultyLevel), nullable=False)
    topic = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    target_duration_seconds = Column(Integer, nullable=False)
    instructions = Column(Text, nullable=False)
    example_response = Column(Text, nullable=True)
    focus_areas = Column(JSON, nullable=False)  # ["grammar", "vocabulary", "fluency"]
    learning_resources = Column(JSON, nullable=False)  # [{type, title, url, duration}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    submissions = relationship("SpeakingSubmission", back_populates="exercise")
    
    __table_args__ = (
        UniqueConstraint('day_number', 'cycle_number', name='uq_speaking_day_cycle'),
    )

class SpeakingSubmission(Base):
    __tablename__ = "speaking_submissions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id = Column(String, ForeignKey("speaking_exercises.id"), nullable=False, index=True)
    daily_activity_id = Column(String, ForeignKey("daily_activities.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_url = Column(String, nullable=False)
    transcription = Column(Text, nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    word_count = Column(Integer, nullable=False)
    words_per_minute = Column(Float, nullable=False)
    fluency_score = Column(Float, nullable=False)  # 0-100
    grammar_score = Column(Float, nullable=False)  # 0-100
    vocabulary_score = Column(Float, nullable=False)  # 0-100
    pronunciation_score = Column(Float, nullable=False)  # 0-100
    overall_score = Column(Float, nullable=False)  # 0-100
    pause_count = Column(Integer, nullable=False)
    filler_words_count = Column(Integer, nullable=False)
    filler_words_list = Column(JSON, nullable=False)  # ["um", "uh", "like"]
    ai_feedback = Column(JSON, nullable=False)  # {strengths, improvements, tips}
    grammar_corrections = Column(JSON, nullable=False)  # [{error, correction, explanation}]
    vocabulary_suggestions = Column(JSON, nullable=False)  # [{word, better_options}]
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="speaking_submissions")
    exercise = relationship("SpeakingExercise", back_populates="submissions")
    daily_activity = relationship("DailyActivity", back_populates="speaking_submissions")
