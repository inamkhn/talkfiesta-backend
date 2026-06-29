"""
TalkFiesta — Progress Service
==============================
Activity-based day progression helpers.

Centralizes the day-completion logic that was previously duplicated across
vocabulary, speaking, and writing modules. All three modules now call
`mark_activity_complete()` instead of managing DailyProgress directly.
"""
import logging
from typing import Literal

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


def mark_activity_complete(
    db: Session,
    user: User,
    activity: Literal["speaking", "vocabulary", "writing"],
    cycle: int,
    day: int,
) -> dict:
    """
    Centralized activity completion tracker.
    Called by speaking, vocabulary, and writing modules when an activity is done.

    Responsibilities:
      1. Validate the activity belongs to the user's current day/cycle
      2. Set the corresponding done flag on DailyProgress (idempotent)
      3. Increment activities_completed counter
      4. Check if all 3 activities are done and advance the day if so

    Callers should only call this after validating the activity is actually
    complete (e.g., vocabulary: all 10 words practiced, speaking: analysis done).
    The cycle/day parameters are provided by the caller to avoid redundant
    DB lookups for the exercise/prompt/word.

    Args:
        db: Database session.
        user: The current user.
        activity: Which module completed — "speaking", "vocabulary", or "writing".
        cycle: The cycle number of the completed exercise/prompt/word.
        day: The day number of the completed exercise/prompt/word.

    Returns:
        dict with keys:
          - activity_done (bool): Whether the flag was set (False if already done)
          - day_advanced (bool): Whether the day was advanced
          - cycle_complete (bool): Whether the full cycle was completed
    """
    result = {
        "activity_done": False,
        "day_advanced": False,
        "cycle_complete": False,
    }

    # Guard: user must have an active plan and be on a valid day
    if not user.active_plan_id or not user.current_day:
        return result

    # Guard: activity must belong to the user's current day and cycle
    if day != user.current_day:
        return result

    # Fetch the plan to verify cycle matches
    plan = db.query(UserPlan).filter(
        UserPlan.id == user.active_plan_id
    ).first()
    if not plan or plan.cycle_number != cycle:
        return result

    # Fetch DailyProgress for the current day
    day_prog = (
        db.query(DailyProgress)
        .filter(
            DailyProgress.plan_id == user.active_plan_id,
            DailyProgress.day_number == user.current_day,
        )
        .first()
    )
    if not day_prog:
        logger.warning(
            "DailyProgress missing for plan=%s day=%s user=%s (mark_activity_complete)",
            user.active_plan_id,
            user.current_day,
            user.id,
        )
        return result

    # Map activity name to the corresponding column
    field_map = {
        "speaking": "speaking_done",
        "vocabulary": "vocabulary_done",
        "writing": "writing_done",
    }
    field_name = field_map[activity]

    # Idempotent: if already marked done, skip
    if getattr(day_prog, field_name):
        return result

    # Mark the activity as done
    setattr(day_prog, field_name, True)
    day_prog.activities_completed = (day_prog.activities_completed or 0) + 1
    db.commit()

    result["activity_done"] = True
    logger.info(
        "User %s marked %s complete for day %s (plan=%s, cycle=%s)",
        user.id,
        activity,
        user.current_day,
        user.active_plan_id,
        cycle,
    )

    # Check if all 3 activities are done → advance day
    advance_result = advance_day_if_complete(db, user)
    if advance_result.get("advanced"):
        result["day_advanced"] = True
        result["cycle_complete"] = advance_result.get("cycle_complete", False)

    return result
