from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.auth_service import AuthService
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserWithTokens,
    UserResponse,
    PasswordChange,
    PasswordReset,
    EmailRequest
)
from app.schemas.auth import RefreshTokenRequest, VerifyEmailRequest
from app.schemas.common import MessageResponse, TokenResponse

router = APIRouter()

# ============================================
# REGISTRATION
# ============================================

@router.post("/register", response_model=UserWithTokens, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and password.
    
    - **email**: Valid email address
    - **password**: Minimum 8 characters
    - **name**: User's full name
    
    Returns user data with access and refresh tokens.
    """
    auth_service = AuthService(db)
    user, access_token, refresh_token = auth_service.register_user(user_data)
    
    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================
# LOGIN
# ============================================

@router.post("/login", response_model=UserWithTokens)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns user data with access and refresh tokens.
    """
    auth_service = AuthService(db)
    user, access_token, refresh_token = auth_service.login_user(login_data)
    
    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================
# TOKEN REFRESH
# ============================================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    
    Returns new access and refresh tokens.
    """
    auth_service = AuthService(db)
    access_token, refresh_token = auth_service.refresh_access_token(token_data.refresh_token)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================
# LOGOUT
# ============================================

@router.post("/logout", response_model=MessageResponse)
async def logout(
    token_data: RefreshTokenRequest = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user by revoking refresh token.
    
    Optionally provide refresh_token to revoke specific token,
    otherwise all user's tokens will be revoked.
    """
    auth_service = AuthService(db)
    refresh_token = token_data.refresh_token if token_data else None
    auth_service.logout_user(current_user.id, refresh_token)
    
    return {"message": "Successfully logged out"}

# ============================================
# PASSWORD MANAGEMENT
# ============================================

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password for authenticated user.
    
    - **current_password**: Current password
    - **new_password**: New password (minimum 8 characters)
    
    All refresh tokens will be revoked after password change.
    """
    auth_service = AuthService(db)
    auth_service.change_password(
        current_user.id,
        password_data.current_password,
        password_data.new_password
    )
    
    return {"message": "Password changed successfully"}

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    email_data: EmailRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset email.
    
    - **email**: User's email address
    
    If email exists, a reset token will be generated.
    For security, always returns success message.
    """
    auth_service = AuthService(db)
    reset_token = auth_service.request_password_reset(email_data.email)
    
    # TODO: Send email with reset token
    # For now, you can log it or return it in development
    # In production, send email and don't return token
    
    return {"message": "Password reset email sent if account exists"}

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """
    Reset password using reset token from email.
    
    - **token**: Reset token from email
    - **new_password**: New password (minimum 8 characters)
    
    All refresh tokens will be revoked after password reset.
    """
    auth_service = AuthService(db)
    auth_service.reset_password(reset_data.token, reset_data.new_password)
    
    return {"message": "Password reset successful"}

# ============================================
# EMAIL VERIFICATION
# ============================================

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    verify_data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify email address using verification token.
    
    - **token**: Verification token from email
    """
    auth_service = AuthService(db)
    auth_service.verify_email(verify_data.token)
    
    return {"message": "Email verified successfully"}

@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resend email verification token.
    
    Requires authentication.
    """
    auth_service = AuthService(db)
    verification_token = auth_service.resend_verification_email(current_user.id)
    
    # TODO: Send email with verification token
    # For now, you can log it or return it in development
    
    return {"message": "Verification email sent"}

# ============================================
# TEST ENDPOINT (Protected)
# ============================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Requires valid access token.
    """
    return current_user
