import logging
import asyncio
import json
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from app.core.rate_limiter import limiter

from app.db.session import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.speaking import SpeakingExercise, SpeakingSubmission, SpeakingJob
from app.schemas.speaking import (
    SpeakingExerciseResponse,
    SpeakingJobResponse,
    SpeakingSubmissionResponse,
    PresignedUrlResponse,
    SpeakingSubmissionCreate,
)
from app.services.s3_service import upload_audio, generate_presigned_upload_url, get_audio_bytes
from app.config import settings
from app.services.plans_service import get_or_create_active_plan
from app.schemas.common import ModuleContentResponse, ModuleContentStatus

router = APIRouter(prefix="/speaking", tags=["Speaking"])
logger = logging.getLogger(__name__)


@router.get("/exercises", response_model=ModuleContentResponse[SpeakingExerciseResponse])
def get_exercises(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get speaking exercises for the current day.
    Lazily creates an active plan if none exists and triggers AI generation
    when personalized content is missing.
    """
    plan = get_or_create_active_plan(db, current_user)
    cycle = plan.cycle_number
    day = current_user.current_day

    exercises = (
        db.query(SpeakingExercise)
        .filter(
            SpeakingExercise.user_id == current_user.id,
            SpeakingExercise.cycle == cycle,
            SpeakingExercise.day == day,
        )
        .all()
    )

    if exercises:
        return ModuleContentResponse(
            status=ModuleContentStatus.ready,
            items=exercises,
            message="",
        )

    # No personalized exercises yet — trigger generation (locked per user/cycle/module)
    try:
        from app.core.lock import module_generation_lock
        from app.services.speaking_generator import generate_cycle_speaking_exercises

        with module_generation_lock(current_user.id, cycle, "speaking") as acquired:
            if acquired:
                generate_cycle_speaking_exercises.delay(current_user.id, cycle)
                logger.info(
                    "Queued speaking generation for user=%s cycle=%s day=%s",
                    current_user.id,
                    cycle,
                    day,
                )
            else:
                logger.info(
                    "Speaking generation already queued for user=%s cycle=%s",
                    current_user.id,
                    cycle,
                )
    except Exception as exc:
        logger.warning("Could not queue speaking generation: %s", exc)

    return ModuleContentResponse(
        status=ModuleContentStatus.generating,
        items=[],
        message="Personalizing your speaking exercises...",
    )


@router.get("/exercises/{exercise_id}", response_model=SpeakingExerciseResponse)
def get_exercise_by_id(
    exercise_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    exercise = db.query(SpeakingExercise).filter(SpeakingExercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.get("/upload-url", response_model=PresignedUrlResponse)
@limiter.limit("10/minute")
def get_upload_url(
    request: Request,
    content_type: str = "audio/webm",
    current_user: User = Depends(get_current_user)
):
    """Generate a presigned URL for direct S3 audio upload from the browser."""
    import uuid
    filename = f"{current_user.id}/{uuid.uuid4().hex}.webm"
    return generate_presigned_upload_url(filename, content_type)

@router.post("/submissions", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def create_submission(
    request: Request,
    payload: SpeakingSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accepts S3 file key after direct frontend upload and triggers Celery evaluation."""
    exercise = db.query(SpeakingExercise).filter(SpeakingExercise.id == payload.exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    from app.config import settings
    s3_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{payload.s3_file_key}"
    if not settings.AWS_S3_BUCKET:
        s3_url = payload.s3_file_key
        
    submission = SpeakingSubmission(
        user_id=current_user.id,
        exercise_id=payload.exercise_id,
        audio_file_path=s3_url,
        audio_mime_type=payload.content_type,
        audio_size_bytes=payload.size_bytes,
        exercise_prompt_text=exercise.prompt_text,
        user_level=current_user.english_level or "B1",
        status="pending"
    )
    db.add(submission)
    db.flush()
    
    job = SpeakingJob(
        user_id=current_user.id,
        submission_id=submission.id,
        status="pending"
    )
    db.add(job)
    db.commit()
    
    # Trigger Async Celery Task
    try:
        from app.workers.speaking_tasks import process_audio_submission
        process_audio_submission.delay(str(job.id))
        logger.info(f"Celery task queued for submission {submission.id}")
    except Exception:
        # Celery not running in dev — log and continue. Job stays "pending".
        logger.warning(
            f"Celery unavailable — submission {submission.id} queued but not processed. "
            "Start a Celery worker to process it."
        )
    
    return {"message": "Audio accepted for processing in background.", "job_id": job.id}


@router.get("/jobs/{job_id}/stream")
def stream_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Server-Sent Events (SSE) endpoint that streams the job status to the frontend without polling."""
    async def event_generator():
        # Use a new DB session for the async generator
        db = SessionLocal()
        try:
            job = db.query(SpeakingJob).filter(
                SpeakingJob.id == job_id, 
                SpeakingJob.user_id == current_user.id
            ).first()
            
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\\n\\n"
                return

            while True:
                db.refresh(job)
                status_data = {
                    "id": job.id,
                    "status": job.status,
                    "submission_id": job.submission_id
                }
                
                if job.status == "failed":
                    status_data["error_message"] = job.error_message
                    
                yield f"data: {json.dumps(status_data)}\\n\\n"
                
                if job.status in ["done", "failed"]:
                    break
                    
                await asyncio.sleep(1) # Check DB every 1 second
        finally:
            db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/submissions", response_model=List[SpeakingSubmissionResponse])
def get_user_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(SpeakingSubmission).filter(
        SpeakingSubmission.user_id == current_user.id
    ).order_by(SpeakingSubmission.created_at.desc()).limit(50).all()


@router.get("/submissions/{submission_id}", response_model=SpeakingSubmissionResponse)
def get_submission_detail(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = db.query(SpeakingSubmission).filter(
        SpeakingSubmission.id == submission_id,
        SpeakingSubmission.user_id == current_user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.get("/jobs/{job_id}", response_model=SpeakingJobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    REST poll endpoint — alternative to SSE streaming.
    Frontend polls this every 2-3 seconds until status is 'done' or 'failed'.
    Returns full submission result when status == 'done'.
    """
    job = db.query(SpeakingJob).filter(
        SpeakingJob.id == job_id,
        SpeakingJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/upload-local", include_in_schema=False)
async def upload_local(
    file: UploadFile = File(...),
    key: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """
    DEV ONLY — receives audio uploaded by the browser when S3 is not configured.
    Saves the file to local AUDIO_STORAGE_DIR using the key from the presigned URL.
    In production this endpoint is never called — the browser uploads directly to S3.
    """
    if settings.AWS_S3_BUCKET and settings.AWS_ACCESS_KEY_ID:
        raise HTTPException(
            status_code=400,
            detail="Local upload is disabled when S3 is configured.",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Empty file received.")

    # Save to local storage using the key as the relative path
    dest = Path(settings.AUDIO_STORAGE_DIR) / key
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f:
        f.write(audio_bytes)

    logger.info(f"[DEV] Local audio saved: {dest} ({len(audio_bytes)} bytes)")
    return {"message": "File uploaded successfully.", "key": key}
