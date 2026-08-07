"""
redis_client.py — Upstash Redis REST client wrapper.

Provides a singleton ``RedisRESTClient`` (and a ``get_redis_client``
factory function) that other backend modules import to talk to Redis.

Uses Upstash Redis REST API (no persistent TCP connection) for
Cloud Run compatibility — all operations are async and stateless.
"""

import json
import logging
from typing import Optional

from upstash_redis.asyncio import Redis as UpstashRedis
from backend.config import settings

logger = logging.getLogger(__name__)

_redis_instance: Optional[UpstashRedis] = None


async def get_redis_client() -> UpstashRedis:
    """Return a singleton Upstash async Redis client.

    Creates the client on first call; reuses it thereafter.
    Uses the REST URL and token from application settings.
    """
    global _redis_instance
    if _redis_instance is None:
        logger.info("Creating Upstash Redis client")
        _redis_instance = UpstashRedis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )
    return _redis_instance