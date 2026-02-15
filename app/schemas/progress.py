from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

# Response Schemas
class DailyProgressResponse(BaseModel):
    """Daily progress response"""
    date: date
    speaking_completed: bool
    vocabulary_completed: bool
    writing_completed: bool
    total_minutes_practiced: int
    words_learned_count: int
    average_score: Optional[float] = None
    exercises_completed_count: int
    streak_maintained: bool

    class Config:
        from_attributes = True

class TodayProgressResponse(BaseModel):
    """Today's progress summary"""
    speaking_completed: bool
    vocabulary_completed: bool
    writing_completed: bool
    total_minutes: int

class RecentScoresResponse(BaseModel):
    """Recent average scores"""
    speaking_avg: Optional[float] = None
    vocabulary_avg: Optional[float] = None
    writing_avg: Optional[float] = None

class PlanSummary(BaseModel):
    """Plan summary for dashboard"""
    plan_type: str
    current_day: int
    completion_percentage: float
    status: str

class UserSummary(BaseModel):
    """User summary for dashboard"""
    name: str
    streak_days: int
    total_practice_minutes: int
    english_level: str

class DashboardResponse(BaseModel):
    """Dashboard overview response"""
    user: UserSummary
    current_cycle: int
    plans: list[PlanSummary]
    today_progress: TodayProgressResponse
    recent_scores: RecentScoresResponse

class StreakHistoryItem(BaseModel):
    """Streak history item"""
    date: date
    maintained: bool

class StreakResponse(BaseModel):
    """Streak information response"""
    current_streak: int
    longest_streak: int
    total_practice_days: int
    streak_history: list[StreakHistoryItem]

class ScoreTrend(BaseModel):
    """Score trend data point"""
    date: date
    score: float

class ModuleBreakdown(BaseModel):
    """Module breakdown stats"""
    completed: int
    avg_score: float

class AnalyticsResponse(BaseModel):
    """Analytics response"""
    period: str
    total_practice_minutes: int
    total_exercises: int
    average_daily_minutes: float
    score_trends: dict[str, list[ScoreTrend]]
    module_breakdown: dict[str, ModuleBreakdown]
    words_learned: int
    most_practiced_time: str
    completion_rate: float
