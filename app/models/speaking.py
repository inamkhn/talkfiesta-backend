import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class SpeakingExercise(Base):
    __tablename__ = "speaking_exercises"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    cycle = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    instruction = Column(Text, nullable=False)
    prompt_text = Column(Text, nullable=False)
    duration_seconds = Column(Integer, default=60)
    difficulty = Column(String(20))
    tips = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_speaking_exercises_user_cycle_day", "user_id", "cycle", "day"),
        Index("idx_speaking_exercises_cycle_day", "cycle", "day"),
    )


class SpeakingSubmission(Base):
    __tablename__ = "speaking_submissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    exercise_id = Column(String, ForeignKey("speaking_exercises.id"), nullable=False)
    audio_file_path = Column(String(500), nullable=False)
    audio_mime_type = Column(String(50))
    audio_size_bytes = Column(Integer)
    status = Column(String(20), default="pending")   # pending/processing/done/failed
    exercise_prompt_text = Column(Text)
    user_level = Column(String(10))
    transcript = Column(Text)
    overall_score = Column(Integer)
    fluency_score = Column(Integer)
    pronunciation_score = Column(Integer)
    pace_score = Column(Integer)
    words_mispronounced = Column(JSON, default=list)
    pronunciation_issues = Column(JSON, default=list)
    feedback = Column(Text)
    improvement_tips = Column(JSON, default=list)
    encouragement = Column(Text)
    passed = Column(Boolean, default=False)
    xp_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    analysed_at = Column(DateTime)

    user = relationship("User", back_populates="speaking_submissions")
    exercise = relationship("SpeakingExercise")
    job = relationship("SpeakingJob", back_populates="submission", uselist=False)

    __table_args__ = (Index("idx_speaking_submissions_user", "user_id"),)


class SpeakingJob(Base):
    __tablename__ = "speaking_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    submission_id = Column(String, ForeignKey("speaking_submissions.id"), nullable=False)
    status = Column(
        Enum("pending", "processing", "done", "failed", name="job_status"),
        default="pending",
        index=True
    )
    error_message = Column(Text)
    result_summary = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    user = relationship("User")
    submission = relationship("SpeakingSubmission", back_populates="job")

    __table_args__ = (Index("idx_speaking_jobs_user_status", "user_id", "status"),)
