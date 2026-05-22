"""
TalkFiesta — Progress Service
==============================
Activity-based day progression helpers.
"""
import logging
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.plan import UserPlan, DailyProgress

logger = logging.getLogger(__name__)

DAYS_PER_CYCLE = 21


def advance_day_if_complete(db: Session, user: User) -> dict:
    """
    Check whether the user's current day is fully complete (all 3 activities).
    If yes:
      - day < 21  → increment user.current_day
      - day == 21 → mark plan completed, clear user.active_plan_id / current_day
    Returns a dict describing the outcome so callers can react.
    """
    plan_id = user.active_plan_id
    current_day = user.current_day

    if not plan_id or not current_day:
        return {"advanced": False, "reason": "no_active_plan"}

    day_row = (
        db.query(DailyProgress)
        .filter(
            DailyProgress.plan_id == plan_id,
            DailyProgress.day_number == current_day,
        )
        .first()
    )

    if not day_row:
        logger.warning(
            "DailyProgress missing for plan=%s day=%s user=%s",
            plan_id,
            current_day,
            user.id,
        )
        return {"advanced": False, "reason": "missing_daily_progress"}

    if not (day_row.speaking_done and day_row.vocabulary_done and day_row.writing_done):
        return {"advanced": False, "reason": "incomplete_day"}

    day_row.is_complete = True

    if current_day < DAYS_PER_CYCLE:
        user.current_day = current_day + 1
        db.commit()
        logger.info(
            "User %s advanced from day %s to day %s (plan=%s)",
            user.id,
            current_day,
            user.current_day,
            plan_id,
        )
        return {
            "advanced": True,
            "cycle_complete": False,
            "previous_day": current_day,
            "current_day": user.current_day,
        }

    # Day 21 complete → cycle finished
    plan = db.query(UserPlan).filter(UserPlan.id == plan_id).first()
    if plan:
        plan.status = "completed"
        plan.completed_at = day_row.created_at  # reuse as rough timestamp

    user.active_plan_id = None
    user.current_day = 1
    db.commit()

    logger.info("User %s completed cycle %s", user.id, plan.cycle_number if plan else "?")
    return {
        "advanced": True,
        "cycle_complete": True,
        "previous_day": current_day,
        "current_day": 1,
    }
