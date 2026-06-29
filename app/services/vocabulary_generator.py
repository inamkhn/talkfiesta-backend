"""
TalkFiesta — Vocabulary Generator (Celery Task)
=================================================
Generates 210 personalized vocabulary words per cycle using Google Gemini.

Optimizations over original:
  - Idempotency guard: skips if words already exist for user+cycle
  - Partial failure handling: saves each successful batch immediately
  - Smarter struggle context: uses SRS lapse_count + mastery_level
  - AI output validation: graceful defaults for malformed/missing fields
  - Celery-native retry with autoretry_for instead of blocking sleep
"""
import logging
import json
import time
from typing import Optional

from celery import shared_task
from google import genai
from google.genai import types

from app.db.session import SessionLocal
from app.models.user import User
from app.models.vocabulary import VocabularyWord, VocabularyProgress, VocabularySRS
from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

EXPECTED_WORDS_PER_DAY = 10
TOTAL_DAYS = 21
BATCHES = [(1, 7), (8, 14), (15, 21)]  # 3 batches × 7 days × 10 words = 210

REQUIRED_FIELDS = {"word", "definition", "day", "position_in_day"}
OPTIONAL_LIST_FIELDS = {"example_sentences", "synonyms", "antonyms", "collocations"}
OPTIONAL_STRING_FIELDS = {"phonetic", "part_of_speech", "memory_tip"}

MODELS_TO_TRY = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_word(raw: dict, user_level: str) -> Optional[dict]:
    """
    Validate a single word dict from Gemini output.
    Returns a cleaned dict with defaults for missing optional fields,
    or None if required fields are missing.
    """
    if not isinstance(raw, dict):
        return None

    # Check required fields
    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        logger.warning("Skipping word — missing required fields: %s", missing)
        return None

    word_text = raw.get("word", "").strip()
    if not word_text:
        logger.warning("Skipping word — empty 'word' field")
        return None

    # Build clean dict with safe defaults
    clean = {
        "word": word_text,
        "definition": str(raw.get("definition", "")).strip(),
        "day": int(raw.get("day", 1)),
        "position_in_day": int(raw.get("position_in_day", 1)),
    }

    # Optional string fields — default to empty string
    for field in OPTIONAL_STRING_FIELDS:
        clean[field] = str(raw.get(field, "") or "").strip()

    # Optional list fields — default to empty list, ensure list type
    for field in OPTIONAL_LIST_FIELDS:
        val = raw.get(field)
        if isinstance(val, list):
            clean[field] = [str(x) for x in val if x]
        else:
            clean[field] = []

    # Difficulty: validate it's a valid CEFR level, fall back to user level
    valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}
    diff = str(raw.get("difficulty", "") or "").strip().upper()
    clean["difficulty"] = diff if diff in valid_levels else user_level

    return clean


def _build_struggle_context(db, user_id: str, user_level: str) -> str:
    """
    Build AI prompt context from words the user struggled with.
    Uses both mastery_level (from VocabularyProgress) and lapse_count
    (from VocabularySRS) for richer signal.
    """
    # High-lapse words (forgotten 2+ times in SRS reviews)
    high_lapse_words = (
        db.query(VocabularySRS)
        .join(VocabularyWord)
        .filter(
            VocabularySRS.user_id == user_id,
            VocabularySRS.lapse_count >= 2,
        )
        .order_by(VocabularySRS.lapse_count.desc())
        .limit(10)
        .all()
    )

    # Low-mastery words (practiced but never stuck)
    low_mastery_words = (
        db.query(VocabularyProgress)
        .join(VocabularyWord)
        .filter(
            VocabularyProgress.user_id == user_id,
            VocabularyProgress.mastery_level < 3,
        )
        .order_by(VocabularyProgress.times_practiced.desc())
        .limit(10)
        .all()
    )

    parts = []

    if high_lapse_words:
        words = [srs.word.word for srs in high_lapse_words if srs.word]
        if words:
            parts.append(
                f"Words they repeatedly forgot (high lapse count): {', '.join(words)}"
            )

    if low_mastery_words:
        words = [p.word.word for p in low_mastery_words if p.word]
        if words:
            parts.append(
                f"Words with low mastery (practiced but not retained): {', '.join(words)}"
            )

    if not parts:
        return ""

    return (
        "IMPORTANT: Reinforce word families and semantic fields related to "
        "these previously struggled words:\n" + "\n".join(parts)
    )


def _generate_batch(
    client, user: User, cycle: int, day_start: int, day_end: int,
    struggle_context: str,
) -> list[dict]:
    """
    Call Gemini to generate words for days day_start..day_end (inclusive).
    Returns validated list of word dicts. Raises RuntimeError after all retries fail.
    """
    num_days = day_end - day_start + 1
    total_words = num_days * EXPECTED_WORDS_PER_DAY
    user_level = user.english_level or "B1"

    prompt = f"""
    You are a highly skilled CEFR native English curriculum expert.
    Generate exactly {total_words} vocabulary words for a user learning English.
    User Level: {user_level}.
    Learning Goal: {user.learning_goal or 'conversational'}.
    Cycle Number: {cycle}.

    {struggle_context}

    Organize the words into exactly {num_days} days (days {day_start} to {day_end}), 10 words per day.
    Return a strict JSON ARRAY of EXACTLY {total_words} objects. Each object MUST have:
    - "word": string
    - "phonetic": string (IPA)
    - "part_of_speech": string
    - "definition": string
    - "example_sentences": array of exactly 3 string examples
    - "synonyms": array of strings (max 3)
    - "antonyms": array of strings (max 3)
    - "collocations": array of strings (max 3 common pairings)
    - "memory_tip": string mnemonic device
    - "difficulty": string CEFR level
    - "day": integer ({day_start} through {day_end})
    - "position_in_day": integer (1 through 10)
    """

    last_error = None

    for attempt in range(4):
        model = MODELS_TO_TRY[min(attempt, len(MODELS_TO_TRY) - 1)]
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            raw_text = response.text.strip()

            # Strip markdown fences if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            raw_words = json.loads(raw_text.strip())

            if not isinstance(raw_words, list):
                raise ValueError(f"Expected JSON array, got {type(raw_words).__name__}")

            # Validate each word individually
            validated = []
            for raw_word in raw_words:
                clean = _validate_word(raw_word, user_level)
                if clean:
                    validated.append(clean)

            logger.info(
                "Batch days %d-%d: %d/%d words valid via %s",
                day_start, day_end, len(validated), len(raw_words), model,
            )
            return validated

        except Exception as e:
            last_error = e
            wait = 5 * (2 ** attempt)  # 5s, 10s, 20s, 40s
            logger.warning(
                "Batch days %d-%d attempt %d (%s) failed: %s. Retrying in %ds...",
                day_start, day_end, attempt + 1, model, e, wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"All retries failed for batch days {day_start}-{day_end}: {last_error}"
    )


def _save_batch(db, user: User, cycle: int, words_data: list[dict]) -> int:
    """
    Convert validated word dicts to VocabularyWord ORM objects and persist.
    Returns the count of words saved.
    """
    db_words = []
    for wd in words_data:
        db_words.append(VocabularyWord(
            user_id=user.id,
            cycle=cycle,
            day=wd["day"],
            position_in_day=wd["position_in_day"],
            word=wd["word"],
            phonetic=wd.get("phonetic", ""),
            part_of_speech=wd.get("part_of_speech", ""),
            definition=wd["definition"],
            example_sentences=wd.get("example_sentences", []),
            synonyms=wd.get("synonyms", []),
            antonyms=wd.get("antonyms", []),
            collocations=wd.get("collocations", []),
            memory_tip=wd.get("memory_tip", ""),
            difficulty=wd.get("difficulty", user.english_level or "B1"),
        ))

    if db_words:
        db.bulk_save_objects(db_words)
        db.commit()

    return len(db_words)


# ── Celery Task ──────────────────────────────────────────────────────────────

@shared_task(
    name="app.services.vocabulary_generator.generate_cycle_vocabulary",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(RuntimeError,),
)
def generate_cycle_vocabulary(self, user_id: str, cycle: int):
    """
    Generate 210 personalized vocabulary words for a user's cycle.

    Optimizations:
      - Idempotency: exits early if words already exist for user+cycle
      - Partial failure: saves each successful batch immediately
      - Graceful degradation: skips failed batches, logs warnings
      - Struggle-aware: uses SRS lapse_count for richer reinforcement
    """
    logger.info(
        "Starting vocab generation for User %s, Cycle %s (attempt %d)",
        user_id, cycle, self.request.retries + 1,
    )

    db = SessionLocal()
    client = genai.Client(api_key=settings.GOOGLE_AI_STUDIO_API_KEY)

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error("User %s not found — aborting.", user_id)
            return

        # ── Idempotency guard ───────────────────────────────────────────
        existing_count = (
            db.query(VocabularyWord)
            .filter(
                VocabularyWord.user_id == user_id,
                VocabularyWord.cycle == cycle,
            )
            .count()
        )
        expected_total = TOTAL_DAYS * EXPECTED_WORDS_PER_DAY

        if existing_count >= expected_total:
            logger.info(
                "User %s cycle %s already has %d words — skipping.",
                user_id, cycle, existing_count,
            )
            return

        if existing_count > 0:
            logger.warning(
                "User %s cycle %s has %d/%d words — will top up missing batches.",
                user_id, cycle, existing_count, expected_total,
            )

        # ── Build struggle context ──────────────────────────────────────
        struggle_context = _build_struggle_context(db, user_id, user.english_level or "B1")

        # ── Generate and save each batch independently ──────────────────
        total_saved = 0
        failed_batches = []

        for day_start, day_end in BATCHES:
            # Check if this batch's days already have words (for top-up)
            batch_existing = (
                db.query(VocabularyWord)
                .filter(
                    VocabularyWord.user_id == user_id,
                    VocabularyWord.cycle == cycle,
                    VocabularyWord.day >= day_start,
                    VocabularyWord.day <= day_end,
                )
                .count()
            )
            batch_expected = (day_end - day_start + 1) * EXPECTED_WORDS_PER_DAY

            if batch_existing >= batch_expected:
                logger.info(
                    "Days %d-%d already have %d words — skipping batch.",
                    day_start, day_end, batch_existing,
                )
                total_saved += batch_existing
                continue

            logger.info("Calling Gemini for batch: days %d-%d...", day_start, day_end)
            try:
                validated_words = _generate_batch(
                    client, user, cycle, day_start, day_end, struggle_context,
                )
                saved = _save_batch(db, user, cycle, validated_words)
                total_saved += saved
                logger.info(
                    "Batch days %d-%d saved: %d words", day_start, day_end, saved,
                )
            except Exception as e:
                logger.error(
                    "Batch days %d-%d failed permanently: %s",
                    day_start, day_end, e,
                )
                failed_batches.append((day_start, day_end, str(e)))

        # ── Summary ─────────────────────────────────────────────────────
        if failed_batches:
            logger.warning(
                "Generation complete for User %s Cycle %s: %d words saved, "
                "%d batches failed (days: %s). Task will retry.",
                user_id, cycle, total_saved, len(failed_batches),
                [f"{s}-{e}" for s, e, _ in failed_batches],
            )
            if total_saved == 0:
                raise RuntimeError(
                    f"All batches failed for user {user_id} cycle {cycle}"
                )
        else:
            logger.info(
                "Successfully generated %d words for User %s Cycle %s.",
                total_saved, user_id, cycle,
            )

    except RuntimeError:
        # Let Celery autoretry handle this
        raise
    except Exception as e:
        logger.error(
            "Unexpected error generating vocabulary for User %s: %s",
            user_id, e, exc_info=True,
        )
        db.rollback()
        raise
    finally:
        db.close()
