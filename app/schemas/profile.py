from __future__ import annotations

from pydantic import BaseModel, field_validator

ALLOWED_CEFR = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})


class ProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    english_level: str | None = None
    learning_goal: str | None = None
    daily_commitment: int = 30
    total_xp: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    is_verified: bool = False
    active_plan_id: str | None = None
    current_day: int = 1

    class Config:
        from_attributes = True


class ProfileStatsResponse(BaseModel):
    total_xp: int
    current_streak: int
    longest_streak: int
    achievements_unlocked: int
    days_completed: int
    cycles_completed: int
    active_plan_cycle_number: int | None = None


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    english_level: str | None = None
    learning_goal: str | None = None
    daily_commitment: int | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_valid(cls, v: str | None):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 100:
            raise ValueError("Full name must be at most 100 characters")
        return v

    @field_validator("avatar_url")
    @classmethod
    def avatar_url_valid(cls, v: str | None):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 500:
            raise ValueError("Avatar URL must be at most 500 characters")
        return v

    @field_validator("english_level")
    @classmethod
    def english_level_valid(cls, v: str | None):
        if v is None:
            return None
        v = v.strip().upper()
        if v not in ALLOWED_CEFR:
            raise ValueError(f"english_level must be one of: {', '.join(sorted(ALLOWED_CEFR))}")
        return v

    @field_validator("learning_goal")
    @classmethod
    def learning_goal_valid(cls, v: str | None):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 50:
            raise ValueError("learning_goal must be at most 50 characters")
        return v
