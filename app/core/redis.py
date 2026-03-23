from redis.asyncio import Redis

from app.core.config import settings

redis_client: Redis | None = None


async def get_redis() -> Redis:
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


async def acquire_lock(key: str, ttl: int = 30) -> bool:
    """Adquiere lock atomico (SET NX EX). True si se adquirio, False si ya existia."""
    r = await get_redis()
    result = await r.set(key, "1", nx=True, ex=ttl)
    return result is True


async def release_lock(key: str) -> None:
    """Libera un lock."""
    r = await get_redis()
    await r.delete(key)


async def check_rate_limit(key: str, limit: int = 10, window: int = 60) -> bool:
    """True si el numero de llamadas en la ventana supera el limite (INCR+EXPIRE)."""
    r = await get_redis()
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window)
    return count > limit
