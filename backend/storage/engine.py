"""
engine.py — Async SQLAlchemy engine for Neon PostgreSQL + pgvector.

Creates async engine and session factory from DATABASE_URL.
Supports both production (Neon) and local development PostgreSQL.

Usage:
    from backend.storage.engine import create_session

    async with create_session() as session:
        result = await session.execute(...)
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

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

# Use NullPool for serverless environments (Neon, Railway) to avoid connection pooling issues
_engine = create_async_engine(
    _db_url,
    echo=(settings.log_level == "DEBUG"),
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

# ── Session Factory ─────────────────────────────────────────────────────────────

_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


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
