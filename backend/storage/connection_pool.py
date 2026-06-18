"""
Vision OS — Database Connection Pooling Module (Sprint 10.3)

Manages async PostgreSQL connection pools using SQLAlchemy async + asyncpg.
Supports connection health checks, automatic reconnection, pool metrics,
and optional read replicas for analytics queries.
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timedelta

import asyncpg
from asyncpg.pool import Pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PoolConfig:
    """Configuration for the asyncpg connection pool."""
    database_url: str
    min_size: int = 2
    max_size: int = 10
    max_queries: int = 50000
    max_inactive_connection_lifetime: float = 300.0  # seconds
    command_timeout: int = 30
    statement_cache_size: int = 100
    ssl: str = "require"


@dataclass
class PoolStats:
    """Snapshot of pool metrics at a point in time."""
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    max_connections: int = 0
    waiting_requests: int = 0
    avg_acquire_time_ms: float = 0.0
    total_queries_executed: int = 0
    queries_per_second: float = 0.0
    errors_last_5min: int = 0
    pool_utilization_pct: float = 0.0


@dataclass
class ReadReplicaConfig:
    """Optional read-replica configuration for analytics workloads."""
    enabled: bool = False
    replica_url: Optional[str] = None
    analytics_queries_only: bool = True


# ---------------------------------------------------------------------------
# Pool Manager
# ---------------------------------------------------------------------------

class ConnectionPoolManager:
    """
    Manages an asyncpg connection pool with health checks, metrics,
    automatic reconnection, and optional read-replica support.
    """

    def __init__(self, config: PoolConfig, replica_config: Optional[ReadReplicaConfig] = None):
        self.config = config
        self.replica_config = replica_config or ReadReplicaConfig()
        self._pool: Optional[Pool] = None
        self._replica_pool: Optional[Pool] = None
        self._total_queries: int = 0
        self._error_count: int = 0
        self._error_reset_time: float = time.time()
        self._cumulative_acquire_time_ms: float = 0.0
        self._acquire_count: int = 0
        self._health_check_task: Optional[asyncio.Task] = None
        self._running: bool = False

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def initialize_pool(self, pool_config: Optional[PoolConfig] = None) -> Pool:
        """Create and return the main connection pool."""
        if pool_config:
            self.config = pool_config

        if self._pool is not None:
            logger.warning("Pool already initialised; closing existing pool first.")
            await self.close_pool()

        logger.info(
            "Initialising pool: min=%d max=%d db=%s",
            self.config.min_size,
            self.config.max_size,
            self._mask_url(self.config.database_url),
        )

        self._pool = await asyncpg.create_pool(
            dsn=self.config.database_url,
            min_size=self.config.min_size,
            max_size=self.config.max_size,
            max_queries=self.config.max_queries,
            max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
            command_timeout=self.config.command_timeout,
            statement_cache_size=self.config.statement_cache_size,
            ssl=self.config.ssl,
        )

        # Initialise read-replica pool if enabled
        if self.replica_config.enabled and self.replica_config.replica_url:
            self._replica_pool = await asyncpg.create_pool(
                dsn=self.replica_config.replica_url,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                command_timeout=self.config.command_timeout,
                statement_cache_size=self.config.statement_cache_size,
                ssl=self.config.ssl,
            )
            logger.info("Read-replica pool initialised.")

        self._running = True
        # Start periodic health check
        self._health_check_task = asyncio.create_task(self._periodic_health_check())
        return self._pool

    async def get_connection(self, use_replica: bool = False) -> asyncpg.Connection:
        """
        Acquire a connection from the pool.
        If use_replica is True and replicas are enabled, acquire from replica pool.
        """
        pool = self._resolve_pool(use_replica)
        if pool is None:
            raise RuntimeError("Connection pool not initialised. Call initialize_pool() first.")

        start = time.perf_counter()
        conn = await pool.acquire()
        elapsed_ms = (time.perf_counter() - start) * 1000

        self._cumulative_acquire_time_ms += elapsed_ms
        self._acquire_count += 1
        return conn

    async def release_connection(self, conn: asyncpg.Connection, use_replica: bool = False) -> None:
        """Release a connection back to its pool."""
        pool = self._resolve_pool(use_replica)
        if pool is None:
            logger.warning("Pool not available; connection not released.")
            return
        await pool.release(conn)

    def get_pool_stats(self) -> PoolStats:
        """Return a snapshot of current pool metrics."""
        if self._pool is None:
            return PoolStats()

        now = time.time()
        time_since_reset = max(now - self._error_reset_time, 1.0)
        errors_5min = self._error_count if time_since_reset <= 300.0 else 0

        # Estimate active/idle from pool internal state
        # asyncpg doesn't expose this directly; we approximate using pool size
        pool = self._pool
        idle = max(0, pool.get_idle_size() if hasattr(pool, "get_idle_size") else 0)
        active = max(0, pool.get_size() if hasattr(pool, "get_size") else 0) - idle
        total = active + idle
        utilization = (active / max(self.config.max_size, 1)) * 100.0 if active > 0 else 0.0

        avg_acquire = (
            self._cumulative_acquire_time_ms / max(self._acquire_count, 1)
        )

        return PoolStats(
            active_connections=active,
            idle_connections=idle,
            total_connections=total,
            max_connections=self.config.max_size,
            waiting_requests=max(0, self.config.max_size - total),
            avg_acquire_time_ms=round(avg_acquire, 2),
            total_queries_executed=self._total_queries,
            queries_per_second=round(
                self._total_queries / max(time_since_reset, 1), 2
            ),
            errors_last_5min=errors_5min,
            pool_utilization_pct=round(utilization, 1),
        )

    async def health_check(self) -> bool:
        """Perform a live health check by executing a simple query."""
        try:
            conn = await self.get_connection()
            try:
                result = await conn.fetchval("SELECT 1")
                return result == 1
            finally:
                await self.release_connection(conn)
        except Exception as exc:
            logger.error("Health check failed: %s", exc)
            return False

    async def reset_pool(self) -> dict:
        """Close and recreate the connection pool. Returns status dict."""
        logger.info("Resetting connection pool...")
        old_pool = self._pool
        self._pool = None

        if old_pool:
            await old_pool.close()

        await self.initialize_pool()
        self._total_queries = 0
        self._error_count = 0
        self._error_reset_time = time.time()
        self._cumulative_acquire_time_ms = 0.0
        self._acquire_count = 0

        return {
            "status": "ok",
            "action": "pool_reset",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def close_pool(self) -> dict:
        """Close the connection pool and cancel health checks."""
        logger.info("Closing connection pool...")
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None

        # Close replica pool
        if self._replica_pool:
            await self._replica_pool.close()
            self._replica_pool = None

        if self._pool:
            await self._pool.close()
            self._pool = None

        return {
            "status": "ok",
            "action": "pool_closed",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def execute_with_retry(
        self,
        query: str,
        params: tuple = (),
        max_retries: int = 3,
        use_replica: bool = False,
    ) -> Any:
        """
        Execute a query with retry logic.

        Retries on connection-related exceptions up to *max_retries* times.
        Returns the query result.
        """
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                conn = await self.get_connection(use_replica=use_replica)
                try:
                    result = await conn.fetch(query, *params)
                    self._total_queries += 1
                    return result
                finally:
                    await self.release_connection(conn, use_replica=use_replica)
            except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as exc:
                last_exc = exc
                self._error_count += 1
                logger.warning(
                    "Query attempt %d/%d failed: %s", attempt, max_retries, exc
                )
                if attempt < max_retries:
                    wait = 0.5 * (2 ** (attempt - 1))  # Exponential back-off
                    await asyncio.sleep(wait)
        raise RuntimeError(
            f"Query failed after {max_retries} retries: {last_exc}"
        ) from last_exc

    async def execute_in_transaction(self, queries: list[tuple]) -> list[Any]:
        """
        Execute multiple query/params tuples in a single transaction.

        Each element of *queries* is a (query_string, params_tuple) pair.
        Returns a list of results in the same order.
        """
        if not queries:
            return []

        conn = await self.get_connection()
        try:
            async with conn.transaction():
                results = []
                for query, params in queries:
                    result = await conn.fetch(query, *params)
                    self._total_queries += 1
                    results.append(result)
            return results
        except Exception:
            # Transaction will be rolled back automatically
            self._error_count += 1
            raise
        finally:
            await self.release_connection(conn)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _resolve_pool(self, use_replica: bool) -> Optional[Pool]:
        """Return the appropriate pool (main or replica)."""
        if use_replica and self.replica_config.enabled:
            return self._replica_pool or self._pool
        return self._pool

    async def _periodic_health_check(self) -> None:
        """Run health checks every 30 seconds while the pool is active."""
        while self._running:
            await asyncio.sleep(30)
            try:
                healthy = await self.health_check()
                if not healthy:
                    logger.error("Periodic health check FAILED.")
                    self._error_count += 1
                else:
                    logger.debug("Periodic health check passed.")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Health check error: %s", exc)

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask credentials in a database URL for logging."""
        if "@" in url:
            parts = url.split("@")
            credentials = parts[0].split("://")[-1]
            masked = credentials.split(":")[0] + ":****"
            return url.replace(credentials, masked)
        return url
