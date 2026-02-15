from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class PlanType(str, Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"

class PlanStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class ActivityStatus(str, Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    COMPLETED = "COMPLETED"

# Request Schemas
class PlanCreate(BaseModel):
    """Create new plan schema"""
    plan_type: PlanType
    cycle_number: int = Field(default=1, ge=1, le=5)

# Response Schemas
class DailyActivityResponse(BaseModel):
    """Daily activity response"""
    id: str
    day_number: int
    activity_type: PlanType
    status: ActivityStatus
    score: Optional[float] = None
    completed_at: Optional[datetime] = None
    time_spent_seconds: int
    attempts_count: int

    class Config:
        from_attributes = True

class UserPlanResponse(BaseModel):
    """User plan response"""
    id: str
    plan_type: PlanType
    status: PlanStatus
    current_day: int
    completion_percentage: float
    cycle_number: int
    cycles_completed: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True

class UserPlanDetail(UserPlanResponse):
    """User plan with daily activities"""
    daily_activities: list[DailyActivityResponse]

class CycleCompletionResponse(BaseModel):
    """Cycle completion response"""
    id: str
    cycle_number: int
    speaking_completed: bool
    vocabulary_completed: bool
    writing_completed: bool
    speaking_avg_score: Optional[float] = None
    vocabulary_avg_score: Optional[float] = None
    writing_avg_score: Optional[float] = None
    overall_avg_score: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_time_spent_minutes: int

    class Config:
        from_attributes = True
