"""
User Profile Endpoints
Handles user profile management
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.profile_service import ProfileService
from app.schemas.user import UserResponse
from app.schemas.profile import (
    ProfileUpdate,
    AvatarUploadResponse,
    ProfileStats,
    FullProfile
)
from app.schemas.common import MessageResponse

router = APIRouter()

# ============================================
# GET PROFILE
# ============================================

@router.get("/me", response_model=FullProfile)
async def get_my_profile(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user profile with statistics
    
    Returns complete profile including learning stats.
    """
    profile_service = ProfileService(db)
    
    # Get stats
    stats = profile_service.get_profile_stats(current_user.id)
    
    # Build full profile
    profile_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "english_level": current_user.english_level,
        "primary_goal": current_user.primary_goal,
        "role": current_user.role.value,
        "is_email_verified": current_user.is_email_verified,
        "google_id": current_user.google_id,
        "streak_days": current_user.streak_days,
        "total_practice_minutes": current_user.total_practice_minutes,
        "created_at": current_user.created_at.isoformat(),
        "last_active_at": current_user.last_active_at.isoformat(),
        "stats": stats
    }
    
    return profile_dict

@router.get("/me/stats", response_model=ProfileStats)
async def get_profile_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user profile statistics only
    
    Returns learning statistics and progress without full profile data.
    """
    profile_service = ProfileService(db)
    return profile_service.get_profile_stats(current_user.id)

# ============================================
# UPDATE PROFILE
# ============================================

@router.patch("/me", response_model=FullProfile)
async def update_my_profile(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    name: Optional[str] = None,
    english_level: Optional[str] = None,
    primary_goal: Optional[str] = None,
    avatar_url: Optional[str] = None,
    file: UploadFile = File(None)
):
    """
    Update current user profile
    
    Update profile fields:
    - **name**: User's full name
    - **english_level**: English proficiency level (A1-C2)
    - **primary_goal**: Learning goal (FLUENCY, EXAM, BUSINESS, TRAVEL)
    - **avatar_url**: Direct avatar URL update (optional)
    
    You can also upload an avatar file using multipart/form-data.
    
    Only provided fields will be updated.
    """
    profile_service = ProfileService(db)
    
    # Handle file upload if provided
    if file is not None:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Validate file size (5MB max)
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()  # Get position (file size)
        file.file.seek(0)  # Reset to start
        
        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 5MB"
            )
        
        # TODO: Upload to cloud storage
        # For now, return a mock URL
        mock_avatar_url = f"https://api.dicebear.com/7.x/avataaars/svg?seed={current_user.id}"
        
        # Update user avatar
        profile_service.update_avatar(current_user.id, mock_avatar_url)
        db.refresh(current_user)
    
    # Build update data from individual parameters
    update_data = {}
    if name is not None:
        update_data['name'] = name
    if english_level is not None:
        update_data['english_level'] = english_level
    if primary_goal is not None:
        update_data['primary_goal'] = primary_goal
    if avatar_url is not None:
        update_data['avatar_url'] = avatar_url
    
    # Handle avatar_url update
    if 'avatar_url' in update_data:
        profile_service.update_avatar(current_user.id, update_data['avatar_url'])
        del update_data['avatar_url']
        db.refresh(current_user)
    
    # Update other fields if any remain
    if update_data:
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        current_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
    
    # Get updated profile with stats
    stats = profile_service.get_profile_stats(current_user.id)
    
    profile_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "english_level": current_user.english_level,
        "primary_goal": current_user.primary_goal,
        "role": current_user.role.value,
        "is_email_verified": current_user.is_email_verified,
        "google_id": current_user.google_id,
        "streak_days": current_user.streak_days,
        "total_practice_minutes": current_user.total_practice_minutes,
        "created_at": current_user.created_at.isoformat(),
        "last_active_at": current_user.last_active_at.isoformat(),
        "stats": stats
    }
    
    return profile_dict

# ============================================
# ACCOUNT MANAGEMENT
# ============================================

@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete user account (soft delete)
    
    Deactivates the account. User can reactivate by contacting support.
    For permanent deletion, contact support.
    """
    profile_service = ProfileService(db)
    profile_service.delete_account(current_user.id)
    
    return {"message": "Account deactivated successfully"}

# ============================================
# PUBLIC PROFILE (Optional)
# ============================================

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile_by_id(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get public user profile by ID
    
    Returns basic public information about a user.
    This endpoint is public (no authentication required).
    """
    profile_service = ProfileService(db)
    user = profile_service.get_user_profile(user_id)
    
    # Return only public information
    return user
