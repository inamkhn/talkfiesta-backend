"""
TalkFiesta — Redis Lock Helpers
================================
Simple Redis-based locks to prevent duplicate Celery task queuing
for the same (user, cycle, module) triplet.
"""
import logging
from contextlib import contextmanager

import redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


@contextmanager
def module_generation_lock(user_id: str, cycle: int, module: str, ttl_seconds: int = 60):
    """
    Acquire a Redis lock for the given (user, cycle, module).
    Yields True if lock was acquired, False otherwise.
    """
    r = _get_redis()
    lock_key = f"tf:gen_lock:{user_id}:{cycle}:{module}"
    acquired = False
    try:
        acquired = r.set(lock_key, "1", nx=True, ex=ttl_seconds) is not None
        yield acquired
    finally:
        if acquired:
            try:
                r.delete(lock_key)
            except Exception:
                logger.exception("Failed to release lock %s", lock_key)
