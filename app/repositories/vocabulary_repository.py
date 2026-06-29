"""
TalkFiesta — Vocabulary Repository
====================================
Single source of truth for all database queries against
VocabularyWord, VocabularyProgress, and VocabularySRS tables.

Every module (router, service, Celery task) accesses vocabulary data
through this repository — never via raw DB queries elsewhere.
"""
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.vocabulary import VocabularyWord, VocabularyProgress, VocabularySRS

logger = logging.getLogger(__name__)


class VocabularyRepository:
    """Data access layer for the vocabulary domain."""

    def __init__(self, db: Session):
        self.db = db

    # ── Word Queries ─────────────────────────────────────────────────────────

    def get_word_by_id(self, word_id: str) -> Optional[VocabularyWord]:
        """Fetch a single word by its primary key."""
        return self.db.query(VocabularyWord).filter(
            VocabularyWord.id == word_id
        ).first()

    def get_user_words_for_cycle(
        self, user_id: str, cycle: int
    ) -> list[VocabularyWord]:
        """All personalized words for a user's cycle, ordered by day then position."""
        return (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
            )
            .order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc())
            .all()
        )

    def get_user_words_for_day(
        self, user_id: str, cycle: int, day: int
    ) -> list[VocabularyWord]:
        """Personalized words for a specific day, ordered by position."""
        return (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
                VocabularyWord.day == day,
            )
            .order_by(VocabularyWord.position_in_day.asc())
            .all()
        )

    def get_global_words_by_level(
        self, cycle: int, level: str
    ) -> list[VocabularyWord]:
        """Fallback: globally seeded words matching cycle + CEFR difficulty."""
        return (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id.is_(None),
                VocabularyWord.cycle == cycle,
                VocabularyWord.difficulty == level,
            )
            .order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc())
            .all()
        )

    def get_global_words_any(self, cycle: int) -> list[VocabularyWord]:
        """Fallback: any globally seeded words for a cycle (no level filter)."""
        return (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id.is_(None),
                VocabularyWord.cycle == cycle,
            )
            .order_by(VocabularyWord.day.asc(), VocabularyWord.position_in_day.asc())
            .all()
        )

    def get_words_with_fallback(
        self, user_id: str, cycle: int, level: str
    ) -> list[VocabularyWord]:
        """
        Try user-specific words first, then global words by level,
        then any global words. Returns the first non-empty result.
        """
        words = self.get_user_words_for_cycle(user_id, cycle)
        if words:
            return words

        words = self.get_global_words_by_level(cycle, level)
        if words:
            return words

        return self.get_global_words_any(cycle)

    def count_day_words(self, user_id: str, cycle: int, day: int) -> int:
        """Count how many words are assigned for a specific day."""
        return (
            self.db.query(func.count(VocabularyWord.id))
            .filter(
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
                VocabularyWord.day == day,
            )
            .scalar()
        ) or 0

    # ── Progress Queries ─────────────────────────────────────────────────────

    def get_progress_for_word(
        self, user_id: str, word_id: str
    ) -> Optional[VocabularyProgress]:
        """Fetch progress record for a specific user+word pair."""
        return (
            self.db.query(VocabularyProgress)
            .filter(
                VocabularyProgress.user_id == user_id,
                VocabularyProgress.word_id == word_id,
            )
            .first()
        )

    def create_progress(
        self, user_id: str, word_id: str
    ) -> VocabularyProgress:
        """Create a new progress record with times_practiced=1."""
        progress = VocabularyProgress(
            id=str(uuid.uuid4()),
            user_id=user_id,
            word_id=word_id,
            times_practiced=1,
            times_correct=0,
            mastery_level=0,
            last_practiced=date.today(),
            created_at=datetime.utcnow(),
        )
        self.db.add(progress)
        return progress

    def increment_practice(self, progress: VocabularyProgress) -> None:
        """Increment practice count and update last_practiced."""
        progress.times_practiced += 1
        progress.last_practiced = date.today()

    def count_practiced_day_words(
        self, user_id: str, cycle: int, day: int
    ) -> int:
        """
        Count how many words for a day the user has practiced at least once.
        Joins VocabularyProgress with VocabularyWord.
        """
        return (
            self.db.query(func.count(VocabularyProgress.id))
            .join(
                VocabularyWord,
                VocabularyProgress.word_id == VocabularyWord.id,
            )
            .filter(
                VocabularyProgress.user_id == user_id,
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
                VocabularyWord.day == day,
            )
            .scalar()
        ) or 0

    def get_struggled_words(
        self, user_id: str, limit: int = 20
    ) -> list[VocabularyProgress]:
        """
        Words the user has struggled with (mastery < 3), ordered by
        practice count descending. Used by vocabulary generator to
        reinforce weak word families in the next cycle.
        """
        return (
            self.db.query(VocabularyProgress)
            .join(VocabularyWord, VocabularyProgress.word_id == VocabularyWord.id)
            .options(joinedload(VocabularyProgress.word))
            .filter(
                VocabularyProgress.user_id == user_id,
                VocabularyProgress.mastery_level < 3,
            )
            .order_by(VocabularyProgress.times_practiced.desc())
            .limit(limit)
            .all()
        )

    def update_mastery_on_word(
        self, user_id: str, word_id: str, mastery_level: int
    ) -> None:
        """Sync mastery level on VocabularyProgress when SRS marks a word mastered."""
        progress = self.get_progress_for_word(user_id, word_id)
        if progress:
            progress.mastery_level = mastery_level

    # ── SRS Queries ──────────────────────────────────────────────────────────

    def get_srs_for_word(
        self, user_id: str, word_id: str
    ) -> Optional[VocabularySRS]:
        """Fetch SRS tracking record for a specific user+word pair."""
        return (
            self.db.query(VocabularySRS)
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.word_id == word_id,
            )
            .first()
        )

    def create_srs(
        self, user_id: str, word_id: str
    ) -> VocabularySRS:
        """
        Create a new SRS record. First review is scheduled for tomorrow.
        Default ease_factor = 2.5 (SM-2 standard starting value).
        """
        srs = VocabularySRS(
            id=str(uuid.uuid4()),
            user_id=user_id,
            word_id=word_id,
            ease_factor=2.5,
            interval_days=0,
            repetitions=0,
            mastery_level=0,
            review_count=0,
            next_review_date=date.today() + timedelta(days=1),
            last_reviewed=date.today(),
            is_mastered=False,
            created_at=datetime.utcnow(),
        )
        self.db.add(srs)
        return srs

    def get_due_reviews(
        self, user_id: str, limit: int = 50
    ) -> list[VocabularySRS]:
        """
        Fetch SRS entries due for review today (next_review_date <= today).
        Eagerly loads the related VocabularyWord to avoid N+1 queries
        when the frontend needs word data alongside SRS data.
        """
        return (
            self.db.query(VocabularySRS)
            .options(joinedload(VocabularySRS.word))
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.is_mastered == False,
                VocabularySRS.next_review_date <= date.today(),
            )
            .order_by(VocabularySRS.next_review_date.asc())
            .limit(limit)
            .all()
        )

    def mark_mastered(self, srs: VocabularySRS) -> None:
        """Mark an SRS entry as fully mastered."""
        srs.is_mastered = True
        srs.mastered_at = datetime.utcnow()
        srs.mastery_level = 5

    # ── Aggregate / Stats Queries ────────────────────────────────────────────

    def count_learning(self, user_id: str) -> int:
        """Count words currently in the learning pipeline (not yet mastered)."""
        return (
            self.db.query(func.count(VocabularySRS.id))
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.is_mastered == False,
            )
            .scalar()
        ) or 0

    def count_mastered(self, user_id: str) -> int:
        """Count words that have reached mastery threshold."""
        return (
            self.db.query(func.count(VocabularySRS.id))
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.is_mastered == True,
            )
            .scalar()
        ) or 0

    def count_due_today(self, user_id: str) -> int:
        """Count words due for review today (not mastered, review date <= today)."""
        return (
            self.db.query(func.count(VocabularySRS.id))
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.is_mastered == False,
                VocabularySRS.next_review_date <= date.today(),
            )
            .scalar()
        ) or 0

    def count_total_encountered(self, user_id: str) -> int:
        """Count total words the user has ever practiced (VocabularyProgress rows)."""
        return (
            self.db.query(func.count(VocabularyProgress.id))
            .filter(VocabularyProgress.user_id == user_id)
            .scalar()
        ) or 0

    def avg_mastery_level(self, user_id: str) -> float:
        """Average mastery level across all SRS-tracked words."""
        result = (
            self.db.query(func.avg(VocabularySRS.mastery_level))
            .filter(VocabularySRS.user_id == user_id)
            .scalar()
        )
        return float(result) if result else 0.0

    def get_review_stats(self, user_id: str) -> dict:
        """
        Single-call aggregation of learning/mastered/due counts.
        Replaces 3 separate queries from the old router with 1 dict return.
        """
        return {
            "words_learning": self.count_learning(user_id),
            "words_mastered": self.count_mastered(user_id),
            "due_for_review_today": self.count_due_today(user_id),
        }

    def get_progress_stats(self, user_id: str) -> dict:
        """
        Full progress statistics for the /progress endpoint.
        Returns all fields needed by VocabularyProgressStats schema.
        """
        return {
            "total_words_encountered": self.count_total_encountered(user_id),
            "words_mastered": self.count_mastered(user_id),
            "average_mastery_level": self.avg_mastery_level(user_id),
            "words_due_today": self.count_due_today(user_id),
        }

    # ── Batch / Bulk Operations ──────────────────────────────────────────────

    def get_srs_for_words(
        self, user_id: str, word_ids: list[str]
    ) -> list[VocabularySRS]:
        """
        Fetch SRS records for multiple words in a single query.
        Used by batch review to avoid N queries for N words.
        """
        if not word_ids:
            return []
        return (
            self.db.query(VocabularySRS)
            .options(joinedload(VocabularySRS.word))
            .filter(
                VocabularySRS.user_id == user_id,
                VocabularySRS.word_id.in_(word_ids),
            )
            .all()
        )

    def get_words_by_ids(self, word_ids: list[str]) -> list[VocabularyWord]:
        """Fetch multiple words by their IDs in a single query."""
        if not word_ids:
            return []
        return (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.id.in_(word_ids))
            .all()
        )

    # ── Paginated Queries ────────────────────────────────────────────────────

    def get_words_paginated(
        self,
        user_id: str,
        cycle: int,
        day: Optional[int] = None,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> tuple[list[VocabularyWord], int]:
        """
        Cursor-based pagination for word browsing.

        Args:
            user_id: User whose words to fetch.
            cycle: Cycle number to filter by.
            day: Optional day filter (None = all days in cycle).
            cursor: Last word_id from previous page (None = first page).
            page_size: Number of words per page (max 50).

        Returns:
            (words, total_count) — total_count is only computed on first page (cursor=None).
        """
        page_size = min(page_size, 50)

        query = (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
            )
        )

        if day is not None:
            query = query.filter(VocabularyWord.day == day)

        # Cursor: fetch words with id > cursor (ordered by day, position, id)
        if cursor:
            cursor_word = (
                self.db.query(VocabularyWord)
                .filter(VocabularyWord.id == cursor)
                .first()
            )
            if cursor_word:
                query = query.filter(
                    (VocabularyWord.day > cursor_word.day)
                    | (
                        (VocabularyWord.day == cursor_word.day)
                        & (VocabularyWord.position_in_day > cursor_word.position_in_day)
                    )
                    | (
                        (VocabularyWord.day == cursor_word.day)
                        & (VocabularyWord.position_in_day == cursor_word.position_in_day)
                        & (VocabularyWord.id > cursor)
                    )
                )

        words = (
            query
            .order_by(
                VocabularyWord.day.asc(),
                VocabularyWord.position_in_day.asc(),
                VocabularyWord.id.asc(),
            )
            .limit(page_size + 1)  # fetch one extra to detect has_more
            .all()
        )

        # Total count only on first page (expensive, skip on subsequent pages)
        total_count = 0
        if cursor is None:
            count_query = (
                self.db.query(func.count(VocabularyWord.id))
                .filter(
                    VocabularyWord.user_id == user_id,
                    VocabularyWord.cycle == cycle,
                )
            )
            if day is not None:
                count_query = count_query.filter(VocabularyWord.day == day)
            total_count = count_query.scalar() or 0

        return words[:page_size], total_count
