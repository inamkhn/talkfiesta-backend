import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.plan import UserPlan, DailyProgress
from app.models.gamification import UserAchievement, CycleCompletion
from app.schemas.profile import ProfileUpdateRequest, ProfileStatsResponse

logger = logging.getLogger(__name__)


def get_profile_stats(db: Session, user: User) -> ProfileStatsResponse:
    achievements_unlocked = (
        db.query(func.count(UserAchievement.id))
        .filter(UserAchievement.user_id == user.id)
        .scalar()
        or 0
    )
    days_completed = (
        db.query(func.count(DailyProgress.id))
        .filter(
            DailyProgress.user_id == user.id,
            DailyProgress.is_complete.is_(True),
        )
        .scalar()
        or 0
    )
    cycles_completed = (
        db.query(func.count(CycleCompletion.id))
        .filter(CycleCompletion.user_id == user.id)
        .scalar()
        or 0
    )

    active_plan = (
        db.query(UserPlan)
        .filter(
            UserPlan.user_id == user.id,
            UserPlan.status == "in_progress",
        )
        .first()
    )

    return ProfileStatsResponse(
        total_xp=user.total_xp or 0,
        current_streak=user.current_streak or 0,
        longest_streak=user.longest_streak or 0,
        achievements_unlocked=int(achievements_unlocked),
        days_completed=int(days_completed),
        cycles_completed=int(cycles_completed),
        active_plan_cycle_number=active_plan.cycle_number if active_plan else None,
    )


def update_profile(db: Session, user: User, data: ProfileUpdateRequest) -> User:
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return user

    for key, value in payload.items():
        setattr(user, key, value)

    user.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("Failed to update profile for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile. Please try again.",
        )

    return user
