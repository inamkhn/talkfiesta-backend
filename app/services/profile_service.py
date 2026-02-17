"""
User Profile Service
Handles user profile management operations
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.user import User
from app.models.achievement import UserAchievement
from app.models.vocabulary import UserVocabulary
from app.models.speaking import SpeakingSubmission
from app.models.writing import WritingSubmission
from app.models.plan import CycleCompletion
from app.schemas.profile import ProfileUpdate, ProfileStats

class ProfileService:
    """Service for user profile operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_profile(self, user_id: str) -> User:
        """Get user profile by ID"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    
    def update_profile(self, user_id: str, profile_data: ProfileUpdate) -> User:
        """Update user profile"""
        user = self.get_user_profile(user_id)
        
        # Update only provided fields
        update_data = profile_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def update_avatar(self, user_id: str, avatar_url: str) -> User:
        """Update user avatar URL"""
        user = self.get_user_profile(user_id)
        
        user.avatar_url = avatar_url
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def delete_avatar(self, user_id: str) -> User:
        """Remove user avatar"""
        user = self.get_user_profile(user_id)
        
        user.avatar_url = None
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def get_profile_stats(self, user_id: str) -> ProfileStats:
        """Get user profile statistics"""
        user = self.get_user_profile(user_id)
        
        # Get completed cycles count
        completed_cycles = self.db.query(func.count(CycleCompletion.id)).filter(
            CycleCompletion.user_id == user_id
        ).scalar() or 0
        
        # Get vocabulary learned count (status = MASTERED or LEARNING)
        vocabulary_learned = self.db.query(func.count(UserVocabulary.id)).filter(
            UserVocabulary.user_id == user_id,
            UserVocabulary.status.in_(["LEARNING", "MASTERED"])
        ).scalar() or 0
        
        # Get speaking exercises completed
        speaking_completed = self.db.query(func.count(SpeakingSubmission.id)).filter(
            SpeakingSubmission.user_id == user_id
        ).scalar() or 0
        
        # Get writing submissions
        writing_submissions = self.db.query(func.count(WritingSubmission.id)).filter(
            WritingSubmission.user_id == user_id
        ).scalar() or 0
        
        # Get achievements earned
        achievements_earned = self.db.query(func.count(UserAchievement.id)).filter(
            UserAchievement.user_id == user_id
        ).scalar() or 0
        
        # Calculate total practice hours
        total_practice_hours = round(user.total_practice_minutes / 60, 2)
        
        return ProfileStats(
            streak_days=user.streak_days,
            total_practice_minutes=user.total_practice_minutes,
            total_practice_hours=total_practice_hours,
            completed_cycles=completed_cycles,
            vocabulary_learned=vocabulary_learned,
            speaking_exercises_completed=speaking_completed,
            writing_submissions=writing_submissions,
            achievements_earned=achievements_earned
        )
    
    def delete_account(self, user_id: str) -> None:
        """
        Delete user account (soft delete - deactivate)
        For hard delete, use with caution
        """
        user = self.get_user_profile(user_id)
        
        # Soft delete - deactivate account
        user.is_active = False
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # For hard delete (uncomment if needed):
        # self.db.delete(user)
        # self.db.commit()
    
    def reactivate_account(self, user_id: str) -> User:
        """Reactivate deactivated account"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = True
        user.updated_at = datetime.utcnow()
        user.last_active_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
