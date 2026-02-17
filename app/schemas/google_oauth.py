"""
Google OAuth Schemas
Request/Response models for Google OAuth endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional

class GoogleAuthURLResponse(BaseModel):
    """Response containing Google OAuth authorization URL"""
    authorization_url: str = Field(..., description="URL to redirect user to for Google OAuth")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection")

class GoogleCallbackRequest(BaseModel):
    """Request body for Google OAuth callback"""
    code: str = Field(..., description="Authorization code from Google")
    state: Optional[str] = Field(None, description="State parameter for CSRF verification")

class GoogleTokenRequest(BaseModel):
    """Request body for Google ID token authentication (frontend OAuth)"""
    id_token: str = Field(..., description="Google ID token from frontend")

class GoogleLinkRequest(BaseModel):
    """Request body for linking Google account"""
    id_token: str = Field(..., description="Google ID token to link")

class GoogleAccountStatus(BaseModel):
    """Response showing Google account link status"""
    is_linked: bool = Field(..., description="Whether Google account is linked")
    google_email: Optional[str] = Field(None, description="Linked Google email")
    linked_at: Optional[str] = Field(None, description="When account was linked")
