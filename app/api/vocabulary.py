import logging
from datetime import date, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.vocabulary import VocabularyWord, VocabularyProgress, VocabularySRS
from app.schemas.vocabulary import (
    VocabularyWordResponse,
    VocabularyPracticeSubmit,
    VocabularyReviewSubmit,
    VocabularySRSResponse,
    VocabularyProgressStats
)
from app.services.srs_engine import calculate_next_review
from app.services.plans_service import get_or_create_active_plan
from app.schemas.common import ModuleContentResponse, ModuleContentStatus

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary & Spaced Repetition"])
logger = logging.getLogger(__name__)

# --- BROWSE & LEARN ---

@router.get("/words", response_model=List[VocabularyWordResponse])
def get_words(
    cycle: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch words dynamically generated for this user's cycle."""
    words = db.query(VocabularyWord).filter(
        VocabularyWord.user_id == current_user.id,
        VocabularyWord.cycle == cycle
    ).order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc()).all()
    
    # Fallback to globally seeded words if custom ones haven't generated yet
    if not words:
        user_level = current_user.english_level or "B1"
        words = db.query(VocabularyWord).filter(
            VocabularyWord.user_id.is_(None),
            VocabularyWord.cycle == cycle,
            VocabularyWord.difficulty == user_level
        ).order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc()).all()
        
        # Second fallback if no specific global words exist for this level
        if not words:
            words = db.query(VocabularyWord).filter(
                VocabularyWord.user_id.is_(None),
                VocabularyWord.cycle == cycle
            ).order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc()).all()
            
    return words

@router.get("/words/{word_id}", response_model=VocabularyWordResponse)
def get_word_by_id(
    word_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    word = db.query(VocabularyWord).filter(VocabularyWord.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return word

# --- PRACTICE (NEW LEARNING) ---

@router.get("/practice", response_model=ModuleContentResponse[VocabularyWordResponse])
def get_todays_new_words(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the specific 10 new words assigned to the user's current day.
    Lazily creates an active plan if none exists and triggers AI generation
    when personalized content is missing.
    """
    plan = get_or_create_active_plan(db, current_user)
    cycle = plan.cycle_number
    day = current_user.current_day

    words = (
        db.query(VocabularyWord)
        .filter(
            VocabularyWord.user_id == current_user.id,
            VocabularyWord.cycle == cycle,
            VocabularyWord.day == day,
        )
        .order_by(VocabularyWord.position_in_day.asc())
        .all()
    )

    if words:
        return ModuleContentResponse(
            status=ModuleContentStatus.ready,
            items=words,
            message="",
        )

    # No personalized words yet — trigger generation (locked per user/cycle/module)
    try:
        from app.core.lock import module_generation_lock
        from app.services.vocabulary_generator import generate_cycle_vocabulary

        with module_generation_lock(current_user.id, cycle, "vocabulary") as acquired:
            if acquired:
                generate_cycle_vocabulary.delay(current_user.id, cycle)
                logger.info(
                    "Queued vocab generation for user=%s cycle=%s day=%s",
                    current_user.id,
                    cycle,
                    day,
                )
            else:
                logger.info(
                    "Vocab generation already queued for user=%s cycle=%s",
                    current_user.id,
                    cycle,
                )
    except Exception as exc:
        logger.warning("Could not queue vocab generation: %s", exc)

    return ModuleContentResponse(
        status=ModuleContentStatus.generating,
        items=[],
        message="Personalizing your vocabulary words...",
    )

@router.post("/practice")
def submit_practice(
    payload: VocabularyPracticeSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a NEW flashcard as learned, dropping it into the SRS pipeline."""
    word = db.query(VocabularyWord).filter(VocabularyWord.id == payload.word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
        
    # Update General Progress
    progress = db.query(VocabularyProgress).filter(
        VocabularyProgress.user_id == current_user.id,
        VocabularyProgress.word_id == payload.word_id
    ).first()
    
    if not progress:
        progress = VocabularyProgress(
            user_id=current_user.id,
            word_id=payload.word_id,
            times_practiced=1,
            last_practiced=date.today()
        )
        db.add(progress)
    else:
        progress.times_practiced += 1
        progress.last_practiced = date.today()
        
    # Initialize SRS Tracker if it doesn't exist
    srs = db.query(VocabularySRS).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.word_id == payload.word_id
    ).first()
    
    if not srs:
        from datetime import timedelta
        srs = VocabularySRS(
            user_id=current_user.id,
            word_id=payload.word_id,
            next_review_date=date.today() + timedelta(days=1), # Review tomorrow
            last_reviewed=date.today()
        )
        db.add(srs)
        
    db.commit()

    # --- Day-completion tracking ---
    if (
        word.user_id == current_user.id
        and word.day == current_user.current_day
        and current_user.active_plan_id
    ):
        total_day_words = (
            db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id == current_user.id,
                VocabularyWord.cycle == word.cycle,
                VocabularyWord.day == current_user.current_day,
            )
            .count()
        )
        practiced_day_words = (
            db.query(VocabularyProgress)
            .join(VocabularyWord)
            .filter(
                VocabularyProgress.user_id == current_user.id,
                VocabularyWord.user_id == current_user.id,
                VocabularyWord.cycle == word.cycle,
                VocabularyWord.day == current_user.current_day,
            )
            .count()
        )
        if total_day_words > 0 and practiced_day_words >= total_day_words:
            from app.models.plan import DailyProgress
            day_prog = (
                db.query(DailyProgress)
                .filter(
                    DailyProgress.plan_id == current_user.active_plan_id,
                    DailyProgress.day_number == current_user.current_day,
                )
                .first()
            )
            if day_prog and not day_prog.vocabulary_done:
                day_prog.vocabulary_done = True
                day_prog.activities_completed = (
                    day_prog.activities_completed or 0
                ) + 1
                db.commit()
                from app.services.progress_service import advance_day_if_complete
                advance_day_if_complete(db, current_user)

    return {"message": "Word saved. Scheduled for first SRS review tomorrow."}

# --- REVIEW (SPACED REPETITION) ---

@router.get("/review", response_model=List[VocabularySRSResponse])
def get_due_srs_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch flashcards mathematically due for review TODAY, capped at 50 to prevent overload."""
    due_reviews = db.query(VocabularySRS).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= date.today()
    ).order_by(VocabularySRS.next_review_date.asc()).limit(50).all()
    
    return due_reviews

@router.post("/review")
def submit_srs_review(
    payload: VocabularyReviewSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User grades their memory 0-5. SM-2 Engine adjusts intervals mathematically."""
    if payload.grade < 0 or payload.grade > 5:
        raise HTTPException(status_code=400, detail="Grade must be between 0 and 5")
        
    srs = db.query(VocabularySRS).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.word_id == payload.word_id
    ).first()
    
    if not srs:
        raise HTTPException(status_code=404, detail="Word not in SRS tracking yet. Practice it first.")
        
    if srs.is_mastered:
        return {"message": "Word already mastered. Skipping update."}
        
    # Plug into SuperMemo-2 mathematical bounder
    new_ef, new_interval, new_reps, next_date, is_mastered = calculate_next_review(
        ease_factor=srs.ease_factor,
        interval_days=srs.interval_days,
        repetitions=srs.repetitions,
        grade=payload.grade
    )
    
    srs.ease_factor = new_ef
    srs.interval_days = new_interval
    srs.repetitions = new_reps
    srs.next_review_date = next_date
    srs.last_reviewed = date.today()
    srs.review_count += 1
    
    if is_mastered:
        srs.is_mastered = True
        srs.mastered_at = datetime.utcnow()
        srs.mastery_level = 5
        
        # Keep progress synced
        progress = db.query(VocabularyProgress).filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.word_id == srs.word_id
        ).first()
        if progress:
            progress.mastery_level = 5
            
    db.commit()
    return {
        "message": "Review recorded.",
        "grade": payload.grade,
        "next_review_date": next_date,
        "is_mastered": is_mastered
    }

@router.get("/review/stats")
def get_srs_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Breakdown of flashcard intervals."""
    total_learning = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False
    ).scalar()
    
    total_mastered = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == True
    ).scalar()
    
    due_today = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= date.today()
    ).scalar()
    
    return {
        "words_learning": total_learning,
        "words_mastered": total_mastered,
        "due_for_review_today": due_today
    }

# --- ANALYTICS ---

@router.get("/progress", response_model=VocabularyProgressStats)
def get_vocabulary_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_encountered = db.query(func.count(VocabularyProgress.id)).filter(VocabularyProgress.user_id == current_user.id).scalar() or 0
    words_mastered = db.query(func.count(VocabularySRS.id)).filter(VocabularySRS.user_id == current_user.id, VocabularySRS.is_mastered == True).scalar() or 0
    
    # Calculate average mastery
    avg_mastery = db.query(func.avg(VocabularySRS.mastery_level)).filter(VocabularySRS.user_id == current_user.id).scalar() or 0.0
    
    due_today = db.query(func.count(VocabularySRS.id)).filter(
        VocabularySRS.user_id == current_user.id,
        VocabularySRS.is_mastered == False,
        VocabularySRS.next_review_date <= date.today()
    ).scalar() or 0
    
    return VocabularyProgressStats(
        total_words_encountered=total_encountered,
        words_mastered=words_mastered,
        average_mastery_level=float(avg_mastery),
        words_due_today=due_today
    )

@router.get("/analytics")
def get_vocabulary_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Returns general counts
    return {"message": "Use /progress for core stats. Extended analytics pipeline to be routed to Data Warehouse."}
