"""
TalkFiesta — Vocabulary Service
=================================
Business logic layer for vocabulary practice and spaced repetition.
All vocabulary operations go through this service — the API router
is a thin HTTP translation layer only.

Responsibilities:
  - Word browsing with fallback chain (personalized → global by level → any global)
  - Practice (new learning): mark words learned, initialize SRS, check day completion
  - Review (spaced repetition): SM-2 grading, mastery tracking, batch reviews
  - Stats & analytics aggregation
  - Paginated word browsing
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.vocabulary_repository import VocabularyRepository
from app.services.srs_engine import calculate_next_review
from app.cache import vocabulary_cache as cache

logger = logging.getLogger(__name__)


class VocabularyService:
    """Business logic for vocabulary learning and spaced repetition review."""

    def __init__(self, repo: VocabularyRepository):
        self.repo = repo
        self.db: Session = repo.db

    # ── Word Browsing ────────────────────────────────────────────────────────

    def get_words_for_cycle(
        self, user: User, cycle: int
    ) -> list:
        """
        Fetch all words for a cycle with the full fallback chain:
        1. User-specific personalized words
        2. Global words matching user's CEFR level
        3. Any global words for the cycle
        """
        level = user.english_level or "B1"
        return self.repo.get_words_with_fallback(user.id, cycle, level)

    def get_words_for_day(
        self, user: User, cycle: int, day: int
    ) -> list:
        """Fetch words assigned to a specific day."""
        return self.repo.get_user_words_for_day(user.id, cycle, day)

    def get_word_by_id(self, word_id: str):
        """Fetch a single word. Raises 404 if not found."""
        word = self.repo.get_word_by_id(word_id)
        if not word:
            raise HTTPException(status_code=404, detail="Word not found")
        return word

    # ── Practice (New Learning) ──────────────────────────────────────────────

    def get_todays_words(self, db: Session, user: User) -> dict:
        """
        Get the specific 10 new words assigned to the user's current day.
        Lazily creates an active plan if none exists and triggers AI
        generation when personalized content is missing.

        Returns dict matching ModuleContentResponse shape:
            {status, items, message}
        """
        from app.services.plans_service import get_or_create_active_plan
        from app.schemas.common import ModuleContentStatus

        plan = get_or_create_active_plan(db, user)
        cycle = plan.cycle_number
        day = user.current_day

        words = self.repo.get_user_words_for_day(user.id, cycle, day)

        if words:
            return {
                "status": ModuleContentStatus.ready,
                "items": words,
                "message": "",
            }

        # No personalized words yet — trigger generation with Redis lock
        try:
            from app.core.lock import module_generation_lock
            from app.services.vocabulary_generator import generate_cycle_vocabulary

            with module_generation_lock(user.id, cycle, "vocabulary") as acquired:
                if acquired:
                    generate_cycle_vocabulary.delay(user.id, cycle)
                    logger.info(
                        "Queued vocab generation for user=%s cycle=%s day=%s",
                        user.id,
                        cycle,
                        day,
                    )
                else:
                    logger.info(
                        "Vocab generation already queued for user=%s cycle=%s",
                        user.id,
                        cycle,
                    )
        except Exception as exc:
            logger.warning("Could not queue vocab generation: %s", exc)

        return {
            "status": ModuleContentStatus.generating,
            "items": [],
            "message": "Personalizing your vocabulary words...",
        }

    def practice_word(self, db: Session, user: User, word_id: str) -> dict:
        """
        Mark a NEW flashcard as learned, dropping it into the SRS pipeline.

        Steps:
          1. Validate word exists
          2. Create or increment VocabularyProgress
          3. Initialize VocabularySRS if not exists (first review = tomorrow)
          4. Check day completion → advance day if all 3 activities done

        Returns dict: {message, word_id}
        """
        word = self.repo.get_word_by_id(word_id)
        if not word:
            raise HTTPException(status_code=404, detail="Word not found")

        # Update or create progress
        progress = self.repo.get_progress_for_word(user.id, word_id)
        if not progress:
            self.repo.create_progress(user.id, word_id)
        else:
            self.repo.increment_practice(progress)

        # Initialize SRS if not already tracked
        srs = self.repo.get_srs_for_word(user.id, word_id)
        if not srs:
            self.repo.create_srs(user.id, word_id)

        db.commit()

        # Invalidate caches affected by practicing a new word
        cache.invalidate_on_practice(user.id)

        # Check day completion for vocabulary activity
        self._check_day_complete_vocabulary(user, word)

        return {
            "message": "Word saved. Scheduled for first SRS review tomorrow.",
            "word_id": word_id,
        }

    # ── Review (Spaced Repetition) ───────────────────────────────────────────

    def get_due_reviews(self, user: User, limit: int = 50) -> list:
        """
        Fetch words due for review today.
        Uses joinedload to eagerly load word data (avoids N+1).
        Capped at 50 to prevent overload after long absences.
        """
        return self.repo.get_due_reviews(user.id, limit)

    def submit_review(
        self, db: Session, user: User, word_id: str, grade: int
    ) -> dict:
        """
        User grades their memory 0-5. SM-2 Engine adjusts intervals mathematically.

        Returns dict: {message, grade, next_review_date, is_mastered, word_id}
        """
        if grade < 0 or grade > 5:
            raise HTTPException(
                status_code=400, detail="Grade must be between 0 and 5"
            )

        srs = self.repo.get_srs_for_word(user.id, word_id)
        if not srs:
            raise HTTPException(
                status_code=404,
                detail="Word not in SRS tracking yet. Practice it first.",
            )

        if srs.is_mastered:
            return {
                "message": "Word already mastered. Skipping update.",
                "grade": grade,
                "next_review_date": srs.next_review_date,
                "is_mastered": True,
                "word_id": word_id,
            }

        # SM-2 calculation with adaptive parameters
        adaptive = self._get_adaptive_params(srs)
        new_ef, new_interval, new_reps, next_date, is_mastered = (
            calculate_next_review(
                ease_factor=srs.ease_factor,
                interval_days=srs.interval_days,
                repetitions=srs.repetitions,
                grade=grade,
                word_difficulty=adaptive["word_difficulty"],
                time_since_last_review=adaptive["time_since_last_review"],
            )
        )

        # Update SRS
        srs.ease_factor = new_ef
        srs.interval_days = new_interval
        srs.repetitions = new_reps
        srs.next_review_date = next_date
        srs.last_reviewed = date.today()
        srs.review_count += 1

        # Track lapses (times user forgot the word)
        if grade < 3:
            srs.lapse_count = (srs.lapse_count or 0) + 1

        if is_mastered:
            self.repo.mark_mastered(srs)
            self.repo.update_mastery_on_word(user.id, word_id, mastery_level=5)

        db.commit()

        # Invalidate caches affected by submitting a review
        cache.invalidate_on_review(user.id)

        return {
            "message": "Review recorded.",
            "grade": grade,
            "next_review_date": next_date,
            "is_mastered": is_mastered,
            "word_id": word_id,
        }

    def submit_batch_review(
        self,
        db: Session,
        user: User,
        reviews: list[dict],
    ) -> dict:
        """
        Process multiple word reviews in a single transaction.
        Reduces round trips from N to 1, and uses a single cache invalidation.

        Args:
            reviews: list of {"word_id": str, "grade": int} dicts.

        Returns dict: {results: list[dict], stats_updated: dict}
        """
        word_ids = [r["word_id"] for r in reviews]

        # Fetch all SRS records in one query (with eager-loaded words)
        srs_records = self.repo.get_srs_for_words(user.id, word_ids)
        srs_by_word = {s.word_id: s for s in srs_records}

        results = []
        for review in reviews:
            word_id = review["word_id"]
            grade = review["grade"]

            # Validate grade
            if grade < 0 or grade > 5:
                results.append({
                    "word_id": word_id,
                    "grade": grade,
                    "error": "Grade must be between 0 and 5",
                    "next_review_date": None,
                    "is_mastered": False,
                })
                continue

            srs = srs_by_word.get(word_id)
            if not srs:
                results.append({
                    "word_id": word_id,
                    "grade": grade,
                    "error": "Word not in SRS tracking yet. Practice it first.",
                    "next_review_date": None,
                    "is_mastered": False,
                })
                continue

            if srs.is_mastered:
                results.append({
                    "word_id": word_id,
                    "grade": grade,
                    "error": None,
                    "next_review_date": srs.next_review_date,
                    "is_mastered": True,
                })
                continue

            # SM-2 calculation with adaptive parameters
            adaptive = self._get_adaptive_params(srs)
            new_ef, new_interval, new_reps, next_date, is_mastered = (
                calculate_next_review(
                    ease_factor=srs.ease_factor,
                    interval_days=srs.interval_days,
                    repetitions=srs.repetitions,
                    grade=grade,
                    word_difficulty=adaptive["word_difficulty"],
                    time_since_last_review=adaptive["time_since_last_review"],
                )
            )

            srs.ease_factor = new_ef
            srs.interval_days = new_interval
            srs.repetitions = new_reps
            srs.next_review_date = next_date
            srs.last_reviewed = date.today()
            srs.review_count += 1

            # Track lapses (times user forgot the word)
            if grade < 3:
                srs.lapse_count = (srs.lapse_count or 0) + 1

            if is_mastered:
                self.repo.mark_mastered(srs)
                self.repo.update_mastery_on_word(user.id, word_id, mastery_level=5)

            results.append({
                "word_id": word_id,
                "grade": grade,
                "error": None,
                "next_review_date": next_date,
                "is_mastered": is_mastered,
            })

        # Single commit for all reviews
        db.commit()

        # Invalidate caches affected by reviews (single call, not per-word)
        cache.invalidate_on_review(user.id)

        # Fetch fresh stats and cache them for subsequent reads
        fresh_stats = self.repo.get_review_stats(user.id)
        cache.set_review_stats(user.id, fresh_stats)

        return {
            "results": results,
            "stats_updated": fresh_stats,
        }

    # ── Stats & Analytics ────────────────────────────────────────────────────

    def get_review_stats(self, user: User) -> dict:
        """
        Quick SRS stats: learning, mastered, due_today.
        Cache-first: reads from Redis on hit, falls through to DB on miss.
        Used by GET /review.stats endpoint.
        """
        cached = cache.get_review_stats(user.id)
        if cached is not None:
            return cached

        stats = self.repo.get_review_stats(user.id)
        cache.set_review_stats(user.id, stats)
        return stats

    def get_progress_stats(self, user: User) -> dict:
        """
        Full progress analytics.
        Cache-first: reads from Redis on hit, falls through to DB on miss.
        Used by GET /progress endpoint (maps to VocabularyProgressStats schema).
        """
        cached = cache.get_progress_stats(user.id)
        if cached is not None:
            return cached

        stats = self.repo.get_progress_stats(user.id)
        cache.set_progress_stats(user.id, stats)
        return stats

    # ── Pagination ───────────────────────────────────────────────────────────

    def get_words_paginated(
        self,
        user: User,
        cycle: int,
        day: Optional[int] = None,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> dict:
        """
        Cursor-based paginated word browsing.

        Returns dict: {words, next_cursor, has_more, total_count}
        """
        words, total_count = self.repo.get_words_paginated(
            user_id=user.id,
            cycle=cycle,
            day=day,
            cursor=cursor,
            page_size=page_size,
        )

        has_more = len(words) > page_size
        if has_more:
            words = words[:page_size]

        next_cursor = words[-1].id if words and has_more else None

        return {
            "words": words,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total_count": total_count,
        }

    # ── Private Helpers ──────────────────────────────────────────────────────

    def _get_adaptive_params(self, srs) -> dict:
        """
        Extract adaptive parameters from an SRS record for the SM-2 engine.

        Returns dict with:
          - word_difficulty: CEFR level from the eagerly loaded word
          - time_since_last_review: days since last review (None if unavailable)
        """
        word_difficulty = None
        if srs.word:
            word_difficulty = srs.word.difficulty

        time_since_last_review = None
        if srs.last_reviewed:
            time_since_last_review = (date.today() - srs.last_reviewed).days

        return {
            "word_difficulty": word_difficulty,
            "time_since_last_review": time_since_last_review,
        }

    def _check_day_complete_vocabulary(self, user: User, word) -> None:
        """
        Check if all vocabulary words for the user's current day are practiced.
        If yes, delegate to the centralized mark_activity_complete() to set
        the vocabulary_done flag and advance the day if all 3 activities are done.
        """
        if (
            word.user_id == user.id
            and word.day == user.current_day
            and user.active_plan_id
        ):
            total = self.repo.count_day_words(
                user.id, word.cycle, user.current_day
            )
            practiced = self.repo.count_practiced_day_words(
                user.id, word.cycle, user.current_day
            )

            if total > 0 and practiced >= total:
                from app.services.progress_service import mark_activity_complete
                mark_activity_complete(
                    self.db, user, "vocabulary", word.cycle, word.day
                )
