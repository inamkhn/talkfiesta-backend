"""
Google OAuth Endpoints
Handles Google OAuth authentication flow
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService
from app.schemas.user import UserWithTokens, UserResponse
from app.schemas.google_oauth import (
    GoogleAuthURLResponse,
    GoogleCallbackRequest,
    GoogleTokenRequest,
    GoogleLinkRequest,
    GoogleAccountStatus
)
from app.schemas.common import MessageResponse

router = APIRouter()

# ============================================
# GOOGLE OAUTH FLOW (Backend)
# ============================================

@router.get("/url", response_model=GoogleAuthURLResponse)
async def get_google_auth_url():
    """
    Get Google OAuth authorization URL
    
    Redirect user to this URL to start OAuth flow.
    User will be redirected back to your callback URL after authorization.
    """
    google_service = GoogleOAuthService()
    
    # Generate state for CSRF protection (optional but recommended)
    import secrets
    state = secrets.token_urlsafe(32)
    
    auth_url = google_service.get_authorization_url(state=state)
    
    return {
        "authorization_url": auth_url,
        "state": state
    }

@router.post("/callback", response_model=UserWithTokens)
async def google_oauth_callback(
    callback_data: GoogleCallbackRequest,
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback
    
    Exchange authorization code for user info and authenticate/create user.
    
    - **code**: Authorization code from Google
    - **state**: State parameter for CSRF verification (optional)
    
    Returns user data with access and refresh tokens.
    """
    google_service = GoogleOAuthService()
    auth_service = AuthService(db)
    
    # Exchange code for user info
    google_user_info = await google_service.authenticate_with_code(callback_data.code)
    
    # Authenticate or create user
    user, access_token, refresh_token = auth_service.authenticate_google_user(google_user_info)
    
    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================
# GOOGLE OAUTH (Frontend - ID Token)
# ============================================

@router.post("/token", response_model=UserWithTokens)
async def google_oauth_token(
    token_data: GoogleTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate with Google ID token (for frontend OAuth)
    
    Use this endpoint when implementing Google Sign-In on the frontend.
    The frontend gets the ID token from Google and sends it here.
    
    - **id_token**: Google ID token from frontend
    
    Returns user data with access and refresh tokens.
    """
    google_service = GoogleOAuthService()
    auth_service = AuthService(db)
    
    # Verify ID token and get user info
    google_user_info = await google_service.authenticate_with_token(token_data.id_token)
    
    # Authenticate or create user
    user, access_token, refresh_token = auth_service.authenticate_google_user(google_user_info)
    
    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================
# LINK/UNLINK GOOGLE ACCOUNT
# ============================================

@router.post("/link", response_model=UserResponse)
async def link_google_account(
    link_data: GoogleLinkRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Link Google account to existing user
    
    Requires authentication. Links a Google account to the current user.
    
    - **id_token**: Google ID token to link
    
    Returns updated user data.
    """
    google_service = GoogleOAuthService()
    auth_service = AuthService(db)
    
    # Verify ID token and get user info
    google_user_info = await google_service.authenticate_with_token(link_data.id_token)
    
    # Link Google account
    user = auth_service.link_google_account(current_user.id, google_user_info)
    
    return user

@router.post("/unlink", response_model=UserResponse)
async def unlink_google_account(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlink Google account from user
    
    Requires authentication. Removes Google account link from current user.
    Note: Cannot unlink if it's the only authentication method.
    """
    auth_service = AuthService(db)
    
    # Unlink Google account
    user = auth_service.unlink_google_account(current_user.id)
    
    return user

@router.get("/status", response_model=GoogleAccountStatus)
async def get_google_account_status(
    current_user = Depends(get_current_user)
):
    """
    Get Google account link status
    
    Requires authentication. Returns whether a Google account is linked.
    """
    is_linked = current_user.google_id is not None
    
    return {
        "is_linked": is_linked,
        "google_email": current_user.email if is_linked else None,
        "linked_at": current_user.updated_at.isoformat() if is_linked else None
    }
