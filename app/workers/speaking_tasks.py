"""
TalkFiesta — Speaking Analysis Celery Task
==========================================
Workflow:
  1. Load SpeakingJob + SpeakingSubmission from DB
  2. Download audio bytes from S3 (or local disk in dev)
  3. Call Gemini via ai_service.analyse_speaking()
  4. Save results back to SpeakingSubmission
  5. Award XP to user if passed
  6. Mark SpeakingJob as done / failed
"""
import logging
from datetime import datetime
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.speaking import SpeakingExercise, SpeakingJob, SpeakingSubmission
from app.models.user import User
from app.services.s3_service import get_audio_bytes
from app.services.ai_service import analyse_speaking

logger = logging.getLogger(__name__)


# ── XP calculator ─────────────────────────────────────────────────────────────

def _calculate_xp(score: int) -> int:
    if score >= 90:
        return 60
    if score >= 75:
        return 45
    if score >= 60:
        return 35
    return 20


# ── Task ──────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="speaking.process_audio",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_audio_submission(self: Task, job_id: str) -> dict:
    """
    Process a speaking audio submission.

    Args:
        job_id: UUID of the SpeakingJob record.

    Returns:
        dict with job_id, status, and result summary.
    """
    db = SessionLocal()

    try:
        # ── 1. Load job ───────────────────────────────────────────────────────
        job = db.query(SpeakingJob).filter(SpeakingJob.id == job_id).first()

        if not job:
            logger.error(f"[Task] Job not found: {job_id}")
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        if job.status != "pending":
            logger.warning(f"[Task] Job {job_id} already {job.status} — skipping")
            return {"job_id": job_id, "status": job.status}

        # ── 2. Mark as processing ─────────────────────────────────────────────
        job.status = "processing"
        job.started_at = datetime.utcnow()
        db.commit()

        # ── 3. Load submission ────────────────────────────────────────────────
        submission = db.query(SpeakingSubmission).filter(
            SpeakingSubmission.id == job.submission_id
        ).first()

        if not submission:
            _fail_job(db, job, "Submission record not found")
            return {"job_id": job_id, "status": "failed"}

        submission.status = "processing"
        db.commit()

        # ── 4. Download audio ─────────────────────────────────────────────────
        logger.info(f"[Task] Downloading audio for submission {submission.id}")
        try:
            audio_bytes = get_audio_bytes(submission.audio_file_path)
        except FileNotFoundError as exc:
            _fail_job(db, job, f"Audio file not found: {exc}", submission)
            return {"job_id": job_id, "status": "failed"}
        except Exception as exc:
            _fail_job(db, job, f"Failed to download audio: {exc}", submission)
            return {"job_id": job_id, "status": "failed"}

        if not audio_bytes or len(audio_bytes) < 500:
            _fail_job(db, job, "Audio file is empty or too short", submission)
            return {"job_id": job_id, "status": "failed"}

        # ── 5. Call Gemini ────────────────────────────────────────────────────
        logger.info(
            f"[Task] Calling Gemini for submission {submission.id} "
            f"({len(audio_bytes)} bytes, level={submission.user_level})"
        )
        try:
            result = analyse_speaking(
                audio_bytes=audio_bytes,
                mime_type=submission.audio_mime_type or "audio/webm",
                exercise_text=submission.exercise_prompt_text or "",
                level=submission.user_level or "B1",
            )
        except SoftTimeLimitExceeded:
            _fail_job(db, job, "Analysis timed out", submission)
            raise
        except Exception as exc:
            logger.error(f"[Task] Gemini failed for {submission.id}: {exc}", exc_info=True)
            # Retry up to max_retries
            raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))

        # ── 6. Save results ───────────────────────────────────────────────────
        submission.transcript = result.get("transcript")
        submission.overall_score = result.get("overall_score")
        submission.fluency_score = result.get("fluency_score")
        submission.pronunciation_score = result.get("pronunciation_score")
        submission.pace_score = result.get("pace_score")
        submission.words_mispronounced = result.get("words_mispronounced", [])
        submission.pronunciation_issues = result.get("pronunciation_issues", [])
        submission.feedback = result.get("feedback")
        submission.improvement_tips = result.get("improvement_tips", [])
        submission.encouragement = result.get("encouragement")
        submission.passed = result.get("passed", False)
        submission.status = "done"
        submission.analysed_at = datetime.utcnow()

        # ── 7. Award XP ───────────────────────────────────────────────────────
        xp = 0
        if submission.passed and submission.overall_score:
            xp = _calculate_xp(submission.overall_score)
            user = db.query(User).filter(User.id == submission.user_id).first()
            if user:
                user.total_xp = (user.total_xp or 0) + xp
                submission.xp_earned = xp
                logger.info(
                    f"[Task] Awarded {xp} XP to user {user.id} "
                    f"(score={submission.overall_score})"
                )

        # ── 8. Mark job done ──────────────────────────────────────────────────
        job.status = "done"
        job.completed_at = datetime.utcnow()
        job.result_summary = {
            "overall_score": submission.overall_score,
            "passed": submission.passed,
            "xp_earned": xp,
        }

        db.commit()

        # ── 9. Day-completion tracking ──────────────────────────────────────────
        if user and user.active_plan_id:
            exercise = (
                db.query(SpeakingExercise)
                .filter(SpeakingExercise.id == submission.exercise_id)
                .first()
            )
            if exercise and exercise.user_id == user.id:
                from app.services.progress_service import mark_activity_complete
                mark_activity_complete(
                    db, user, "speaking", exercise.cycle, exercise.day
                )

        logger.info(
            f"[Task] Job {job_id} completed — "
            f"score={submission.overall_score}, passed={submission.passed}"
        )

        return {
            "job_id": job_id,
            "status": "done",
            "overall_score": submission.overall_score,
            "passed": submission.passed,
            "xp_earned": xp,
        }

    except self.MaxRetriesExceededError:
        logger.error(f"[Task] Job {job_id} failed after {self.max_retries} retries")
        job = db.query(SpeakingJob).filter(SpeakingJob.id == job_id).first()
        if job:
            sub = db.query(SpeakingSubmission).filter(
                SpeakingSubmission.id == job.submission_id
            ).first()
            _fail_job(db, job, "Max retries exceeded", sub)
        return {"job_id": job_id, "status": "failed"}

    except SoftTimeLimitExceeded:
        # Already handled above — just ensure DB is clean
        db.rollback()
        return {"job_id": job_id, "status": "failed", "error": "timeout"}

    except Exception as exc:
        db.rollback()
        logger.exception(f"[Task] Unexpected error for job {job_id}: {exc}")
        job = db.query(SpeakingJob).filter(SpeakingJob.id == job_id).first()
        if job:
            sub = db.query(SpeakingSubmission).filter(
                SpeakingSubmission.id == job.submission_id
            ).first()
            _fail_job(db, job, str(exc)[:500], sub)
        return {"job_id": job_id, "status": "failed"}

    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fail_job(
    db,
    job: SpeakingJob,
    error_message: str,
    submission: SpeakingSubmission | None = None,
) -> None:
    """Mark job and optionally submission as failed and commit."""
    try:
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.utcnow()

        if submission:
            submission.status = "failed"

        db.commit()
        logger.error(f"[Task] Job {job.id} failed: {error_message}")
    except Exception:
        db.rollback()
        logger.exception(f"[Task] Could not persist failure for job {job.id}")
