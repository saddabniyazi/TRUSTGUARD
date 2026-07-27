import redis

from app.core.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """
    Shared Redis connection, used by both the rate limiter and the
    agent-response cache. `decode_responses=True` so callers get str
    back instead of bytes — every value this project stores in Redis
    is either a plain int (rate-limit counters) or a JSON string
    (cached verdicts), never binary data.
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client
