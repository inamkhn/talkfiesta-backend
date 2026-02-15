from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str

class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PaginationParams(BaseModel):
    """Pagination parameters"""
    limit: int = 20
    offset: int = 0

class TimestampMixin(BaseModel):
    """Mixin for created_at and updated_at"""
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
