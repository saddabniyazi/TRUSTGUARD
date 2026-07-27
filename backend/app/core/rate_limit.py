"""
Fixed-window rate limiting, backed by Redis, applied as a FastAPI
dependency.

WHY THIS EXISTS: the free-tier Gemini quota is the single biggest
operational risk in this project (see the Day 4 rate-limit incident in
the README) — a handful of requests in quick succession from one
client can exhaust it for everyone. Rate limiting the endpoints that
trigger LLM calls (`/api/moderate/*`) protects the shared quota from
one client hammering it; rate limiting ingestion (`/api/listings`,
`/api/reviews`) protects against basic spam submission.

ALGORITHM: fixed-window counter, not a sliding window or token bucket.
`INCR` a Redis key namespaced by (route, client identifier), and set
its expiry only the first time it's created in a window. This is the
simplest correct rate limiter Redis supports natively (single atomic
INCR, no Lua script needed) — it allows a burst right at a window
boundary that a sliding window wouldn't, which is an acceptable
tradeoff for a portfolio project's actual risk (free-tier quota
protection), not a production billing-critical system.

IDENTIFIER: client IP, not user ID. Some rate-limited endpoints
(`POST /api/listings`, `POST /api/reviews`) are deliberately
unauthenticated (Day 2 — they simulate a marketplace backend calling
in), so there's no user to key on. Keying everything on IP keeps the
limiter uniform across authenticated and unauthenticated endpoints
instead of two different identification schemes.

FAIL OPEN: if Redis itself is unreachable, requests are allowed
through rather than blocked. A rate limiter's backing store being down
shouldn't take down the whole API — availability of the actual feature
matters more than perfect enforcement of a quota-protection mechanism.
"""

import logging

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


def _client_identifier(request: Request) -> str:
    if request.client is not None:
        return request.client.host
    return "unknown"


def rate_limiter(key_prefix: str, limit: int, window_seconds: int):
    """
    Returns a FastAPI dependency enforcing `limit` requests per
    `window_seconds` per client IP, namespaced under `key_prefix` so
    different endpoints don't share a counter.

    Usage: `Depends(rate_limiter("moderate", limit=5, window_seconds=60))`
    """

    def dependency(request: Request) -> None:
        identifier = _client_identifier(request)
        redis_key = f"ratelimit:{key_prefix}:{identifier}"

        try:
            client = get_redis()
            current = client.incr(redis_key)
            if current == 1:
                client.expire(redis_key, window_seconds)
            ttl = client.ttl(redis_key) if current > limit else None
        except RedisError:
            logger.warning("Rate limiter could not reach Redis — failing open for %s", redis_key)
            return

        if current > limit:
            retry_after = ttl if ttl and ttl > 0 else window_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests / {window_seconds}s). Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
