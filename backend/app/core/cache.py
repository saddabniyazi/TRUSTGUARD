"""
Caches agent verdicts by a hash of their exact inputs, so an identical
moderation call doesn't re-spend free-tier Gemini quota.

WHY CONTENT-ADDRESSED, NOT ITEM-ID-ADDRESSED: caching by listing_id or
review_id would mean re-moderating the SAME id always hits the cache,
even after the content or the active policy rules changed — silently
wrong. Keying by a hash of the actual inputs (content text, plus
whatever else affects the verdict — active rules for Policy, reviewer
velocity for Fraud) means the cache is correct by construction: it can
only ever return a verdict that was actually computed for these exact
inputs. Two different listings with coincidentally identical
descriptions correctly share a cache entry; the same listing re-
moderated after an edit or a rule change correctly misses.

FAIL OPEN, SAME AS RATE LIMITING: a cache read/write failure calls the
real agent instead of raising. Caching is a cost optimization, not a
correctness requirement — losing it should degrade performance, not
availability.
"""

import hashlib
import json
import logging

from pydantic import BaseModel
from redis.exceptions import RedisError

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# 1 hour: long enough to absorb accidental double-clicks or a quick
# re-moderation retry after a transient failure, short enough that a
# policy rule change or content edit is reflected well within the same
# working session rather than being masked for days.
CACHE_TTL_SECONDS = 3600


def _cache_key(agent_name: str, *parts: str) -> str:
    payload = "|".join([agent_name, *parts])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"agent_cache:{agent_name}:{digest}"


def get_cached(agent_name: str, schema: type[BaseModel], *key_parts: str) -> BaseModel | None:
    """Returns a validated instance of `schema` if cached, else None (including on any Redis error)."""
    try:
        client = get_redis()
        raw = client.get(_cache_key(agent_name, *key_parts))
    except RedisError:
        logger.warning("Cache read failed for agent=%s — calling the agent instead", agent_name)
        return None
    if raw is None:
        return None
    try:
        return schema.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        # Corrupt or stale-format cache entry — treat as a miss rather
        # than crash the request over a caching optimization.
        return None


def set_cached(agent_name: str, verdict: BaseModel, *key_parts: str) -> None:
    try:
        client = get_redis()
        client.setex(_cache_key(agent_name, *key_parts), CACHE_TTL_SECONDS, verdict.model_dump_json())
    except RedisError:
        logger.warning("Cache write failed for agent=%s — verdict computed but not cached", agent_name)
