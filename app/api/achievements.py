import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.gamification import Achievement, UserAchievement

router = APIRouter(prefix="/achievements", tags=["Achievements"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AchievementResponse(BaseModel):
    id: str
    key: str
    title: str
    description: str
    icon: Optional[str] = None
    category: Optional[str] = None
    requirement_type: Optional[str] = None
    requirement_value: int
    xp_reward: int
    rarity: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserAchievementResponse(BaseModel):
    id: str
    achievement_id: str
    unlocked_at: datetime
    progress: int
    achievement: AchievementResponse
    model_config = ConfigDict(from_attributes=True)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AchievementResponse])
def get_all_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the full achievement catalog."""
    return db.query(Achievement).order_by(Achievement.category, Achievement.requirement_value).all()


@router.get("/user", response_model=List[UserAchievementResponse])
def get_user_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns all achievements the user has unlocked."""
    return db.query(UserAchievement).filter(
        UserAchievement.user_id == current_user.id
    ).order_by(UserAchievement.unlocked_at.desc()).all()


@router.get("/{achievement_id}", response_model=AchievementResponse)
def get_achievement_detail(
    achievement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ach = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not ach:
        raise HTTPException(status_code=404, detail="Achievement not found")
    return ach


@router.post("/{achievement_id}/unlock")
def unlock_achievement(
    achievement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlocks an achievement for a user (called server-side after a trigger event).
    Guards against double-unlocking.
    """
    ach = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not ach:
        raise HTTPException(status_code=404, detail="Achievement not found")

    # Idempotency: check if already unlocked
    existing = db.query(UserAchievement).filter(
        UserAchievement.user_id == current_user.id,
        UserAchievement.achievement_id == achievement_id
    ).first()

    if existing:
        return {"message": "Achievement already unlocked.", "xp_awarded": 0}

    # Unlock it
    user_ach = UserAchievement(
        user_id=current_user.id,
        achievement_id=achievement_id,
        progress=ach.requirement_value
    )
    db.add(user_ach)

    # Award XP to user
    current_user.total_xp = (current_user.total_xp or 0) + ach.xp_reward
    db.commit()

    logger.info(f"User {current_user.id} unlocked achievement: {ach.title} (+{ach.xp_reward} XP)")
    return {
        "message": f"Achievement '{ach.title}' unlocked!",
        "xp_awarded": ach.xp_reward
    }


@router.get("/analytics/summary")
def get_achievement_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_achievements = db.query(func.count(Achievement.id)).scalar() or 0
    user_unlocked = db.query(func.count(UserAchievement.id)).filter(
        UserAchievement.user_id == current_user.id
    ).scalar() or 0

    xp_from_achievements = db.query(func.sum(Achievement.xp_reward)).join(
        UserAchievement, UserAchievement.achievement_id == Achievement.id
    ).filter(
        UserAchievement.user_id == current_user.id
    ).scalar() or 0

    return {
        "total_available": total_achievements,
        "unlocked": user_unlocked,
        "completion_percent": round((user_unlocked / total_achievements) * 100, 1) if total_achievements else 0.0,
        "xp_earned_from_achievements": xp_from_achievements
    }
