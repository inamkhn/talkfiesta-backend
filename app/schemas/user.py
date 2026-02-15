from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class EnglishLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class PrimaryGoal(str, Enum):
    FLUENCY = "FLUENCY"
    EXAM = "EXAM"
    BUSINESS = "BUSINESS"
    TRAVEL = "TRAVEL"

# Request Schemas
class UserRegister(BaseModel):
    """User registration schema"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2, max_length=100)

class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    """User profile update schema"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None
    english_level: Optional[EnglishLevel] = None
    primary_goal: Optional[PrimaryGoal] = None

class PasswordChange(BaseModel):
    """Password change schema"""
    current_password: str
    new_password: str = Field(..., min_length=8)

class PasswordReset(BaseModel):
    """Password reset schema"""
    token: str
    new_password: str = Field(..., min_length=8)

class EmailRequest(BaseModel):
    """Email request schema"""
    email: EmailStr

class AssessmentAnswer(BaseModel):
    """Assessment answer schema"""
    question_id: int
    answer: str

class AssessmentSubmission(BaseModel):
    """Assessment submission schema"""
    answers: list[AssessmentAnswer]

# Response Schemas
class UserBase(BaseModel):
    """Base user schema"""
    id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    english_level: EnglishLevel
    primary_goal: PrimaryGoal
    role: UserRole = UserRole.USER

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    """User response with additional fields"""
    streak_days: int
    total_practice_minutes: int
    created_at: datetime
    last_active_at: datetime

class UserWithTokens(BaseModel):
    """User response with authentication tokens"""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class GoogleAuthResponse(BaseModel):
    """Google OAuth response"""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False

class AssessmentResult(BaseModel):
    """Assessment result schema"""
    assessed_level: EnglishLevel
    score: float
    recommendations: list[str]
