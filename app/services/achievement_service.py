"""
Achievement Service
Handles business logic for achievements
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.achievement import Achievement, UserAchievement, AchievementType
from app.models.user import User


class AchievementService:
    """Service for managing achievements"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # GET ACHIEVEMENTS
    # ============================================
    
    def get_achievements(
        self,
        achievement_type: Optional[AchievementType] = None,
        difficulty: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Achievement]:
        """
        Get achievements with optional filters
        
        Args:
            achievement_type: Filter by type
            difficulty: Filter by difficulty
            limit: Maximum records to return
            offset: Pagination offset
            
        Returns:
            List of Achievement objects
        """
        query = self.db.query(Achievement)
        
        if achievement_type is not None:
            query = query.filter(Achievement.achievement_type == achievement_type)
        
        if difficulty is not None:
            query = query.filter(Achievement.difficulty == difficulty)
        
        achievements = query.order_by(
            Achievement.difficulty,
            Achievement.title
        ).limit(limit).offset(offset).all()
        
        return achievements
    
    # ============================================
    # GET ACHIEVEMENT BY ID
    # ============================================
    
    def get_achievement_by_id(self, achievement_id: str) -> Achievement:
        """
        Get specific achievement by ID
        
        Args:
            achievement_id: Achievement ID
            
        Returns:
            Achievement object
            
        Raises:
            HTTPException: If achievement not found
        """
        achievement = self.db.query(Achievement).filter(
            Achievement.id == achievement_id
        ).first()
        
        if not achievement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Achievement not found"
            )
        
        return achievement
    
    # ============================================
    # GET USER ACHIEVEMENTS
    # ============================================
    
    def get_user_achievements(
        self,
        user_id: str,
        achievement_type: Optional[AchievementType] = None,
        unlocked: Optional[bool] = None
    ) -> List[UserAchievement]:
        """
        Get user's achievements
        
        Args:
            user_id: User ID
            achievement_type: Filter by type
            unlocked: Filter by unlocked status
            
        Returns:
            List of UserAchievement objects
        """
        query = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).order_by(
            desc(UserAchievement.unlocked_at)
        )
        
        if achievement_type is not None:
            query = query.filter(UserAchievement.achievement.has(
                Achievement.achievement_type == achievement_type
            ))
        
        if unlocked is not None:
            if unlocked:
                query = query.filter(UserAchievement.unlocked_at.isnot(None))
            else:
                query = query.filter(UserAchievement.unlocked_at.is_(None))
        
        return query.all()
    
    # ============================================
    # UNLOCK ACHIEVEMENT
    # ============================================
    
    def unlock_achievement(
        self,
        user_id: str,
        achievement_id: str
    ) -> UserAchievement:
        """
        Unlock an achievement for a user
        
        Args:
            user_id: User ID
            achievement_id: Achievement ID
            
        Returns:
            UserAchievement object
            
        Raises:
            HTTPException: If achievement not found or already unlocked
        """
        # Verify achievement exists
        achievement = self.get_achievement_by_id(achievement_id)
        
        # Check if already unlocked
        user_achievement = self.db.query(UserAchievement).filter(
            and_(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id
            )
        ).first()
        
        if user_achievement and user_achievement.unlocked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Achievement already unlocked"
            )
        
        if not user_achievement:
            # Create new user achievement
            user_achievement = UserAchievement(
                id=str(uuid.uuid4()),
                user_id=user_id,
                achievement_id=achievement_id,
                unlocked_at=datetime.utcnow()
            )
            self.db.add(user_achievement)
        else:
            # Unlock existing
            user_achievement.unlocked_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user_achievement)
        
        return user_achievement
    
    # ============================================
    # GET ACHIEVEMENT ANALYTICS
    # ============================================
    
    def get_analytics(self, user_id: str) -> dict:
        """
        Get achievement analytics and statistics
        
        Args:
            user_id: User ID
            
        Returns:
            Analytics dictionary with achievement stats
        """
        # Get all user's achievements
        user_achievements = self.db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id
        ).all()
        
        # Get all achievements
        all_achievements = self.db.query(Achievement).all()
        
        total_achievements = len(all_achievements)
        unlocked_count = sum(1 for ua in user_achievements if ua.unlocked_at is not None)
        locked_count = total_achievements - unlocked_count
        unlock_rate = (unlocked_count / total_achievements * 100) if total_achievements > 0 else 0
        
        # Count by type
        type_counts = {}
        for ua in user_achievements:
            if ua.unlocked_at is not None:
                achievement_type = ua.achievement.achievement_type
                if achievement_type not in type_counts:
                    type_counts[achievement_type] = 0
                type_counts[achievement_type] += 1
        
        # Count by difficulty
        difficulty_counts = {}
        for ua in user_achievements:
            if ua.unlocked_at is not None:
                difficulty = ua.achievement.difficulty
                if difficulty not in difficulty_counts:
                    difficulty_counts[difficulty] = 0
                difficulty_counts[difficulty] += 1
        
        # Get recently unlocked
        recently_unlocked = [
            {
                "achievement_id": ua.achievement_id,
                "title": ua.achievement.title,
                "description": ua.achievement.description,
                "unlocked_at": ua.unlocked_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for ua in user_achievements
            if ua.unlocked_at is not None
        ][:10]
        
        return {
            "total_achievements": total_achievements,
            "unlocked_count": unlocked_count,
            "locked_count": locked_count,
            "unlock_rate": round(unlock_rate, 1),
            "type_counts": type_counts,
            "difficulty_counts": difficulty_counts,
            "recently_unlocked": recently_unlocked
        }
