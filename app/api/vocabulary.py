"""
TalkFiesta — Vocabulary Router
================================
Thin HTTP translation layer. All business logic lives in VocabularyService.

Existing endpoints are backward compatible. New endpoints:
  - POST /review/batch  — submit multiple reviews in one request
  - GET  /words/paginated — cursor-based paginated word browsing
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.vocabulary_repository import VocabularyRepository
from app.services.vocabulary_service import VocabularyService
from app.schemas.vocabulary import (
    VocabularyWordResponse,
    VocabularyPracticeSubmit,
    VocabularyReviewSubmit,
    VocabularySRSResponse,
    VocabularyProgressStats,
    BatchReviewRequest,
    BatchReviewResponse,
    PaginatedWordResponse,
)
from app.schemas.common import ModuleContentResponse

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary & Spaced Repetition"])
logger = logging.getLogger(__name__)


def _get_service(db: Session) -> VocabularyService:
    """Build VocabularyService with repository for the current DB session."""
    return VocabularyService(VocabularyRepository(db))


# ── BROWSE ───────────────────────────────────────────────────────────────────

@router.get("/words", response_model=List[VocabularyWordResponse])
def get_words(
    cycle: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch words dynamically generated for this user's cycle."""
    svc = _get_service(db)
    return svc.get_words_for_cycle(current_user, cycle)


@router.get("/words/paginated", response_model=PaginatedWordResponse)
def get_words_paginated(
    cycle: int = 1,
    day: Optional[int] = Query(None, ge=1, le=21),
    cursor: Optional[str] = None,
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cursor-based paginated word browsing."""
    svc = _get_service(db)
    result = svc.get_words_paginated(current_user, cycle, day, cursor, page_size)
    return PaginatedWordResponse(**result)


@router.get("/words/{word_id}", response_model=VocabularyWordResponse)
def get_word_by_id(
    word_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch a single word by ID."""
    svc = _get_service(db)
    return svc.get_word_by_id(word_id)


# ── PRACTICE (NEW LEARNING) ─────────────────────────────────────────────────

@router.get("/practice", response_model=ModuleContentResponse[VocabularyWordResponse])
def get_todays_new_words(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the specific 10 new words assigned to the user's current day.
    Lazily creates an active plan if none exists and triggers AI generation
    when personalized content is missing.
    """
    svc = _get_service(db)
    result = svc.get_todays_words(db, current_user)
    return ModuleContentResponse(**result)


@router.post("/practice")
def submit_practice(
    payload: VocabularyPracticeSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a NEW flashcard as learned, dropping it into the SRS pipeline."""
    svc = _get_service(db)
    return svc.practice_word(db, current_user, payload.word_id)


# ── REVIEW (SPACED REPETITION) ──────────────────────────────────────────────

@router.get("/review", response_model=List[VocabularySRSResponse])
def get_due_srs_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch flashcards mathematically due for review TODAY, capped at 50."""
    svc = _get_service(db)
    return svc.get_due_reviews(current_user)


@router.post("/review")
def submit_srs_review(
    payload: VocabularyReviewSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User grades their memory 0-5. SM-2 Engine adjusts intervals mathematically."""
    svc = _get_service(db)
    return svc.submit_review(db, current_user, payload.word_id, payload.grade)


@router.post("/review/batch", response_model=BatchReviewResponse)
def submit_batch_review(
    payload: BatchReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit multiple word reviews in a single request.
    Reduces round trips from N to 1. Max 50 reviews per batch.
    """
    svc = _get_service(db)
    reviews = [{"word_id": r.word_id, "grade": r.grade} for r in payload.reviews]
    result = svc.submit_batch_review(db, current_user, reviews)
    return BatchReviewResponse(**result)


# ── STATS ────────────────────────────────────────────────────────────────────

@router.get("/review/stats")
def get_srs_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Breakdown of flashcard intervals."""
    svc = _get_service(db)
    return svc.get_review_stats(current_user)


# ── ANALYTICS ────────────────────────────────────────────────────────────────

@router.get("/progress", response_model=VocabularyProgressStats)
def get_vocabulary_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Core vocabulary progress statistics."""
    svc = _get_service(db)
    stats = svc.get_progress_stats(current_user)
    return VocabularyProgressStats(**stats)


@router.get("/analytics")
def get_vocabulary_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extended analytics placeholder."""
    return {
        "message": "Use /progress for core stats. Extended analytics pipeline to be routed to Data Warehouse."
    }
