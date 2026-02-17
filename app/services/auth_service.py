from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import secrets
import uuid

from app.models.user import User, RefreshToken, UserRole, EnglishLevel, PrimaryGoal
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.schemas.user import UserRegister, UserLogin
from app.config import settings

class AuthService:
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # USER REGISTRATION
    # ============================================
    
    def register_user(self, user_data: UserRegister) -> Tuple[User, str, str]:
        """
        Register a new user with email and password
        Returns: (user, access_token, refresh_token)
        """
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            name=user_data.name,
            password_hash=get_password_hash(user_data.password),
            role=UserRole.USER,
            english_level=EnglishLevel.B1,
            primary_goal=PrimaryGoal.FLUENCY,
            is_active=True,
            is_email_verified=False,  # Will be verified later
            email_verification_token=secrets.token_urlsafe(32),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_active_at=datetime.utcnow()
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Generate tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token_str = create_refresh_token(data={"sub": user.id})
        
        # Save refresh token to database
        self._save_refresh_token(user.id, refresh_token_str)
        
        return user, access_token, refresh_token_str
    
    # ============================================
    # USER LOGIN
    # ============================================
    
    def login_user(self, login_data: UserLogin) -> Tuple[User, str, str]:
        """
        Authenticate user with email and password
        Returns: (user, access_token, refresh_token)
        """
        # Find user by email
        user = self.db.query(User).filter(User.email == login_data.email).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user has password (not OAuth user)
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account uses Google Sign-In. Please login with Google."
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )
        
        # Update last active
        user.last_active_at = datetime.utcnow()
        self.db.commit()
        
        # Generate tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token_str = create_refresh_token(data={"sub": user.id})
        
        # Save refresh token
        self._save_refresh_token(user.id, refresh_token_str)
        
        return user, access_token, refresh_token_str
    
    # ============================================
    # TOKEN REFRESH
    # ============================================
    
    def refresh_access_token(self, refresh_token_str: str) -> Tuple[str, str]:
        """
        Refresh access token using refresh token
        Returns: (new_access_token, new_refresh_token)
        """
        # Decode refresh token
        try:
            payload = decode_token(refresh_token_str)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Check if refresh token exists and is not revoked
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token_str,
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).first()
        
        if not db_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found or revoked"
            )
        
        # Check if token is expired
        if db_token.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        # Verify user exists and is active
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Revoke old refresh token
        db_token.is_revoked = True
        self.db.commit()
        
        # Generate new tokens
        new_access_token = create_access_token(data={"sub": user_id})
        new_refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Save new refresh token
        self._save_refresh_token(user_id, new_refresh_token)
        
        return new_access_token, new_refresh_token
    
    # ============================================
    # LOGOUT
    # ============================================
    
    def logout_user(self, user_id: str, refresh_token_str: Optional[str] = None):
        """Logout user by revoking refresh token(s)"""
        if refresh_token_str:
            # Revoke specific token
            token = self.db.query(RefreshToken).filter(
                RefreshToken.token == refresh_token_str,
                RefreshToken.user_id == user_id
            ).first()
            if token:
                token.is_revoked = True
        else:
            # Revoke all user's tokens
            self.db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            ).update({"is_revoked": True})
        
        self.db.commit()
    
    # ============================================
    # PASSWORD MANAGEMENT
    # ============================================
    
    def change_password(self, user_id: str, current_password: str, new_password: str):
        """Change user password"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not user.password_hash or not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        user.password_hash = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Revoke all refresh tokens (force re-login)
        self.logout_user(user_id)
    
    def request_password_reset(self, email: str) -> Optional[str]:
        """Generate password reset token"""
        user = self.db.query(User).filter(User.email == email).first()
        
        if not user:
            # Don't reveal if email exists
            return None
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return reset_token
    
    def reset_password(self, token: str, new_password: str):
        """Reset password using reset token"""
        user = self.db.query(User).filter(
            User.password_reset_token == token
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Check if token is expired
        if not user.password_reset_expires or user.password_reset_expires < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired"
            )
        
        # Update password
        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Revoke all refresh tokens
        self.logout_user(user.id)
    
    # ============================================
    # EMAIL VERIFICATION
    # ============================================
    
    def verify_email(self, token: str):
        """Verify user email with token"""
        user = self.db.query(User).filter(
            User.email_verification_token == token
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )
        
        user.is_email_verified = True
        user.email_verification_token = None
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
    
    def resend_verification_email(self, user_id: str) -> str:
        """Generate new verification token"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
        
        # Generate new token
        verification_token = secrets.token_urlsafe(32)
        user.email_verification_token = verification_token
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return verification_token
    
    # ============================================
    # HELPER METHODS
    # ============================================
    
    def _save_refresh_token(self, user_id: str, token: str):
        """Save refresh token to database"""
        refresh_token = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=datetime.utcnow(),
            is_revoked=False
        )
        
        self.db.add(refresh_token)
        self.db.commit()

    # ============================================
    # GOOGLE OAUTH AUTHENTICATION
    # ============================================
    
    def authenticate_google_user(self, google_user_info: dict) -> Tuple[User, str, str]:
        """
        Authenticate or create user from Google OAuth
        Returns: (user, access_token, refresh_token)
        """
        google_id = google_user_info["google_id"]
        email = google_user_info["email"]
        
        # Try to find user by Google ID first
        user = self.db.query(User).filter(User.google_id == google_id).first()
        
        if user:
            # User exists with this Google ID - login
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive. Please contact support."
                )
            
            # Update last active and avatar if changed
            user.last_active_at = datetime.utcnow()
            if google_user_info.get("avatar_url"):
                user.avatar_url = google_user_info["avatar_url"]
            self.db.commit()
            
        else:
            # Check if user exists with this email (email/password account)
            user = self.db.query(User).filter(User.email == email).first()
            
            if user:
                # User exists with email/password - link Google account
                if user.google_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This email is already linked to another Google account"
                    )
                
                # Link Google account to existing user
                user.google_id = google_id
                user.is_email_verified = True  # Google emails are verified
                user.last_active_at = datetime.utcnow()
                if google_user_info.get("avatar_url") and not user.avatar_url:
                    user.avatar_url = google_user_info["avatar_url"]
                self.db.commit()
                
            else:
                # Create new user from Google account
                user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    name=google_user_info.get("name", email.split("@")[0]),
                    google_id=google_id,
                    avatar_url=google_user_info.get("avatar_url"),
                    password_hash=None,  # No password for OAuth users
                    role=UserRole.USER,
                    english_level=EnglishLevel.B1,
                    primary_goal=PrimaryGoal.FLUENCY,
                    is_active=True,
                    is_email_verified=True,  # Google emails are verified
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    last_active_at=datetime.utcnow()
                )
                
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
        
        # Generate tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token_str = create_refresh_token(data={"sub": user.id})
        
        # Save refresh token
        self._save_refresh_token(user.id, refresh_token_str)
        
        return user, access_token, refresh_token_str
    
    def link_google_account(self, user_id: str, google_user_info: dict) -> User:
        """
        Link Google account to existing user
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.google_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google account already linked"
            )
        
        google_id = google_user_info["google_id"]
        
        # Check if this Google ID is already used by another user
        existing_google_user = self.db.query(User).filter(User.google_id == google_id).first()
        if existing_google_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another user"
            )
        
        # Link Google account
        user.google_id = google_id
        user.is_email_verified = True
        user.updated_at = datetime.utcnow()
        if google_user_info.get("avatar_url") and not user.avatar_url:
            user.avatar_url = google_user_info["avatar_url"]
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def unlink_google_account(self, user_id: str) -> User:
        """
        Unlink Google account from user
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.google_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Google account linked"
            )
        
        # Check if user has a password (can't unlink if it's the only auth method)
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unlink Google account. Please set a password first."
            )
        
        # Unlink Google account
        user.google_id = None
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
