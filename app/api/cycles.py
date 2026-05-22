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
from app.models.gamification import CycleCompletion
from app.models.plan import UserPlan, DailyProgress
from app.schemas.plans import PlanDetailResponse
from app.services.plans_service import get_or_create_active_plan

router = APIRouter(prefix="/cycles", tags=["Cycles"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CycleCompleteRequest(BaseModel):
    cycle_number: int
    total_xp_earned: int
    average_score: Optional[float] = None
    days_taken: Optional[int] = None

class CycleCompletionResponse(BaseModel):
    id: str
    cycle_number: int
    completed_at: datetime
    total_xp_earned: int
    average_score: Optional[float] = None
    days_taken: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/continue", response_model=PlanDetailResponse)
def continue_cycle(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicitly start or continue the next learning cycle.
    Only callable when the user has no active in-progress plan.
    """
    # Defensive: query DB directly in case active_plan_id cache is stale
    active = (
        db.query(UserPlan)
        .filter(
            UserPlan.user_id == current_user.id,
            UserPlan.status == "in_progress",
        )
        .first()
    )
    if active or current_user.active_plan_id:
        raise HTTPException(
            status_code=409,
            detail="You already have an active cycle. Complete it before starting a new one.",
        )
    plan = get_or_create_active_plan(db, current_user)
    from app.services.plans_service import get_plan
    return get_plan(db, current_user, plan.id)


@router.get("/completions", response_model=List[CycleCompletionResponse])
def get_cycle_completions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns all cycles the user has completed in chronological order."""
    return db.query(CycleCompletion).filter(
        CycleCompletion.user_id == current_user.id
    ).order_by(CycleCompletion.cycle_number.asc()).all()


@router.post("/complete", response_model=CycleCompletionResponse)
def complete_cycle(
    payload: CycleCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Called when the user finishes the last day of a cycle.
    Records the completion, marks the UserPlan complete, awards XP, and
    triggers the Celery vocab generation for the next cycle.
    """
    # Guard: prevent duplicate completions
    existing = db.query(CycleCompletion).filter(
        CycleCompletion.user_id == current_user.id,
        CycleCompletion.cycle_number == payload.cycle_number
    ).first()
    if existing:
        return existing

    completion = CycleCompletion(
        user_id=current_user.id,
        cycle_number=payload.cycle_number,
        total_xp_earned=payload.total_xp_earned,
        average_score=payload.average_score,
        days_taken=payload.days_taken
    )
    db.add(completion)

    # Mark the corresponding UserPlan as completed
    plan = db.query(UserPlan).filter(
        UserPlan.user_id == current_user.id,
        UserPlan.cycle_number == payload.cycle_number,
        UserPlan.status == "in_progress"
    ).first()
    if plan:
        plan.status = "completed"
        plan.completed_at = datetime.utcnow()

    # Award cumulative XP bonus to user account
    current_user.total_xp = (current_user.total_xp or 0) + payload.total_xp_earned

    db.commit()
    db.refresh(completion)

    # 🔥 Trigger Gemini AI word generation for the next cycle in background
    next_cycle = payload.cycle_number + 1
    if next_cycle <= 5:
        try:
            from app.services.vocabulary_generator import generate_cycle_vocabulary
            generate_cycle_vocabulary.delay(current_user.id, next_cycle)
            logger.info(f"Triggered vocabulary generation for User {current_user.id}, Cycle {next_cycle}")
        except Exception as e:
            logger.warning(f"Could not trigger next cycle vocab generation: {e}")

    return completion


@router.get("/analytics")
def get_cycle_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    completions = db.query(CycleCompletion).filter(
        CycleCompletion.user_id == current_user.id
    ).all()

    if not completions:
        return {"cycles_completed": 0, "total_xp_from_cycles": 0}

    return {
        "cycles_completed": len(completions),
        "total_xp_from_cycles": sum(c.total_xp_earned for c in completions),
        "average_score_across_cycles": round(
            sum(c.average_score for c in completions if c.average_score) / len(completions), 1
        ) if any(c.average_score for c in completions) else None,
        "cycle_history": [
            {
                "cycle": c.cycle_number,
                "completed_at": c.completed_at.isoformat(),
                "xp": c.total_xp_earned,
                "avg_score": c.average_score,
                "days_taken": c.days_taken
            } for c in completions
        ]
    }
