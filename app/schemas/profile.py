"""
User Profile Schemas
Request/Response models for user profile management
"""

import enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional

# Use string enums to avoid circular imports
class EnglishLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class PrimaryGoal(str, enum.Enum):
    FLUENCY = "FLUENCY"
    EXAM = "EXAM"
    BUSINESS = "BUSINESS"
    TRAVEL = "TRAVEL"

class ProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="User's full name")
    english_level: Optional[EnglishLevel] = Field(None, description="English proficiency level")
    primary_goal: Optional[PrimaryGoal] = Field(None, description="Primary learning goal")
    avatar_url: Optional[str] = Field(None, description="Avatar URL (for direct URL update)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("Name cannot be empty")
        return v.strip() if v else v

class AvatarUploadResponse(BaseModel):
    """Response after avatar upload"""
    avatar_url: str = Field(..., description="URL of uploaded avatar")
    message: str = Field(default="Avatar uploaded successfully")

class ProfileStats(BaseModel):
    """User profile statistics"""
    streak_days: int = Field(..., description="Current streak in days")
    total_practice_minutes: int = Field(..., description="Total practice time in minutes")
    total_practice_hours: float = Field(..., description="Total practice time in hours")
    completed_cycles: int = Field(default=0, description="Number of completed 30-day cycles")
    vocabulary_learned: int = Field(default=0, description="Number of vocabulary words learned")
    speaking_exercises_completed: int = Field(default=0, description="Speaking exercises completed")
    writing_submissions: int = Field(default=0, description="Writing submissions")
    achievements_earned: int = Field(default=0, description="Achievements earned")

class ProfilePreferences(BaseModel):
    """User preferences (for future use)"""
    email_notifications: bool = Field(default=True, description="Receive email notifications")
    daily_reminder: bool = Field(default=True, description="Receive daily practice reminders")
    reminder_time: Optional[str] = Field(None, description="Preferred reminder time (HH:MM)")
    language_interface: str = Field(default="en", description="Interface language")
    theme: str = Field(default="light", description="UI theme (light/dark)")

class ProfilePreferencesUpdate(BaseModel):
    """Schema for updating user preferences"""
    email_notifications: Optional[bool] = None
    daily_reminder: Optional[bool] = None
    reminder_time: Optional[str] = None
    language_interface: Optional[str] = None
    theme: Optional[str] = None
    
    @field_validator('reminder_time')
    @classmethod
    def validate_reminder_time(cls, v):
        if v is not None:
            # Validate HH:MM format
            try:
                hours, minutes = v.split(':')
                h, m = int(hours), int(minutes)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except:
                raise ValueError("reminder_time must be in HH:MM format (e.g., '09:00')")
        return v

class FullProfile(BaseModel):
    """Complete user profile with stats"""
    # Basic info
    id: str
    email: str
    name: str
    avatar_url: Optional[str]
    english_level: EnglishLevel
    primary_goal: PrimaryGoal
    role: str
    is_email_verified: bool
    
    # OAuth info
    google_id: Optional[str]
    
    # Stats
    streak_days: int
    total_practice_minutes: int
    
    # Timestamps
    created_at: str
    last_active_at: str
    
    # Additional stats
    stats: Optional[ProfileStats] = None
    
    class Config:
        from_attributes = True
