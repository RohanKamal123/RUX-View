"""Tests for performance optimization modules: cache_manager, rate_limiter, query_optimizer."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.cache_manager import (
    LRUCache,
    CacheManager,
    RateLimiter,
    QueryOptimizer,
    CacheEntry,
)


@pytest.fixture
def lru_cache():
    return LRUCache(max_size_mb=1, default_ttl_seconds=60)


@pytest.fixture
def cache_manager():
    return CacheManager(redis_client=None)


@pytest.fixture
def rate_limiter():
    return RateLimiter(redis_client=None)


@pytest.fixture
def query_optimizer():
    mock_session_factory = MagicMock()
    return QueryOptimizer(db_session_factory=mock_session_factory)


class TestLRUCache:
    """Tests for LRUCache class."""

    @pytest.mark.asyncio
    async def test_lru_cache_hit_returns_value(self, lru_cache):
        """Test that a cache hit returns the stored value."""
        await lru_cache.set("test_key", "test_value")
        result = await lru_cache.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_lru_cache_miss_returns_none(self, lru_cache):
        """Test that a cache miss returns None."""
        result = await lru_cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_cache_evicts_oldest_when_full(self):
        """Test that oldest entries are evicted when cache exceeds max size."""
        cache = LRUCache(max_size_mb=0.001, default_ttl_seconds=300)  # Very small cache
        # Add entries until eviction occurs
        for i in range(100):
            await cache.set(f"key_{i}", "x" * 1000)

        stats = await cache.get_stats()
        assert stats["entries"] < 100  # Some entries should have been evicted

    @pytest.mark.asyncio
    async def test_cache_ttl_expires_entries(self, lru_cache):
        """Test that TTL expiration removes entries."""
        await lru_cache.set("expire_key", "value", ttl_seconds=0)  # Immediate expiry
        await asyncio.sleep(0.1)
        result = await lru_cache.get("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete_removes_entry(self, lru_cache):
        """Test that delete removes a cache entry."""
        await lru_cache.set("delete_key", "value")
        deleted = await lru_cache.delete("delete_key")
        assert deleted is True
        result = await lru_cache.get("delete_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear_removes_all(self, lru_cache):
        """Test that clear removes all entries."""
        await lru_cache.set("key1", "val1")
        await lru_cache.set("key2", "val2")
        await lru_cache.clear()
        stats = await lru_cache.get_stats()
        assert stats["entries"] == 0

    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self, lru_cache):
        """Test that cache statistics are tracked correctly."""
        await lru_cache.set("stat_key", "value")
        await lru_cache.get("stat_key")  # Hit
        await lru_cache.get("stat_key")  # Hit
        await lru_cache.get("missing")   # Miss

        stats = await lru_cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_ratio"] > 0


class TestCacheManager:
    """Tests for CacheManager class."""

    @pytest.mark.asyncio
    async def test_cache_manager_compute_on_miss(self, cache_manager):
        """Test that compute function is called on cache miss."""
        compute_called = False

        async def compute_func():
            nonlocal compute_called
            compute_called = True
            return "computed_value"

        result = await cache_manager.get_cached_or_compute(
            "compute_key", compute_func, ttl_seconds=60
        )
        assert result == "computed_value"
        assert compute_called is True

    @pytest.mark.asyncio
    async def test_cache_manager_returns_cached_value(self, cache_manager):
        """Test that cached value is returned without recomputing."""
        compute_count = 0

        async def compute_func():
            nonlocal compute_count
            compute_count += 1
            return f"computed_{compute_count}"

        # First call - should compute
        result1 = await cache_manager.get_cached_or_compute(
            "cached_key", compute_func, ttl_seconds=60
        )
        assert result1 == "computed_1"

        # Second call - should use cache
        result2 = await cache_manager.get_cached_or_compute(
            "cached_key", compute_func, ttl_seconds=60
        )
        assert result2 == "computed_1"  # Still the cached value
        assert compute_count == 1  # compute_func was only called once

    @pytest.mark.asyncio
    async def test_cache_warm_for_new_user(self, cache_manager):
        """Test cache warming for a new user."""
        result = await cache_manager.warm_cache("user_new")
        assert isinstance(result, dict)
        assert "camera_count" in result
        assert "event_count" in result
        assert "person_count" in result

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache_manager):
        """Test pattern-based cache invalidation."""
        await cache_manager._local_cache.set("events:user:1:page1", "data1")
        await cache_manager._local_cache.set("events:user:1:page2", "data2")
        await cache_manager._local_cache.set("cameras:user:1", "data3")

        count = await cache_manager.invalidate_pattern("events:user:*")
        assert count == 2  # Two event entries should be invalidated


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self, rate_limiter):
        """Test that requests within limit are allowed."""
        result = await rate_limiter.check_rate_limit(
            "test_user:api", max_requests=5, window_seconds=60
        )
        assert result["allowed"] is True
        assert result["remaining"] == 4

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess(self, rate_limiter):
        """Test that requests exceeding limit are blocked."""
        key = "test_user:excess"
        max_req = 3

        for i in range(max_req):
            result = await rate_limiter.check_rate_limit(
                key, max_requests=max_req, window_seconds=60
            )
            assert result["allowed"] is True

        # This request should be blocked
        result = await rate_limiter.check_rate_limit(
            key, max_requests=max_req, window_seconds=60
        )
        assert result["allowed"] is False
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self, rate_limiter):
        """Test that rate limit resets after window expires."""
        key = "test_user:reset"
        max_req = 2

        # Use up all requests
        for i in range(max_req):
            await rate_limiter.check_rate_limit(key, max_requests=max_req, window_seconds=0)

        # With 0-second window, the next request should be allowed
        # (since the window has already passed)
        result = await rate_limiter.check_rate_limit(key, max_requests=max_req, window_seconds=0)
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_rate_limiter_usage_tracking(self, rate_limiter):
        """Test that usage tracking returns correct data."""
        key = "test_user:usage"
        await rate_limiter.check_rate_limit(key, max_requests=10, window_seconds=60)

        usage = await rate_limiter.get_usage(key)
        assert usage["current_count"] >= 1
        assert usage["max_allowed"] == 60
        assert usage["window_seconds"] == 60


class TestQueryOptimizer:
    """Tests for QueryOptimizer class."""

    @pytest.mark.asyncio
    async def test_query_optimizer_adds_pagination(self, query_optimizer):
        """Test that pagination is added to queries."""
        query = "SELECT * FROM events WHERE user_id = '123'"
        paginated = query_optimizer._add_pagination(query, limit=20, offset=0)
        assert "LIMIT 20" in paginated
        assert "OFFSET 0" in paginated

    @pytest.mark.asyncio
    async def test_query_optimizer_builds_filtered_query(self, query_optimizer):
        """Test that filtered queries are built correctly."""
        filters = {
            "camera_id": "cam_123",
            "threat_level": "HIGH",
            "start_time": "2024-01-01",
        }
        query, params = await query_optimizer.get_optimized_event_query(
            user_id="user_123", filters=filters
        )
        assert "user_id" in params
        assert params["user_id"] == "user_123"
        assert params["camera_id"] == "cam_123"
        assert params["threat_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_materialized_view_refresh(self, query_optimizer):
        """Test materialized view refresh."""
        # Mock the session
        mock_session = AsyncMock()
        query_optimizer.db_session_factory.return_value.__aenter__.return_value = mock_session

        result = await query_optimizer.refresh_materialized_views()
        assert isinstance(result, dict)
        assert "views_refreshed" in result
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_query_optimizer_adds_index_hint(self, query_optimizer):
        """Test that index hints are added to queries."""
        query = "SELECT * FROM events WHERE camera_id = 'cam1' AND threat_level = 'HIGH'"
        hinted = query_optimizer._add_index_hint(
            query, "events", ["camera_id", "threat_level"]
        )
        assert "USE INDEX" in hinted
        assert "idx_events_camera_id_threat_level" in hinted


import asyncio
