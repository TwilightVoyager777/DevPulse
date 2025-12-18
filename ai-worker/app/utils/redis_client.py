import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
_redis: Optional[aioredis.Redis] = None


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


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def cache_task_status(task_id: str, status_json: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"task:{task_id}", status_json, ex=ttl)


async def mark_event_processed(task_id: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"processed:event:{task_id}", "1", ex=ttl)


async def is_event_processed(task_id: str) -> bool:
    r = await get_redis()
    return await r.exists(f"processed:event:{task_id}") == 1
