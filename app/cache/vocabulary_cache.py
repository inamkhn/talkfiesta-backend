"""
TalkFiesta — Vocabulary Redis Cache
=====================================
Caches frequently-read, rarely-changing vocabulary data in Redis
to reduce DB load on the most-hit endpoints (stats, due reviews).

Cache key pattern: tf:vocab:{user_id}:{key}
All cached values are JSON-serialized dicts.

Invalidation strategy:
  - practice_word()  → invalidates review_stats + progress_stats
  - submit_review()  → invalidates review_stats + due_reviews
  - batch_review()   → single invalidation for review_stats + due_reviews
  - generation done  → invalidates todays_words + generation_status
"""
import json
import logging
from datetime import date
from typing import Optional

import redis
from app.config import settings

logger = logging.getLogger(__name__)

# ── TTL constants (seconds) ──────────────────────────────────────────────────
TTL_REVIEW_STATS = 300        # 5 min — stats change on practice/review
TTL_PROGRESS_STATS = 300      # 5 min — stats change on practice
TTL_DUE_REVIEWS = 60          # 1 min — lightweight, refreshes often
TTL_TODAYS_WORDS = 3600       # 1 hour — words don't change mid-session
TTL_GENERATION_STATUS = 30    # 30 sec — "is generation done?" polling


# ── Redis client (module-level singleton) ────────────────────────────────────
_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Lazy-initialize Redis connection with decode_responses for text data."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _key(user_id: str, suffix: str) -> str:
    """Build cache key: tf:vocab:{user_id}:{suffix}"""
    return f"tf:vocab:{user_id}:{suffix}"


def _safe_get(r: redis.Redis, key: str) -> Optional[dict]:
    """Read + JSON-deserialize a cache value. Returns None on miss or error."""
    try:
        raw = r.get(key)
        if raw is not None:
            return json.loads(raw)
    except (redis.ConnectionError, json.JSONDecodeError, TypeError) as exc:
        logger.debug("Cache GET miss for %s: %s", key, exc)
    return None


def _safe_set(r: redis.Redis, key: str, value: dict, ttl: int) -> None:
    """JSON-serialize + write a cache value. Silently fails on Redis errors."""
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except (redis.ConnectionError, TypeError) as exc:
        logger.debug("Cache SET failed for %s: %s", key, exc)


def _safe_delete(r: redis.Redis, *keys: str) -> None:
    """Delete one or more cache keys. Silently fails on Redis errors."""
    try:
        if keys:
            r.delete(*keys)
    except redis.ConnectionError as exc:
        logger.debug("Cache DELETE failed for %s: %s", keys, exc)


# ── Review Stats (words_learning, words_mastered, due_for_review_today) ──────

def get_review_stats(user_id: str) -> Optional[dict]:
    """
    Fetch cached review stats.
    Returns dict or None (cache miss).
    """
    r = _get_redis()
    return _safe_get(r, _key(user_id, "review_stats"))


def set_review_stats(user_id: str, stats: dict) -> None:
    """Cache review stats with 5-minute TTL."""
    r = _get_redis()
    _safe_set(r, _key(user_id, "review_stats"), stats, TTL_REVIEW_STATS)


def invalidate_review_stats(user_id: str) -> None:
    """Delete cached review stats (called on practice or review)."""
    r = _get_redis()
    _safe_delete(r, _key(user_id, "review_stats"))


# ── Progress Stats (total_encountered, mastered, avg_mastery, due_today) ─────

def get_progress_stats(user_id: str) -> Optional[dict]:
    """Fetch cached progress stats. Returns dict or None (cache miss)."""
    r = _get_redis()
    return _safe_get(r, _key(user_id, "progress_stats"))


def set_progress_stats(user_id: str, stats: dict) -> None:
    """Cache progress stats with 5-minute TTL."""
    r = _get_redis()
    _safe_set(r, _key(user_id, "progress_stats"), stats, TTL_PROGRESS_STATS)


def invalidate_progress_stats(user_id: str) -> None:
    """Delete cached progress stats (called on practice)."""
    r = _get_redis()
    _safe_delete(r, _key(user_id, "progress_stats"))


# ── Due Reviews (word IDs due for review today) ──────────────────────────────

def get_due_review_ids(user_id: str) -> Optional[list[str]]:
    """
    Fetch cached list of word IDs due for review.
    Returns list[str] or None (cache miss).
    The repository still loads the full SRS+word data for these IDs.
    """
    r = _get_redis()
    data = _safe_get(r, _key(user_id, "due_review_ids"))
    if isinstance(data, list):
        return data
    return None


def set_due_review_ids(user_id: str, word_ids: list[str]) -> None:
    """Cache due review word IDs with 1-minute TTL."""
    r = _get_redis()
    _safe_set(r, _key(user_id, "due_review_ids"), word_ids, TTL_DUE_REVIEWS)


def invalidate_due_reviews(user_id: str) -> None:
    """Delete cached due review IDs (called on review submission)."""
    r = _get_redis()
    _safe_delete(r, _key(user_id, "due_review_ids"))


# ── Today's Words (word IDs for the current day) ────────────────────────────

def get_todays_word_ids(user_id: str, cycle: int, day: int) -> Optional[list[str]]:
    """
    Fetch cached word IDs for a specific day.
    Returns list[str] or None (cache miss).
    """
    r = _get_redis()
    data = _safe_get(r, _key(user_id, f"words:{cycle}:{day}"))
    if isinstance(data, list):
        return data
    return None


def set_todays_word_ids(user_id: str, cycle: int, day: int, word_ids: list[str]) -> None:
    """Cache today's word IDs with 1-hour TTL."""
    r = _get_redis()
    _safe_set(r, _key(user_id, f"words:{cycle}:{day}"), word_ids, TTL_TODAYS_WORDS)


def invalidate_todays_words(user_id: str, cycle: int, day: int) -> None:
    """Delete cached word IDs for a day (called when generation completes)."""
    r = _get_redis()
    _safe_delete(r, _key(user_id, f"words:{cycle}:{day}"))


# ── Generation Status (is vocab generation in progress?) ─────────────────────

def get_generation_status(user_id: str, cycle: int) -> Optional[str]:
    """
    Fetch cached generation status.
    Returns "generating", "ready", or None (cache miss).
    """
    r = _get_redis()
    data = _safe_get(r, _key(user_id, f"gen_status:{cycle}"))
    if isinstance(data, dict):
        return data.get("status")
    return None


def set_generation_status(user_id: str, cycle: int, status: str) -> None:
    """
    Cache generation status with 30-second TTL.
    status: "generating" or "ready"
    """
    r = _get_redis()
    _safe_set(r, _key(user_id, f"gen_status:{cycle}"), {"status": status}, TTL_GENERATION_STATUS)


# ── Bulk Invalidation ───────────────────────────────────────────────────────

def invalidate_all(user_id: str) -> None:
    """
    Delete all cached vocabulary data for a user.
    Called on major state changes (plan completion, cycle change).
    Uses SCAN to find all matching keys.
    """
    r = _get_redis()
    pattern = _key(user_id, "*")
    try:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=50)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except redis.ConnectionError as exc:
        logger.warning("Cache invalidation failed for user %s: %s", user_id, exc)


def invalidate_on_practice(user_id: str) -> None:
    """Invalidate caches affected by practicing a new word."""
    invalidate_review_stats(user_id)
    invalidate_progress_stats(user_id)


def invalidate_on_review(user_id: str) -> None:
    """Invalidate caches affected by submitting a review."""
    invalidate_review_stats(user_id)
    invalidate_due_reviews(user_id)
