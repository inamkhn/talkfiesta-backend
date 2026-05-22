import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.plan import UserPlan, DailyProgress
from app.schemas.plans import (
    PlanSummaryResponse,
    PlanDetailResponse,
    PlanDayBriefResponse,
    PlanDayResponse,
)

logger = logging.getLogger(__name__)

# 21 days per cycle; 5 program cycles total (105-day curriculum).
DAYS_PER_CYCLE = 21
MAX_PROGRAM_CYCLE_NUMBER = 5


def _plan_status_value(plan: UserPlan) -> str:
    s = plan.status
    return s.value if hasattr(s, "value") else str(s)


def list_plans(db: Session, user: User) -> list[PlanSummaryResponse]:
    plans = (
        db.query(UserPlan)
        .filter(UserPlan.user_id == user.id)
        .order_by(UserPlan.created_at.desc())
        .all()
    )
    if not plans:
        return []

    plan_ids = [p.id for p in plans]
    completed_rows = (
        db.query(DailyProgress.plan_id, func.count(DailyProgress.id))
        .filter(
            DailyProgress.plan_id.in_(plan_ids),
            DailyProgress.is_complete.is_(True),
        )
        .group_by(DailyProgress.plan_id)
        .all()
    )
    completed_by_plan = {pid: int(cnt) for pid, cnt in completed_rows}

    return [
        PlanSummaryResponse(
            id=p.id,
            cycle_number=p.cycle_number,
            status=_plan_status_value(p),
            started_at=p.started_at,
            completed_at=p.completed_at,
            created_at=p.created_at,
            days_completed=completed_by_plan.get(p.id, 0),
            total_days=DAYS_PER_CYCLE,
        )
        for p in plans
    ]


def get_or_create_active_plan(db: Session, user: User) -> UserPlan:
    """
    Return the user's active plan if one exists and is in_progress.
    Otherwise atomically create a new plan, seed 21 DailyProgress rows,
    set user.active_plan_id / current_day, and trigger AI generation.
    """
    # Fast path: user already has an active plan cached on their row
    if user.active_plan_id:
        active = (
            db.query(UserPlan)
            .filter(
                UserPlan.id == user.active_plan_id,
                UserPlan.user_id == user.id,
                UserPlan.status == "in_progress",
            )
            .first()
        )
        if active:
            return active

    # Serialize per-user plan creation to avoid race conditions
    db.query(User).filter(User.id == user.id).with_for_update().one()

    # Recheck after acquiring lock
    active = (
        db.query(UserPlan)
        .filter(
            UserPlan.user_id == user.id,
            UserPlan.status == "in_progress",
        )
        .first()
    )
    if active:
        # Only fix stale cache; never wipe current_day progress
        if user.active_plan_id != active.id:
            user.active_plan_id = active.id
        db.commit()
        return active

    max_cycle = (
        db.query(func.max(UserPlan.cycle_number))
        .filter(UserPlan.user_id == user.id)
        .scalar()
    )
    next_cycle = (max_cycle or 0) + 1
    if next_cycle > MAX_PROGRAM_CYCLE_NUMBER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All five program cycles have already been started.",
        )

    now = datetime.now(timezone.utc)
    plan = UserPlan(
        id=str(uuid.uuid4()),
        user_id=user.id,
        cycle_number=next_cycle,
        status="in_progress",
        started_at=now,
        created_at=now,
    )
    db.add(plan)
    db.flush()

    for day in range(1, DAYS_PER_CYCLE + 1):
        db.add(
            DailyProgress(
                id=str(uuid.uuid4()),
                user_id=user.id,
                plan_id=plan.id,
                day_number=day,
                date=None,
                created_at=now,
            )
        )

    user.active_plan_id = plan.id
    user.current_day = 1

    try:
        db.commit()
        db.refresh(plan)

        # Trigger dynamic generation for the new cycle
        try:
            from app.services.vocabulary_generator import generate_cycle_vocabulary
            from app.services.writing_generator import generate_cycle_writing_prompts
            from app.services.speaking_generator import generate_cycle_speaking_exercises

            generate_cycle_vocabulary.delay(user.id, next_cycle)
            generate_cycle_writing_prompts.delay(user.id, next_cycle)
            generate_cycle_speaking_exercises.delay(user.id, next_cycle)

            logger.info(
                "Triggered AI generation (Vocab, Writing, Speaking) for User %s, Cycle %s",
                user.id,
                next_cycle,
            )
        except Exception as e:
            logger.warning("Could not trigger AI generation: %s", e)

    except IntegrityError:
        db.rollback()
        logger.warning(
            "Plan create integrity error for user %s (likely concurrent active plan)",
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create plan. You may already have an active plan.",
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to create plan for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create plan. Please try again.",
        )

    return plan


def _get_owned_plan(db: Session, user: User, plan_id: str) -> UserPlan:
    plan = (
        db.query(UserPlan)
        .filter(UserPlan.id == plan_id, UserPlan.user_id == user.id)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found.",
        )
    return plan


def update_plan_status(
    db: Session,
    user: User,
    plan_id: str,
    new_status: str,
) -> PlanDetailResponse:
    """
    Transition an in_progress plan to completed or abandoned.
    completed -> sets completed_at; abandoned -> completed_at cleared.
    """
    if new_status not in ("completed", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be 'completed' or 'abandoned'.",
        )

    plan = _get_owned_plan(db, user, plan_id)
    current = _plan_status_value(plan)
    if current != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only an in_progress plan can be closed (current status: {current}).",
        )

    now = datetime.utcnow()
    if new_status == "completed":
        plan.status = "completed"
        plan.completed_at = now
    else:
        plan.status = "abandoned"
        plan.completed_at = None

    try:
        db.commit()
        db.refresh(plan)
    except Exception:
        db.rollback()
        logger.exception("Failed to update plan status for plan %s", plan_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update plan. Please try again.",
        )

    return get_plan(db, user, plan.id)


def get_plan(db: Session, user: User, plan_id: str) -> PlanDetailResponse:
    plan = _get_owned_plan(db, user, plan_id)
    days_rows = (
        db.query(DailyProgress)
        .filter(
            DailyProgress.plan_id == plan.id,
            DailyProgress.user_id == user.id,
        )
        .order_by(DailyProgress.day_number)
        .all()
    )
    if len(days_rows) != DAYS_PER_CYCLE:
        logger.warning(
            "Plan %s has %s day rows (expected %s); data may be partial or legacy.",
            plan.id,
            len(days_rows),
            DAYS_PER_CYCLE,
        )

    days = [
        PlanDayBriefResponse(
            day_number=d.day_number,
            date=d.date,
            is_complete=bool(d.is_complete),
        )
        for d in days_rows
    ]
    return PlanDetailResponse(
        id=plan.id,
        cycle_number=plan.cycle_number,
        status=_plan_status_value(plan),
        started_at=plan.started_at,
        completed_at=plan.completed_at,
        created_at=plan.created_at,
        days=days,
    )


def get_plan_day(
    db: Session,
    user: User,
    plan_id: str,
    day_number: int,
) -> PlanDayResponse:
    if day_number < 1 or day_number > DAYS_PER_CYCLE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"day_number must be between 1 and {DAYS_PER_CYCLE}.",
        )

    _get_owned_plan(db, user, plan_id)

    row = (
        db.query(DailyProgress)
        .filter(
            DailyProgress.plan_id == plan_id,
            DailyProgress.user_id == user.id,
            DailyProgress.day_number == day_number,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Day not found for this plan.",
        )

    return PlanDayResponse.model_validate(row)
