"""
Vision OS — Unit Tests for Database Connection Pool Module (Sprint 10.3)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from dataclasses import dataclass

from backend.storage.connection_pool import (
    ConnectionPoolManager,
    PoolConfig,
    PoolStats,
    ReadReplicaConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pool_config():
    return PoolConfig(
        database_url="postgresql://user:pass@localhost:5432/visionos",
        min_size=2,
        max_size=10,
        max_queries=50000,
        max_inactive_connection_lifetime=300.0,
        command_timeout=30,
        statement_cache_size=100,
        ssl="require",
    )


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    pool.get_idle_size = MagicMock(return_value=5)
    pool.get_size = MagicMock(return_value=8)
    return pool


@pytest.fixture
def manager(pool_config):
    return ConnectionPoolManager(config=pool_config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_pool_creates_connections(manager, mock_pool):
    """initialize_pool should create a pool and start health checks."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        pool = await manager.initialize_pool()

    assert pool is mock_pool
    assert manager._pool is mock_pool
    assert manager._running is True


@pytest.mark.asyncio
async def test_get_connection_returns_valid_conn(manager, mock_pool):
    """get_connection should acquire a connection from the pool."""
    mock_conn = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    conn = await manager.get_connection()
    assert conn is mock_conn


@pytest.mark.asyncio
async def test_release_connection_returns_to_pool(manager, mock_pool):
    """release_connection should return the connection to the pool."""
    mock_conn = AsyncMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    conn = await manager.get_connection()
    await manager.release_connection(conn)
    mock_pool.release.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_get_pool_stats_returns_metrics(manager, mock_pool):
    """get_pool_stats should return a PoolStats instance with data."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    stats = manager.get_pool_stats()

    assert isinstance(stats, PoolStats)
    assert stats.max_connections == 10
    assert stats.total_connections == 8  # get_size() returns 8
    assert stats.idle_connections == 5   # get_idle_size() returns 5
    # active = total - idle = 8 - 5 = 3
    assert stats.active_connections == 3


@pytest.mark.asyncio
async def test_health_check_returns_true(manager, mock_pool):
    """health_check should succeed when SELECT 1 returns 1."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    result = await manager.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_reset_pool_recreates_connections(manager, mock_pool):
    """reset_pool should close the old pool and create a new one."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    new_mock_pool = AsyncMock()
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=new_mock_pool):
        result = await manager.reset_pool()

    assert result["status"] == "ok"
    assert result["action"] == "pool_reset"
    assert manager._pool is new_mock_pool


@pytest.mark.asyncio
async def test_close_pool_cleans_up(manager, mock_pool):
    """close_pool should close the pool and cancel health checks."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    result = await manager.close_pool()

    assert result["status"] == "ok"
    assert result["action"] == "pool_closed"
    assert manager._pool is None
    assert manager._running is False
    mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_with_retry_succeeds(manager, mock_pool):
    """execute_with_retry should return query results on success."""
    mock_conn = AsyncMock()
    expected_result = [{"id": 1}]
    mock_conn.fetch = AsyncMock(return_value=expected_result)
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    result = await manager.execute_with_retry("SELECT 1", ())
    assert result == expected_result


@pytest.mark.asyncio
async def test_execute_with_retry_fails_after_max(manager, mock_pool):
    """execute_with_retry should raise after exhausting retries."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=Exception("DB down"))
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    with pytest.raises(RuntimeError, match="Query failed after 3 retries"):
        await manager.execute_with_retry("SELECT 1", (), max_retries=3)


@pytest.mark.asyncio
async def test_execute_in_transaction_commits(manager, mock_pool):
    """execute_in_transaction should commit all queries."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[{"ok": True}])
    mock_conn.transaction = AsyncMock()

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_conn.transaction.return_value = FakeTransaction()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    queries = [
        ("UPDATE users SET name = $1 WHERE id = $2", ("Alice", 1)),
        ("INSERT INTO logs (action) VALUES ($1)", ("update",)),
    ]

    results = await manager.execute_in_transaction(queries)
    assert len(results) == 2
    assert mock_conn.fetch.call_count == 2


@pytest.mark.asyncio
async def test_execute_in_transaction_rolls_back_on_error(manager, mock_pool):
    """execute_in_transaction should roll back on error."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(
        side_effect=[Exception("Query failed")]
    )
    mock_conn.transaction = AsyncMock()

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            if args[0] is not None:
                raise args[1]

    mock_conn.transaction.return_value = FakeTransaction()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    queries = [("SELECT 1", ())]

    with pytest.raises(Exception, match="Query failed"):
        await manager.execute_in_transaction(queries)


@pytest.mark.asyncio
async def test_pool_utilization_calculation(manager, mock_pool):
    """get_pool_stats should calculate pool utilization correctly."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    stats = manager.get_pool_stats()
    # active=3, max=10 => 30%
    assert stats.pool_utilization_pct == 30.0


@pytest.mark.asyncio
async def test_connection_timeout_enforced(manager, mock_pool):
    """execute_with_retry should eventually raise on timeout."""
    manager.config.command_timeout = 1

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=__import__("asyncio").TimeoutError("timeout"))
    mock_pool.acquire = AsyncMock(return_value=mock_conn)

    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
        await manager.initialize_pool()

    with pytest.raises(RuntimeError, match="Query failed after 3 retries"):
        await manager.execute_with_retry("SELECT pg_sleep(10)", (), max_retries=3)


@pytest.mark.asyncio
async def test_get_connection_raises_if_not_initialized(manager):
    """get_connection should raise RuntimeError if pool not initialised."""
    with pytest.raises(RuntimeError, match="not initialised"):
        await manager.get_connection()


@pytest.mark.asyncio
async def test_initialize_pool_with_replica(pool_config):
    """Initialize pool with read-replica should create both pools."""
    replica_config = ReadReplicaConfig(
        enabled=True,
        replica_url="postgresql://user:pass@replica:5432/visionos",
    )
    manager = ConnectionPoolManager(config=pool_config, replica_config=replica_config)

    mock_main = AsyncMock()
    mock_replica = AsyncMock()

    def create_pool_side_effect(dsn, **kwargs):
        if "replica" in dsn:
            return mock_replica
        return mock_main

    with patch("asyncpg.create_pool", new_callable=AsyncMock, side_effect=create_pool_side_effect):
        pool = await manager.initialize_pool()

    assert pool is mock_main
    assert manager._pool is mock_main
    assert manager._replica_pool is mock_replica


@pytest.mark.asyncio
async def test_get_connection_uses_replica_when_enabled(manager, mock_pool):
    """get_connection with use_replica=True should use replica pool."""
    replica_config = ReadReplicaConfig(
        enabled=True,
        replica_url="postgresql://user:pass@replica:5432/visionos",
    )
    manager = ConnectionPoolManager(config=manager.config, replica_config=replica_config)

    mock_main = AsyncMock()
    mock_replica = AsyncMock()
    mock_replica_conn = AsyncMock()
    mock_replica.acquire = AsyncMock(return_value=mock_replica_conn)

    def create_pool_side_effect(dsn, **kwargs):
        if "replica" in dsn:
            return mock_replica
        return mock_main

    with patch("asyncpg.create_pool", new_callable=AsyncMock, side_effect=create_pool_side_effect):
        await manager.initialize_pool()

    conn = await manager.get_connection(use_replica=True)
    assert conn is mock_replica_conn


@pytest.mark.asyncio
async def test_execute_with_retry_on_replica(manager, mock_pool):
    """execute_with_retry with use_replica=True should use replica pool."""
    replica_config = ReadReplicaConfig(
        enabled=True,
        replica_url="postgresql://user:pass@replica:5432/visionos",
    )
    manager = ConnectionPoolManager(config=manager.config, replica_config=replica_config)

    mock_main = AsyncMock()
    mock_replica = AsyncMock()
    mock_replica_conn = AsyncMock()
    mock_replica_conn.fetch = AsyncMock(return_value=[{"id": 1}])
    mock_replica.acquire = AsyncMock(return_value=mock_replica_conn)

    def create_pool_side_effect(dsn, **kwargs):
        if "replica" in dsn:
            return mock_replica
        return mock_main

    with patch("asyncpg.create_pool", new_callable=AsyncMock, side_effect=create_pool_side_effect):
        await manager.initialize_pool()

    result = await manager.execute_with_retry("SELECT 1", (), use_replica=True)
    assert result == [{"id": 1}]
