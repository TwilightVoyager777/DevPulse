import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

# String-decoded client for general use
_redis: Optional[aioredis.Redis] = None
# Binary client for pickle data (BM25 indexes)
_raw_redis: Optional[aioredis.Redis] = None

_BM25_TTL = 86_400  # 24 hours


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        await _redis.ping()
        logger.info("Redis connected")
    return _redis


async def get_raw_redis() -> aioredis.Redis:
    """Binary Redis client (decode_responses=False) for storing pickle data."""
    global _raw_redis
    if _raw_redis is None:
        settings = get_settings()
        _raw_redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=False,
        )
    return _raw_redis


async def close_redis() -> None:
    global _redis, _raw_redis
    if _redis:
        await _redis.aclose()
        _redis = None
    if _raw_redis:
        await _raw_redis.aclose()
        _raw_redis = None


async def cache_task_status(task_id: str, status_json: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"task:{task_id}", status_json, ex=ttl)


async def mark_event_processed(task_id: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"processed:event:{task_id}", "1", ex=ttl)


async def is_event_processed(task_id: str) -> bool:
    r = await get_redis()
    return await r.exists(f"processed:event:{task_id}") == 1


async def save_bm25_to_redis(workspace_id: str, data: bytes) -> None:
    """Persist BM25 pickle bytes to Redis with 24h TTL."""
    r = await get_raw_redis()
    await r.set(f"bm25:{workspace_id}", data, ex=_BM25_TTL)


async def load_bm25_from_redis(workspace_id: str) -> Optional[bytes]:
    """Load BM25 pickle bytes from Redis. Returns None on miss."""
    r = await get_raw_redis()
    return await r.get(f"bm25:{workspace_id}")


async def acquire_bm25_lock(workspace_id: str, ttl: int = 60) -> bool:
    """Try to acquire the BM25 rebuild distributed lock (SET NX). Returns True if acquired."""
    r = await get_redis()
    result = await r.set(f"bm25:lock:{workspace_id}", "1", nx=True, ex=ttl)
    return result is True


async def release_bm25_lock(workspace_id: str) -> None:
    """Release the BM25 rebuild distributed lock."""
    r = await get_redis()
    await r.delete(f"bm25:lock:{workspace_id}")
