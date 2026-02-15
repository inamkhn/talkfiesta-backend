from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AchievementCategory(str, Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"
    STREAK = "STREAK"
    COMPLETION = "COMPLETION"

class CriteriaType(str, Enum):
    DAY_COMPLETE = "DAY_COMPLETE"
    SCORE_THRESHOLD = "SCORE_THRESHOLD"
    STREAK = "STREAK"
    PLAN_COMPLETE = "PLAN_COMPLETE"

class Rarity(str, Enum):
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

# Response Schemas
class AchievementResponse(BaseModel):
    """Achievement response"""
    id: str
    name: str
    description: str
    icon: str
    category: AchievementCategory
    criteria_type: CriteriaType
    criteria_value: dict
    points: int
    rarity: Rarity

    class Config:
        from_attributes = True

class UserAchievementResponse(BaseModel):
    """User achievement response"""
    achievement: AchievementResponse
    unlocked_at: datetime
    progress_percentage: float

    class Config:
        from_attributes = True

class AchievementUnlockRequest(BaseModel):
    """Achievement unlock request"""
    achievement_id: str

class AchievementUnlockResponse(BaseModel):
    """Achievement unlock response"""
    unlocked: bool
    achievement: AchievementResponse
    message: str
