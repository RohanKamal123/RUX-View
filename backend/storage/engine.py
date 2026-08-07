"""
engine.py — Async SQLAlchemy engine for Neon PostgreSQL + pgvector.

Creates async engine and session factory from DATABASE_URL.
Supports both production (Neon) and local development PostgreSQL.

Usage:
    from backend.storage.engine import create_session

    async with create_session() as session:
        result = await session.execute(...)
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from backend.config import settings
from backend.storage.database import Base

logger = logging.getLogger(__name__)

# ── Engine ──────────────────────────────────────────────────────────────────────

# Strip any trailing whitespace/newlines from the DATABASE_URL (common with secrets)
_db_url = settings.database_url.strip() if settings.database_url else settings.database_url

# Convert sync DATABASE_URL to async by replacing postgresql:// with postgresql+asyncpg://
if _db_url and _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url and _db_url.startswith("postgresql+psycopg2://"):
    _db_url = _db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

# asyncpg does NOT support sslmode as a URL query parameter.
# Strip any ?ssl= or ?sslmode= query params from the URL and pass ssl=True via connect_args.
_connect_args = {}
if _db_url:
    if "?sslmode=" in _db_url:
        import re
        _db_url = re.sub(r"\?sslmode=\w+", "", _db_url)
        _connect_args["ssl"] = True
        logger.info("Stripped sslmode from URL, passing ssl=True via connect_args")
    elif "?ssl=" in _db_url:
        import re
        _db_url = re.sub(r"\?ssl=\w+", "", _db_url)
        _connect_args["ssl"] = True
        logger.info("Stripped ssl from URL, passing ssl=True via connect_args")

def _build_engine(pool_size: int, max_overflow: int, pool_timeout: int, connect_timeout: int):
    """Build a new async engine with the given pool tunables.

    Split out from module-level so :func:`refresh_engine_config` can build
    a replacement engine with different db_pool_* values without a redeploy.
    """
    return create_async_engine(
        _db_url,
        echo=(settings.log_level == "DEBUG"),
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,
        connect_args={**_connect_args, "ssl": "require", "timeout": connect_timeout},
    )


# Pool tunables the currently active _engine was built with — compared against
# config_store on each refresh_engine_config() call to decide whether a rebuild
# is warranted. Defaults match config_store.DEFAULTS' db_pool_* keys.
_current_pool_config = {
    "db_pool_size": 3,
    "db_max_overflow": 2,
    "db_pool_timeout_sec": 15,
    "db_connect_timeout_sec": 15,
}

# Use NullPool for serverless environments (Neon, Railway) to avoid connection pooling issues
_engine = _build_engine(
    _current_pool_config["db_pool_size"],
    _current_pool_config["db_max_overflow"],
    _current_pool_config["db_pool_timeout_sec"],
    _current_pool_config["db_connect_timeout_sec"],
)

# ── Session Factory ─────────────────────────────────────────────────────────────

_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Guards concurrent refresh_engine_config() calls (e.g. a config write racing
# a scheduled refresh) so _engine and _async_session_factory are always swapped
# together, never observed half-updated.
_engine_lock = asyncio.Lock()


@asynccontextmanager
async def create_session() -> AsyncIterator[AsyncSession]:
    """Create an async session with automatic commit/rollback.

    Usage:
        async with create_session() as session:
            result = await session.execute(...)
            # Auto-commits on success, rolls back on exception
    """
    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def refresh_engine_config() -> bool:
    """Rebuild the engine if config_store's db_pool_* tunables have changed.

    Compares the live ``db_pool_size`` / ``db_max_overflow`` /
    ``db_pool_timeout_sec`` / ``db_connect_timeout_sec`` values against the
    pool config the currently active engine was built with. If they differ,
    builds a fresh engine + session factory, swaps them in atomically (under
    ``_engine_lock``), and disposes the old engine's connection pool.

    This is how the tuning dashboard's db_pool_* sliders take effect without
    a redeploy: previously these engine kwargs were baked into a bare
    module-level global at import time with no way to change them short of
    restarting the process. Called on server startup, after every
    ``POST /api/config/thresholds`` write, and periodically from the
    scheduler (backend/dashboard/server.py) so other Cloud Run instances
    that didn't handle the write still pick up the change.

    Fails open (keeps the current engine, returns False) if config_store is
    unreachable — a transient Redis blip must not tear down the DB pool.

    Returns:
        True if the engine was rebuilt, False if unchanged or on error.
    """
    global _engine, _async_session_factory, _current_pool_config

    try:
        from backend.core.config_store import get_config, DEFAULTS
        cfg = (await get_config())["values"]
    except Exception as exc:
        logger.warning("refresh_engine_config: config_store unavailable, keeping current pool: %s", exc)
        return False

    new_config = {
        "db_pool_size": int(cfg.get("db_pool_size", DEFAULTS["db_pool_size"])),
        "db_max_overflow": int(cfg.get("db_max_overflow", DEFAULTS["db_max_overflow"])),
        "db_pool_timeout_sec": int(cfg.get("db_pool_timeout_sec", DEFAULTS["db_pool_timeout_sec"])),
        "db_connect_timeout_sec": int(cfg.get("db_connect_timeout_sec", DEFAULTS["db_connect_timeout_sec"])),
    }

    async with _engine_lock:
        if new_config == _current_pool_config:
            return False

        old_engine = _engine
        new_engine = _build_engine(
            new_config["db_pool_size"],
            new_config["db_max_overflow"],
            new_config["db_pool_timeout_sec"],
            new_config["db_connect_timeout_sec"],
        )
        new_factory = async_sessionmaker(
            new_engine, class_=AsyncSession, expire_on_commit=False,
        )

        _engine = new_engine
        _async_session_factory = new_factory
        _current_pool_config = new_config

        # Dispose the old pool after the swap so in-flight sessions created
        # from it (via create_session(), captured before the swap) still
        # finish against a live pool; only new sessions see the new engine.
        await old_engine.dispose()
        logger.info("Rebuilt DB engine with new pool config: %s", new_config)
        return True


async def init_db() -> None:
    """Create all tables if they don't exist.

    This is used for local development / testing.
    In production, use Alembic migrations instead.
    """
    async with _engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await _engine.dispose()
    logger.info("Database engine disposed")
