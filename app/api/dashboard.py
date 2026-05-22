import logging
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.plan import DailyProgress
from app.models.speaking import SpeakingSubmission
from app.models.vocabulary import VocabularySRS
from app.models.writing import WritingSubmission

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)


@router.get("")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Main dashboard — aggregates all KPIs into a single fast response."""
    today = date.today()

    daily = None
    if current_user.active_plan_id and current_user.current_day:
        daily = db.query(DailyProgress).filter(
            DailyProgress.plan_id == current_user.active_plan_id,
            DailyProgress.day_number == current_user.current_day
        ).first()

    vocab_due = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= today
    ).scalar() or 0

    vocab_mastered = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == True
    ).scalar() or 0

    return {
        "user": {
            "full_name": current_user.full_name,
            "english_level": current_user.english_level,
            "total_xp": current_user.total_xp,
            "current_streak": current_user.current_streak,
            "active_plan_id": current_user.active_plan_id,
            "current_day": current_user.current_day,
        },
        "today": {
            "day_number": current_user.current_day,
            "speaking_done": daily.speaking_done if daily else False,
            "vocabulary_done": daily.vocabulary_done if daily else False,
            "writing_done": daily.writing_done if daily else False,
            "xp_earned": daily.xp_earned if daily else 0,
        },
        "vocabulary": {
            "due_today": vocab_due,
            "mastered": vocab_mastered
        }
    }


@router.get("/speaking-preview")
def get_speaking_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Last 3 speaking submissions for a preview card."""
    recent = db.query(SpeakingSubmission).filter(
        SpeakingSubmission.user_id == current_user.id,
        SpeakingSubmission.status == "done"
    ).order_by(SpeakingSubmission.created_at.desc()).limit(3).all()

    return [
        {
            "id": s.id,
            "created_at": s.created_at.isoformat(),
            "overall_score": s.overall_score,
            "passed": s.passed,
            "xp_earned": s.xp_earned
        } for s in recent
    ]


@router.get("/vocabulary-preview")
def get_vocabulary_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Preview: mastered count + next 5 words due for review."""
    today = date.today()

    mastered_count = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == True
    ).scalar() or 0

    due_next = db.query(VocabularySRS).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= today
    ).limit(5).all()

    return {
        "mastered_total": mastered_count,
        "due_today_preview": [
            {
                "word_id": srs.word_id,
                "mastery_level": srs.mastery_level,
                "last_reviewed": srs.last_reviewed.isoformat() if srs.last_reviewed else None
            } for srs in due_next
        ]
    }


@router.get("/writing-preview")
def get_writing_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Last 3 writing submissions for a preview card."""
    recent = db.query(WritingSubmission).filter(
        WritingSubmission.user_id == current_user.id
    ).order_by(WritingSubmission.created_at.desc()).limit(3).all()

    avg_score = db.query(func.avg(WritingSubmission.overall_score)).filter(
        WritingSubmission.user_id == current_user.id,
        WritingSubmission.overall_score.isnot(None)
    ).scalar()

    return {
        "average_score": round(float(avg_score), 1) if avg_score else None,
        "recent_submissions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "overall_score": s.overall_score,
                "passed": s.passed,
                "word_count": s.word_count
            } for s in recent
        ]
    }
