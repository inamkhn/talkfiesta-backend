import logging
from fastapi import Request
from slowapi import Limiter
from app.config import settings
from app.core.security import decode_token

logger = logging.getLogger(__name__)


def get_user_or_ip_key(request: Request) -> str:
    """
    Generate a rate-limiting key.
    If the request is authenticated via a Bearer JWT token, use the user ID.
    Otherwise, fall back to the client's IP address.
    """
    # 1. Check for JWT authorization
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        try:
            parts = auth_header.split(" ")
            if len(parts) == 2:
                token = parts[1]
                payload, error = decode_token(token)
                if not error and payload and payload.get("type") == "access":
                    user_id = payload.get("sub")
                    if user_id:
                        return f"user:{user_id}"
        except Exception as e:
            logger.debug(f"Failed to decode token for rate limiting key: {e}")

    # 2. Fallback to client IP
    client_host = request.client.host if request.client else "127.0.0.1"
    
    # Handle reverse proxy header
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_host = forwarded_for.split(",")[0].strip()

    return f"ip:{client_host}"


import redis

# Resilient connection check: check if Redis is online, fallback to memory if not
storage_uri = settings.REDIS_URL
try:
    r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1.0, socket_timeout=1.0)
    r.ping()
    logger.info("Successfully connected to Redis for rate limiter storage.")
except Exception as e:
    logger.warning(
        f"Redis is unreachable at {settings.REDIS_URL}. "
        f"Falling back to resilient in-memory rate limiting. Error: {e}"
    )
    storage_uri = "memory://"

# Instantiate Limiter globally with custom key function and resolved storage
limiter = Limiter(
    key_func=get_user_or_ip_key,
    storage_uri=storage_uri,
    default_limits=["120/minute"]
)
