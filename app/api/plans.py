import logging
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.plans import (
    PlanSummaryResponse,
    PlanDetailResponse,
    PlanDayResponse,
    PlanStatusUpdateRequest,
)
from app.services import plans_service

router = APIRouter(prefix="/plans", tags=["Plans"])
logger = logging.getLogger(__name__)


# ── Step 1: List all plans for the current user ─────────────────────────────
@router.get("", response_model=list[PlanSummaryResponse])
def list_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every learning cycle (plan) owned by the user, newest first."""
    return plans_service.list_plans(db, current_user)


# ── Step 2: Create / start a new plan ───────────────────────────────────────
@router.post("", response_model=PlanDetailResponse, status_code=201)
def create_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new 21-day cycle. Triggers AI content generation."""
    plan = plans_service.get_or_create_active_plan(db, current_user)
    return plans_service.get_plan(db, current_user, plan.id)


# ── Step 3: Single plan with per-day completion summary ─────────────────────
@router.get("/{plan_id}", response_model=PlanDetailResponse)
def get_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Plan metadata plus brief list of all 21 days."""
    return plans_service.get_plan(db, current_user, plan_id)


# ── Step 4: Close an active plan (complete or abandon) ───────────────────────
@router.patch("/{plan_id}", response_model=PlanDetailResponse)
def patch_plan(
    plan_id: str,
    body: PlanStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set an **in_progress** plan to **completed** or **abandoned**.
    """
    return plans_service.update_plan_status(db, current_user, plan_id, body.status)


# ── Step 5: One day's full progress record ──────────────────────────────────
@router.get("/{plan_id}/days/{day_number}", response_model=PlanDayResponse)
def get_plan_day(
    plan_id: str,
    day_number: int = Path(..., ge=1, le=plans_service.DAYS_PER_CYCLE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full DailyProgress for a single day (1–21) within the plan."""
    return plans_service.get_plan_day(db, current_user, plan_id, day_number)
