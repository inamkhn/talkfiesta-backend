import logging
from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.plan import DailyProgress, UserPlan
from app.models.speaking import SpeakingSubmission
from app.models.vocabulary import VocabularySRS
from app.models.writing import WritingSubmission

router = APIRouter(prefix="/progress", tags=["Progress"])
logger = logging.getLogger(__name__)


@router.get("/daily")
def get_daily_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the current day's activity completion status for the dashboard checklist."""
    today = date.today()

    daily = None
    if current_user.active_plan_id and current_user.current_day:
        daily = db.query(DailyProgress).filter(
            DailyProgress.plan_id == current_user.active_plan_id,
            DailyProgress.day_number == current_user.current_day
        ).first()

    # SRS review queue count for today
    vocab_due = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= today
    ).scalar() or 0

    return {
        "day_number": current_user.current_day,
        "plan_id": current_user.active_plan_id,
        "speaking_done": daily.speaking_done if daily else False,
        "vocabulary_done": daily.vocabulary_done if daily else False,
        "writing_done": daily.writing_done if daily else False,
        "is_complete": daily.is_complete if daily else False,
        "xp_earned_today": daily.xp_earned if daily else 0,
        "vocabulary_due_count": vocab_due
    }


@router.get("/analytics")
def get_progress_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns activity summary for the current cycle."""
    # Active plan day rows (self-paced; date is no longer calendar-bound)
    if current_user.active_plan_id:
        plan_rows = (
            db.query(DailyProgress)
            .filter(
                DailyProgress.plan_id == current_user.active_plan_id,
            )
            .order_by(DailyProgress.day_number.asc())
            .all()
        )
    else:
        plan_rows = []

    total_xp_cycle = sum(r.xp_earned for r in plan_rows)
    days_active = sum(1 for r in plan_rows if r.is_complete)

    # Submission counts
    speaking_count = db.query(func.count(SpeakingSubmission.id)).filter(
        SpeakingSubmission.user_id == current_user.id
    ).scalar() or 0

    writing_count = db.query(func.count(WritingSubmission.id)).filter(
        WritingSubmission.user_id == current_user.id
    ).scalar() or 0

    vocab_mastered = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == True
    ).scalar() or 0

    return {
        "current_streak": current_user.current_streak,
        "longest_streak": current_user.longest_streak,
        "total_xp": current_user.total_xp,
        "xp_this_cycle": total_xp_cycle,
        "days_active_this_cycle": days_active,
        "total_speaking_submissions": speaking_count,
        "total_writing_submissions": writing_count,
        "total_vocab_mastered": vocab_mastered,
        "cycle_summary": [
            {
                "day_number": r.day_number,
                "xp": r.xp_earned,
                "complete": r.is_complete
            } for r in plan_rows
        ]
    }
