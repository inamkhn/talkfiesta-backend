from pydantic import BaseModel

# Request Schemas
class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str

class GoogleCallbackRequest(BaseModel):
    """Google OAuth callback request"""
    code: str
    state: str

class VerifyEmailRequest(BaseModel):
    """Email verification request"""
    token: str

# Response Schemas
class GoogleAuthURLResponse(BaseModel):
    """Google OAuth URL response"""
    authorization_url: str
    state: str
