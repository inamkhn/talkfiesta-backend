import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.schemas.writing import (
    WritingPromptResponse,
    WritingSubmitRequest,
    WritingSubmissionResponse
)
from app.services import writing_service
from app.services.plans_service import get_or_create_active_plan
from app.schemas.common import ModuleContentResponse, ModuleContentStatus

router = APIRouter(prefix="/writing", tags=["Writing"])
logger = logging.getLogger(__name__)

@router.get("/prompts", response_model=ModuleContentResponse[WritingPromptResponse])
def get_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch writing prompts for the current day.
    Lazily creates an active plan if none exists and triggers AI generation
    when personalized content is missing.
    """
    plan = get_or_create_active_plan(db, current_user)
    cycle = plan.cycle_number
    day = current_user.current_day
    user_level = current_user.english_level or "B1"

    prompts = (
        db.query(WritingPrompt)
        .filter(
            WritingPrompt.user_id == current_user.id,
            WritingPrompt.cycle == cycle,
            WritingPrompt.day == day,
        )
        .all()
    )

    if prompts:
        return ModuleContentResponse(
            status=ModuleContentStatus.ready,
            items=prompts,
            message="",
        )

    # No personalized prompts yet — trigger generation (locked per user/cycle/module)
    try:
        from app.core.lock import module_generation_lock
        from app.services.writing_generator import generate_cycle_writing_prompts

        with module_generation_lock(current_user.id, cycle, "writing") as acquired:
            if acquired:
                generate_cycle_writing_prompts.delay(current_user.id, cycle)
                logger.info(
                    "Queued writing generation for user=%s cycle=%s day=%s",
                    current_user.id,
                    cycle,
                    day,
                )
            else:
                logger.info(
                    "Writing generation already queued for user=%s cycle=%s",
                    current_user.id,
                    cycle,
                )
    except Exception as exc:
        logger.warning("Could not queue writing generation: %s", exc)

    return ModuleContentResponse(
        status=ModuleContentStatus.generating,
        items=[],
        message="Personalizing your writing prompts...",
    )

@router.get("/prompts/{prompt_id}", response_model=WritingPromptResponse)
def get_prompt_by_id(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return writing_service.get_prompt_by_id(db, prompt_id)

@router.post("/submissions", response_model=WritingSubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: WritingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits user writing, calls Gemini for instant grading, saves results.
    Writing grading is fast enough to be synchronous (no Celery needed).
    """
    return writing_service.grade_and_save_submission(db, current_user, payload)

@router.patch("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
def revise_submission(
    submission_id: str,
    payload: WritingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User submits a revised version of their writing for re-grading."""
    return writing_service.revise_submission(db, current_user, submission_id, payload)

@router.get("/submissions", response_model=List[WritingSubmissionResponse])
def get_my_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return writing_service.get_user_submissions(db, current_user)

@router.get("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
def get_submission_detail(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return writing_service.get_submission_detail(db, current_user, submission_id)

@router.get("/analytics")
def get_writing_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return writing_service.get_writing_analytics(db, current_user)
