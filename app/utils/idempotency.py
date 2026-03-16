from __future__ import annotations

import logging
from datetime import timedelta

import redis as redis_lib

from app.core.config import settings

logger = logging.getLogger("opsly.idempotency")

_redis_client: redis_lib.Redis | None = None

IDEMPOTENCY_TTL_SECONDS = 86_400  # 24 hours


def get_redis() -> redis_lib.Redis:
    """Return a shared Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def check_idempotency_key(key: str) -> str | None:
    """
    Check whether an idempotency key has been seen before.

    Returns:
        The cached JSON response string if the key exists, else None.
    """
    try:
        r = get_redis()
        return r.get(f"idem:{key}")
    except Exception as exc:
        logger.warning("Redis idempotency check failed: %s", exc)
        return None


def store_idempotency_key(key: str, response_body: str) -> None:
    """
    Store an idempotency key with a 24-hour TTL.

    Args:
        key: The X-Idempotency-Key header value.
        response_body: JSON-serialised response to return on duplicate requests.
    """
    try:
        r = get_redis()
        r.setex(f"idem:{key}", IDEMPOTENCY_TTL_SECONDS, response_body)
    except Exception as exc:
        logger.warning("Redis idempotency store failed: %s", exc)


def add_to_blacklist(token: str, ttl_seconds: int) -> None:
    """Add a JWT to the refresh-token blacklist."""
    try:
        r = get_redis()
        r.setex(f"blacklist:{token}", ttl_seconds, "1")
    except Exception as exc:
        logger.warning("Redis blacklist write failed: %s", exc)


def is_blacklisted(token: str) -> bool:
    """Return True if the token is in the Redis blacklist."""
    try:
        r = get_redis()
        return r.exists(f"blacklist:{token}") == 1
    except Exception as exc:
        logger.warning("Redis blacklist check failed: %s", exc)
        return False
