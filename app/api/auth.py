import logging
from fastapi import APIRouter, Depends, Query, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    LoginRequest, TokenResponse,
    RefreshRequest, ChangePasswordRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    VerifyEmailRequest, ResendVerificationRequest,
    UserResponse,
)
from app.services.auth_service import (
    register_user, login_user, refresh_tokens, change_password,
    forgot_password, reset_password, verify_email, resend_verification,
    logout_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = register_user(db, data)
    return RegisterResponse(
        message="Account created successfully.",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password (JSON). Returns access + refresh tokens."""
    return login_user(db, data)


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
@limiter.limit("5/minute")
def login_form(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 form-based login — used by Swagger UI 'Authorize' button only."""
    data = LoginRequest(email=form_data.username, password=form_data.password)
    return login_user(db, data)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
def refresh(request: Request, data: RefreshRequest, db: Session = Depends(get_db)):
    """Get a new access + refresh token pair using a valid refresh token."""
    return refresh_tokens(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout: revoke all server-side refresh sessions; client must discard tokens."""
    logout_user(db, current_user.id)
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_pwd(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password."""
    change_password(db, current_user, data.current_password, data.new_password)
    return {"message": "Password changed successfully."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def forgot_pwd(request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset email.
    Always returns 200 — never reveals whether the email exists.
    """
    forgot_password(db, data.email)
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def reset_pwd(request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using the token received by email."""
    reset_password(db, data.token, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def verify_email_endpoint(request: Request, data: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email address using the token received by email (JSON body)."""
    verify_email(db, data.token)
    return {"message": "Email verified successfully."}


@router.get("/verify-email", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def verify_email_via_query(
    request: Request,
    token: str = Query(..., description="Token from the verification email link"),
    db: Session = Depends(get_db),
):
    """Verify email using ?token=... (convenient for simple clients and deep links)."""
    verify_email(db, token)
    return {"message": "Email verified successfully."}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def resend_verification_endpoint(request: Request, data: ResendVerificationRequest, db: Session = Depends(get_db)):
    """
    Resend the email verification link.
    Always returns 200 — never reveals whether the email exists.
    """
    resend_verification(db, data.email)
    return {"message": "If that email is registered and unverified, a new verification link has been sent."}
