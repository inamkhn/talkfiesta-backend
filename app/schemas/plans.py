from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PlanSummaryResponse(BaseModel):
    """One plan in GET /plans list."""

    id: str
    cycle_number: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    days_completed: int = Field(ge=0, description="Completed days in this 21-day cycle")
    total_days: int = Field(default=21, ge=1)

    class Config:
        from_attributes = True


class PlanDayBriefResponse(BaseModel):
    """Per-day row for plan detail."""

    day_number: int
    date: Optional[date_type] = None
    is_complete: bool


class PlanDetailResponse(BaseModel):
    """GET /plans/{plan_id}."""

    id: str
    cycle_number: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    days: list[PlanDayBriefResponse] = []


class PlanStatusUpdateRequest(BaseModel):
    """Close an active cycle: mark finished successfully or abandon."""

    status: Literal["completed", "abandoned"]


class PlanDayResponse(BaseModel):
    """GET /plans/{plan_id}/days/{day_number} — full DailyProgress."""

    id: str
    plan_id: str
    day_number: int
    date: Optional[date_type] = None
    is_complete: bool
    activities_completed: int
    xp_earned: int
    speaking_done: bool
    vocabulary_done: bool
    writing_done: bool
    created_at: datetime

    class Config:
        from_attributes = True
