import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    avatar_url = Column(String(500))
    english_level = Column(String(10))       # A1–C2
    learning_goal = Column(String(50))       # conversation/business/academic
    daily_commitment = Column(Integer, default=30) # time in minutes
    total_xp = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Active plan tracking
    active_plan_id = Column(String, ForeignKey("user_plans.id"), nullable=True, index=True)
    current_day = Column(Integer, default=1)

    # Stripe billing — denormalised cus_xxx for O(1) access checks (no JOIN needed)
    stripe_customer_id_cache = Column(String(64), nullable=True, index=True)

    # Email verification
    verification_token = Column(String(64), nullable=True, index=True)
    verification_token_expires = Column(DateTime, nullable=True)

    # Password reset
    reset_token = Column(String(64), nullable=True, index=True)
    reset_token_expires = Column(DateTime, nullable=True)

    # Relationships
    plans = relationship(
        "UserPlan",
        back_populates="user",
        foreign_keys="UserPlan.user_id"
    )
    active_plan = relationship(
        "UserPlan",
        foreign_keys=[active_plan_id],
        post_update=True
    )
    daily_progresses = relationship("DailyProgress", back_populates="user")
    conversation_sessions = relationship("ConversationSession", back_populates="user")
    speaking_submissions = relationship("SpeakingSubmission", back_populates="user")
    vocabulary_progress = relationship("VocabularyProgress", back_populates="user")
    vocabulary_srs = relationship("VocabularySRS", back_populates="user")
    writing_submissions = relationship("WritingSubmission", back_populates="user")
    user_achievements = relationship("UserAchievement", back_populates="user")
    cycle_completions = relationship("CycleCompletion", back_populates="user")
    refresh_token_records = relationship(
        "RefreshTokenRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # ── Stripe billing relationships ──────────────────────────────────────────
    stripe_customer = relationship(
        "StripeCustomer",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    stripe_subscription = relationship(
        "StripeSubscription",
        back_populates="user",
        uselist=False,
        primaryjoin=(
            "and_(User.id == StripeSubscription.user_id, "
            "StripeSubscription.status.in_(['trialing','active','past_due']))"
        ),
        viewonly=True,
    )
    stripe_payment_records = relationship(
        "StripePaymentRecord",
        back_populates="user",
        order_by="StripePaymentRecord.created_at.desc()",
    )
