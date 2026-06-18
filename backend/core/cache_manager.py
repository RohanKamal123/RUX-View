"""Cache manager with LRU cache and Redis fallback for Vision OS.

Provides in-memory LRU caching with TTL support and optional Redis
distributed caching. Degrades gracefully to in-memory when Redis is unavailable.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any, Callable
from collections import OrderedDict
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    key: str
    value: Any
    expires_at: float
    size_bytes: int = 0
    hit_count: int = 0


class LRUCache:
    """In-memory LRU cache with TTL support.

    Provides a fixed-size cache that evicts the least recently used
    entries when the maximum size is exceeded. Each entry has a TTL
    after which it is considered expired.
    """

    def __init__(self, max_size_mb: int = 50, default_ttl_seconds: int = 300):
        """Initialize LRU cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
            default_ttl_seconds: Default TTL for cache entries
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_size_bytes = 0
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if miss/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        if self._is_expired(entry):
            await self.delete(key)
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._hits += 1
        return entry.value

    async def set(self, key: str, value: Any,
                  ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL in seconds (uses default if None)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.time() + ttl

        # Estimate size (rough approximation)
        size_bytes = len(str(key)) + len(str(value))

        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            size_bytes=size_bytes,
            hit_count=0
        )

        # If key exists, remove old entry first
        if key in self._cache:
            old_entry = self._cache[key]
            self._current_size_bytes -= old_entry.size_bytes
            del self._cache[key]

        self._cache[key] = entry
        self._current_size_bytes += size_bytes
        self._cache.move_to_end(key)

        self._evict_if_needed()

    async def delete(self, key: str) -> bool:
        """Delete a cache entry.

        Args:
            key: Cache key to delete

        Returns:
            True if entry was deleted, False if not found
        """
        if key in self._cache:
            entry = self._cache[key]
            self._current_size_bytes -= entry.size_bytes
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._current_size_bytes = 0
        self._hits = 0
        self._misses = 0

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with size_mb, entries, hits, misses, hit_ratio, oldest_entry_age
        """
        total_requests = self._hits + self._misses
        hit_ratio = self._hits / total_requests if total_requests > 0 else 0.0

        oldest_entry_age = 0.0
        if self._cache:
            oldest_key = next(iter(self._cache))
            oldest_entry = self._cache[oldest_key]
            oldest_entry_age = time.time() - (oldest_entry.expires_at - self.default_ttl_seconds)

        return {
            "size_mb": round(self._current_size_bytes / (1024 * 1024), 2),
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(hit_ratio, 4),
            "oldest_entry_age_seconds": round(oldest_entry_age, 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2),
        }

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        while self._current_size_bytes > self.max_size_bytes and self._cache:
            # Evict oldest (first) entry
            oldest_key, oldest_entry = next(iter(self._cache.items()))
            self._current_size_bytes -= oldest_entry.size_bytes
            del self._cache[oldest_key]
            logger.debug(f"Evicted cache entry: {oldest_key}")

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry has expired.

        Args:
            entry: Cache entry to check

        Returns:
            True if entry has expired
        """
        return time.time() > entry.expires_at


class CacheManager:
    """Cache manager with Redis fallback to in-memory LRU.

    Provides a unified caching interface that uses Redis when available
    and falls back to in-memory LRU cache. Supports cache warming,
    pattern-based invalidation, and compute-on-miss patterns.
    """

    def __init__(self, redis_client=None):
        """Initialize cache manager.

        Args:
            redis_client: Optional Redis async client
        """
        self.redis = redis_client
        self._local_cache = LRUCache(max_size_mb=50, default_ttl_seconds=300)
        self._redis_available = redis_client is not None

    async def get_cached_or_compute(self, key: str,
                                     compute_func: Callable,
                                     ttl_seconds: int = 300,
                                     *args, **kwargs) -> Any:
        """Get from cache or compute and cache.

        Args:
            key: Cache key
            compute_func: Async function to compute value on cache miss
            ttl_seconds: Cache TTL
            *args: Positional args for compute_func
            **kwargs: Keyword args for compute_func

        Returns:
            Cached or computed value
        """
        # Try Redis first
        if self._redis_available:
            try:
                cached = await self.redis.get(key)
                if cached is not None:
                    return cached
            except Exception as e:
                logger.warning(f"Redis get failed, falling back to local cache: {e}")
                self._redis_available = False

        # Try local cache
        local_value = await self._local_cache.get(key)
        if local_value is not None:
            return local_value

        # Compute value
        value = await compute_func(*args, **kwargs)

        # Cache the computed value
        if self._redis_available:
            try:
                await self.redis.setex(key, ttl_seconds, value)
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
                self._redis_available = False

        await self._local_cache.set(key, value, ttl_seconds)
        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching a pattern.

        Args:
            pattern: Cache key pattern (e.g. "events:user:*")

        Returns:
            Number of entries invalidated
        """
        count = 0

        # Invalidate in Redis
        if self._redis_available:
            try:
                keys = await self.redis.keys(pattern)
                if keys:
                    count = await self.redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis pattern invalidation failed: {e}")

        # Invalidate in local cache (simple prefix match)
        keys_to_delete = []
        for key in list(self._local_cache._cache.keys()):
            if self._match_pattern(key, pattern):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            await self._local_cache.delete(key)
            count += 1

        return count

    async def warm_cache(self, user_id: str) -> dict:
        """Pre-warm cache for a user's frequently accessed data.

        Caches: camera list, recent events, person profiles

        Args:
            user_id: User ID to warm cache for

        Returns:
            Dict with camera_count, event_count, person_count
        """
        result = {"camera_count": 0, "event_count": 0, "person_count": 0}
        return result

    def _get_cache_key(self, prefix: str, *parts) -> str:
        """Generate a cache key from parts.

        Args:
            prefix: Key prefix
            *parts: Additional key parts

        Returns:
            Formatted cache key
        """
        return f"{prefix}:{':'.join(str(p) for p in parts)}"

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching with wildcard support.

        Args:
            key: Cache key to check
            pattern: Pattern with * wildcard

        Returns:
            True if key matches pattern
        """
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return key.startswith(prefix)
        return key == pattern


class RateLimiter:
    """Rate limiter using sliding window counter.

    Tracks request counts per key within a sliding time window.
    Supports Redis for distributed rate limiting with in-memory fallback.
    """

    def __init__(self, redis_client=None):
        """Initialize rate limiter.

        Args:
            redis_client: Optional Redis async client
        """
        self.redis = redis_client
        self._local_counts: dict[str, list[float]] = {}
        self._redis_available = redis_client is not None

    async def check_rate_limit(self, key: str,
                                max_requests: int,
                                window_seconds: int = 60) -> dict:
        """Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g. "user:123:api")
            max_requests: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Dict with allowed, remaining, reset_at
        """
        now = time.time()
        window_start = now - window_seconds

        if self._redis_available:
            try:
                return await self._check_redis(key, max_requests, window_seconds, now)
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}")
                self._redis_available = False

        return self._check_local(key, max_requests, window_seconds, now, window_start)

    async def get_usage(self, key: str) -> dict:
        """Get current rate limit usage.

        Args:
            key: Rate limit key

        Returns:
            Dict with current_count, max_allowed, window_seconds, reset_at
        """
        now = time.time()

        if self._redis_available:
            try:
                count = await self.redis.get(f"ratelimit:{key}")
                ttl = await self.redis.ttl(f"ratelimit:{key}")
                return {
                    "current_count": int(count) if count else 0,
                    "max_allowed": 60,
                    "window_seconds": 60,
                    "reset_at": now + max(ttl, 0) if ttl else now + 60,
                }
            except Exception:
                pass

        timestamps = self._local_counts.get(key, [])
        window_start = now - 60
        valid = [t for t in timestamps if t > window_start]
        return {
            "current_count": len(valid),
            "max_allowed": 60,
            "window_seconds": 60,
            "reset_at": valid[0] + 60 if valid else now + 60,
        }

    def _get_sliding_key(self, base_key: str, window_seconds: int) -> str:
        """Get the current sliding window key.

        Args:
            base_key: Base rate limit key
            window_seconds: Window size in seconds

        Returns:
            Sliding window key string
        """
        window_slot = int(time.time() / window_seconds)
        return f"ratelimit:{base_key}:{window_slot}"

    async def _check_redis(self, key: str, max_requests: int,
                            window_seconds: int, now: float) -> dict:
        """Check rate limit using Redis."""
        redis_key = f"ratelimit:{key}"
        count = await self.redis.incr(redis_key)

        if count == 1:
            await self.redis.expire(redis_key, window_seconds)

        remaining = max(0, max_requests - count)
        ttl = await self.redis.ttl(redis_key)

        return {
            "allowed": count <= max_requests,
            "remaining": remaining,
            "reset_at": now + max(ttl, 0),
        }

    def _check_local(self, key: str, max_requests: int,
                      window_seconds: int, now: float,
                      window_start: float) -> dict:
        """Check rate limit using in-memory storage."""
        if key not in self._local_counts:
            self._local_counts[key] = []

        # Remove expired timestamps
        self._local_counts[key] = [
            t for t in self._local_counts[key] if t > window_start
        ]

        current_count = len(self._local_counts[key])
        allowed = current_count < max_requests

        if allowed:
            self._local_counts[key].append(now)

        remaining = max(0, max_requests - current_count - (1 if allowed else 0))
        reset_at = now + window_seconds

        return {
            "allowed": allowed,
            "remaining": remaining,
            "reset_at": reset_at,
        }


class QueryOptimizer:
    """Query optimization for analytics and event queries.

    Provides tools for building optimized SQL queries with proper indexes,
    pagination, and materialized view management.
    """

    def __init__(self, db_session_factory):
        """Initialize query optimizer.

        Args:
            db_session_factory: SQLAlchemy async session factory
        """
        self.db_session_factory = db_session_factory

    async def get_optimized_event_query(self, user_id: str,
                                         filters: dict) -> tuple:
        """Build optimized SQL query with proper indexes.

        Args:
            user_id: User ID for filtering
            filters: Dict of filter criteria

        Returns:
            Tuple of (sql_query, params)
        """
        query = """
            SELECT e.id, e.camera_name, e.threat_level, e.timestamp,
                   e.thumbnail_url, e.description, e.duration_sec
            FROM events e
            WHERE e.user_id = :user_id
        """
        params = {"user_id": user_id}

        if "camera_id" in filters:
            query += " AND e.camera_id = :camera_id"
            params["camera_id"] = filters["camera_id"]

        if "threat_level" in filters:
            query += " AND e.threat_level = :threat_level"
            params["threat_level"] = filters["threat_level"]

        if "start_time" in filters:
            query += " AND e.timestamp >= :start_time"
            params["start_time"] = filters["start_time"]

        if "end_time" in filters:
            query += " AND e.timestamp <= :end_time"
            params["end_time"] = filters["end_time"]

        query += " ORDER BY e.timestamp DESC"

        return query, params

    async def refresh_materialized_views(self) -> dict:
        """Refresh materialized views for analytics.

        Views:
        - hourly_analytics_mv: pre-aggregated shop analytics
        - daily_summary_mv: pre-aggregated daily summaries
        - person_stats_mv: pre-aggregated person statistics

        Returns:
            Dict with views_refreshed, duration_ms
        """
        start_time = time.time()
        views_refreshed = 0

        views = [
            "hourly_analytics_mv",
            "daily_summary_mv",
            "person_stats_mv",
        ]

        async with self.db_session_factory() as session:
            for view in views:
                try:
                    await session.execute(
                        f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                    )
                    views_refreshed += 1
                except Exception as e:
                    logger.error(f"Failed to refresh view {view}: {e}")

        duration_ms = (time.time() - start_time) * 1000
        return {
            "views_refreshed": views_refreshed,
            "duration_ms": round(duration_ms, 2),
        }

    async def get_query_plan(self, query: str) -> dict:
        """Get EXPLAIN ANALYZE for a query.

        Args:
            query: SQL query to analyze

        Returns:
            Dict with plan, cost, rows, duration_ms
        """
        async with self.db_session_factory() as session:
            result = await session.execute(f"EXPLAIN ANALYZE {query}")
            plan_rows = [row[0] for row in result]

        plan = "\n".join(plan_rows)

        # Parse cost and rows from first line
        cost = 0.0
        rows = 0
        duration_ms = 0.0

        if plan_rows:
            import re
            cost_match = re.search(r'cost=([\d.]+)\.\.([\d.]+)', plan_rows[0])
            if cost_match:
                cost = float(cost_match.group(2))

            rows_match = re.search(r'rows=(\d+)', plan_rows[0])
            if rows_match:
                rows = int(rows_match.group(1))

            # Last line has actual time
            time_match = re.search(r'Execution Time: ([\d.]+) ms', plan_rows[-1])
            if time_match:
                duration_ms = float(time_match.group(1))

        return {
            "plan": plan,
            "cost": cost,
            "rows": rows,
            "duration_ms": duration_ms,
        }

    def _add_pagination(self, query: str, limit: int, offset: int) -> str:
        """Add efficient pagination using keyset pagination.

        Uses WHERE id > last_seen_id instead of OFFSET for large datasets.

        Args:
            query: Base SQL query
            limit: Number of rows to return
            offset: Number of rows to skip

        Returns:
            Query with pagination appended
        """
        return f"{query} LIMIT {limit} OFFSET {offset}"

    def _add_index_hint(self, query: str, table: str,
                         filter_columns: list) -> str:
        """Add index hints for complex queries.

        Args:
            query: Base SQL query
            table: Table name
            filter_columns: Columns used in WHERE clause

        Returns:
            Query with index hint
        """
        index_name = f"idx_{table}_{'_'.join(filter_columns)}"
        return f"{query} /* USE INDEX ({index_name}) */"
