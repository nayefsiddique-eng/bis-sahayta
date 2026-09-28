"""
Cache service with Redis backend and in-memory fallback.
If Redis is unavailable the service silently degrades to the existing
in-memory cache so that tests and development environments never require Redis.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback (existing app/core/cache.py behaviour)
# ---------------------------------------------------------------------------

class _InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:  # ttl ignored in-memory
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def backend(self) -> str:
        return "memory"


# ---------------------------------------------------------------------------
# Redis-backed cache
# ---------------------------------------------------------------------------

class _RedisCache:
    def __init__(self, redis_url: str) -> None:
        import redis as redis_lib  # type: ignore
        self._client = redis_lib.from_url(redis_url, decode_responses=True)
        self._client.ping()  # raises if Redis is down
        logger.info(f"RedisCache connected to {redis_url}")

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.warning(f"RedisCache.get error: {exc}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning(f"RedisCache.set error: {exc}")

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception as exc:
            logger.warning(f"RedisCache.delete error: {exc}")

    def clear(self) -> None:
        try:
            self._client.flushdb()
        except Exception as exc:
            logger.warning(f"RedisCache.clear error: {exc}")

    @property
    def backend(self) -> str:
        return "redis"


# ---------------------------------------------------------------------------
# Public cache service singleton
# ---------------------------------------------------------------------------

_cache_backend: Optional[Any] = None


def _build_cache() -> Any:
    try:
        return _RedisCache(settings.REDIS_URL)
    except Exception as exc:
        logger.warning(
            f"Redis unavailable ({exc}), falling back to in-memory cache. "
            "Set REDIS_URL in .env to enable Redis."
        )
        return _InMemoryCache()


def get_cache() -> Any:
    """Return the shared cache singleton (Redis or in-memory)."""
    global _cache_backend
    if _cache_backend is None:
        _cache_backend = _build_cache()
    return _cache_backend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cache_key(*parts: Any, prefix: str = "bis") -> str:
    """Build a deterministic cache key from arbitrary parts."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


async def cached(
    key: str,
    compute,
    ttl: int = None,
) -> Any:
    """
    Generic cache-aside helper.

    Usage:
        result = await cached("my-key", lambda: expensive_call(), ttl=60)
    """
    cache = get_cache()
    hit = cache.get(key)
    if hit is not None:
        logger.debug(f"Cache HIT: {key}")
        return hit

    logger.debug(f"Cache MISS: {key}")
    result = await compute() if asyncio_is_coroutine(compute) else compute()
    cache.set(key, result, ttl=ttl or settings.CACHE_TTL_SECONDS)
    return result


def asyncio_is_coroutine(fn) -> bool:
    import inspect
    return inspect.iscoroutinefunction(fn)
