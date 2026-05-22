import uuid
import secrets
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.config import settings
from app.models.user import User
from app.models.refresh_token import RefreshTokenRecord
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse
from app.utils.email import send_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)

VERIFICATION_TOKEN_EXPIRE_HOURS = 24
RESET_TOKEN_EXPIRE_HOURS = 1


def revoke_all_user_refresh_tokens(db: Session, user_id: str) -> None:
    """Invalidate all refresh sessions for a user (logout, password change, etc.)."""
    now = datetime.utcnow()
    db.query(RefreshTokenRecord).filter(
        RefreshTokenRecord.user_id == user_id,
        RefreshTokenRecord.revoked_at.is_(None),
    ).update({RefreshTokenRecord.revoked_at: now}, synchronize_session=False)


def logout_user(db: Session, user_id: str) -> None:
    revoke_all_user_refresh_tokens(db, user_id)
    db.commit()


def register_user(db: Session, data: RegisterRequest) -> User:
    # Check duplicates — case-insensitive email check
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    user = User(
        id=str(uuid.uuid4()),
        username=data.username,           # already lowercased by validator
        email=data.email.lower(),         # normalize email to lowercase
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception(f"DB error during registration for {data.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )

    # Persist verification token, then send email (rollback only if DB write fails)
    token: str | None = None
    try:
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        user.verification_token_expires = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"Failed to save verification token for {user.email}")
    else:
        try:
            send_verification_email(user.email, user.full_name or "", token)
        except Exception:
            logger.exception(f"Failed to send verification email to {user.email}")

    logger.info(f"New user registered: {user.email}")
    return user


def login_user(db: Session, data: LoginRequest) -> dict:
    user = db.query(User).filter(User.email == data.email.lower()).first()

    # FIX: check is_active BEFORE verifying password to avoid leaking account existence
    # Use same generic error for both "not found" and "wrong password" — prevents user enumeration
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    now = datetime.utcnow()
    family_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    exp_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    try:
        user.last_login = now
        db.add(
            RefreshTokenRecord(
                id=str(uuid.uuid4()),
                user_id=user.id,
                jti=jti,
                family_id=family_id,
                expires_at=exp_at,
                created_at=now,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"Failed to persist session for {user.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )

    logger.info(f"User logged in: {user.email}")

    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id, jti, family_id, exp_at),
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    payload, error = decode_token(refresh_token)

    if error == "expired":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )

    if error or not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")
    fam = payload.get("fam")
    if not user_id or not jti or not fam:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled",
        )

    now = datetime.utcnow()

    row = (
        db.query(RefreshTokenRecord)
        .filter(
            RefreshTokenRecord.jti == jti,
            RefreshTokenRecord.user_id == user_id,
            RefreshTokenRecord.revoked_at.is_(None),
            RefreshTokenRecord.expires_at > now,
        )
        .with_for_update()
        .first()
    )

    if row:
        if row.family_id != fam:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        try:
            row.revoked_at = now
            new_jti = str(uuid.uuid4())
            exp_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            db.add(
                RefreshTokenRecord(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    jti=new_jti,
                    family_id=fam,
                    expires_at=exp_at,
                    created_at=now,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to rotate refresh token for user %s", user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not refresh session. Please try again.",
            )

        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id, new_jti, fam, exp_at),
            "token_type": "bearer",
            "user": None,
        }

    stale = db.query(RefreshTokenRecord).filter(RefreshTokenRecord.jti == jti).first()
    if stale:
        if stale.user_id != user_id:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        if stale.revoked_at is not None:
            db.rollback()
            logger.warning(
                "Attempt to use a revoked refresh token (user_id=%s)",
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        if stale.expires_at <= now:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please log in again.",
            )

    db.rollback()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # FIX: prevent setting the same password
    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    try:
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        revoke_all_user_refresh_tokens(db, user.id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"Failed to change password for {user.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password. Please try again.",
        )

    logger.info(f"Password changed for user: {user.email}")


def forgot_password(db: Session, email: str) -> None:
    """
    Generate a password reset token and email it.
    Always returns success — never reveals whether email exists (prevents enumeration).
    """
    user = db.query(User).filter(User.email == email.lower(), User.is_active == True).first()

    if not user:
        # Silent return — don't leak that email doesn't exist
        logger.info(f"Forgot password requested for unknown email: {email}")
        return

    revoke_all_user_refresh_tokens(db, user.id)

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)

    try:
        db.commit()
        send_password_reset_email(user.email, user.full_name or "", token)
        logger.info(f"Password reset email sent to: {user.email}")
    except Exception:
        db.rollback()
        logger.exception(f"Failed to process forgot password for {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reset email. Please try again.",
        )


def reset_password(db: Session, token: str, new_password: str) -> None:
    """Validate reset token and set new password."""
    user = db.query(User).filter(User.reset_token == token).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if user.reset_token_expires < datetime.utcnow():
        # Clear expired token
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Prevent reusing the same password
    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    try:
        user.password_hash = hash_password(new_password)
        user.reset_token = None           # invalidate token after use
        user.reset_token_expires = None
        user.updated_at = datetime.utcnow()
        revoke_all_user_refresh_tokens(db, user.id)
        db.commit()
        logger.info(f"Password reset successful for: {user.email}")
    except Exception:
        db.rollback()
        logger.exception(f"Failed to reset password for token {token}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again.",
        )


def verify_email(db: Session, token: str) -> None:
    """Mark user as verified using the email verification token."""
    user = db.query(User).filter(User.verification_token == token).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    if user.is_verified:
        # Already verified — not an error, just idempotent
        return

    if user.verification_token_expires < datetime.utcnow():
        user.verification_token = None
        user.verification_token_expires = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please request a new one.",
        )

    try:
        user.is_verified = True
        user.verification_token = None        # invalidate after use
        user.verification_token_expires = None
        user.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Email verified for: {user.email}")
    except Exception:
        db.rollback()
        logger.exception(f"Failed to verify email for token {token}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email. Please try again.",
        )


def resend_verification(db: Session, email: str) -> None:
    """
    Resend verification email.
    Silent return if email not found — prevents enumeration.
    """
    user = db.query(User).filter(User.email == email.lower(), User.is_active == True).first()

    if not user:
        logger.info(f"Resend verification requested for unknown email: {email}")
        return

    if user.is_verified:
        # Idempotent — same response as unknown email (no enumeration)
        logger.info(f"Resend verification ignored; already verified: {email}")
        return

    token = secrets.token_urlsafe(32)
    user.verification_token = token
    user.verification_token_expires = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)

    try:
        db.commit()
        send_verification_email(user.email, user.full_name or "", token)
        logger.info(f"Verification email resent to: {user.email}")
    except Exception:
        db.rollback()
        logger.exception(f"Failed to resend verification for {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again.",
        )
