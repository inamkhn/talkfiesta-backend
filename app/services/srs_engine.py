"""
TalkFiesta — SM-2 Spaced Repetition Engine
============================================
Enhanced SuperMemo-2 algorithm with adaptive parameters:
  - Word difficulty modulation (harder words reviewed more frequently)
  - Stale review gentler ramp-up (long absence = shorter first interval back)
  - Backward compatible: all new parameters are optional with safe defaults
"""
from datetime import date, timedelta
from typing import Optional, Tuple

MASTERY_THRESHOLD = 5
EF_FLOOR = 1.3

# CEFR difficulty → ease_factor multiplier
# Harder words reduce EF gains on success and increase EF losses on failure.
# This makes harder words reviewed more frequently.
DIFFICULTY_EF_MODIFIER: dict[str, float] = {
    "A1": 1.15,
    "A2": 1.10,
    "B1": 1.00,
    "B2": 0.92,
    "C1": 0.85,
    "C2": 0.78,
}

# Stale review thresholds (days since last review → interval multiplier)
# If a user hasn't reviewed in a long time, their first interval back
# is shortened proportionally. A full reset (reps=0) already sets interval=1,
# so this only affects the reps >= 1 case.
STALE_REVIEW_MULTIPLIER: list[tuple[int, float]] = [
    (60, 0.5),    # 60+ days absent → half the normal interval
    (30, 0.7),    # 30+ days absent → 70% of normal interval
    (14, 0.85),   # 14+ days absent → 85% of normal interval
]


def calculate_next_review(
    ease_factor: float,
    interval_days: int,
    repetitions: int,
    grade: int,
    word_difficulty: Optional[str] = None,
    time_since_last_review: Optional[int] = None,
) -> Tuple[float, int, int, date, bool]:
    """
    Enhanced SuperMemo-2 with adaptive factors.

    Args:
        ease_factor: Current EF multiplier (starts at 2.5).
        interval_days: Previous gap length in days.
        repetitions: Consecutive correct review count.
        grade: User self-assessment 0-5 (5 = perfect, 0 = forgot completely).
        word_difficulty: Optional CEFR level (A1-C2). Harder words get
            shorter intervals via EF modulation.
        time_since_last_review: Optional days since last review. Long
            absences trigger a gentler ramp-up on the next interval.

    Returns:
        (updated_ease_factor, new_interval, new_repetitions,
         next_review_date, is_mastered)
    """
    # Resolve difficulty modifier (1.0 = neutral)
    diff_mod = DIFFICULTY_EF_MODIFIER.get(word_difficulty or "B1", 1.0)

    # ── Calculate new interval ──────────────────────────────────────────────
    if grade >= 3:
        # User remembered the word
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * ease_factor)

        # Stale review: if long absence, shorten the interval
        if time_since_last_review is not None:
            for threshold, multiplier in STALE_REVIEW_MULTIPLIER:
                if time_since_last_review >= threshold:
                    new_interval = max(1, round(new_interval * multiplier))
                    break

        new_repetitions = repetitions + 1
    else:
        # User failed — reset sequence
        new_repetitions = 0
        new_interval = 1

    # ── Update Ease Factor ──────────────────────────────────────────────────
    # Standard SM-2 formula: EF = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    ef_delta = 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)

    # Apply difficulty modulation:
    #   - Successful reviews (grade >= 3): harder words get smaller EF gains
    #   - Failed reviews (grade < 3): harder words get larger EF penalties
    if grade >= 3:
        ef_delta *= diff_mod
    else:
        ef_delta *= (2.0 - diff_mod)

    new_ease_factor = ease_factor + ef_delta

    # Hard floor at 1.3
    if new_ease_factor < EF_FLOOR:
        new_ease_factor = EF_FLOOR

    # ── Finalize ────────────────────────────────────────────────────────────
    next_review_date = date.today() + timedelta(days=new_interval)
    is_mastered = new_repetitions >= MASTERY_THRESHOLD

    return new_ease_factor, new_interval, new_repetitions, next_review_date, is_mastered
