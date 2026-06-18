"""
seed_database.py — Database seeding script for Vision OS.

Run this against a fresh Neon PostgreSQL instance to:
1. Enable pgvector extension
2. Apply Alembic migrations
3. Create initial admin user (optional)

Usage:
    # Set DATABASE_URL first, then:
    python scripts/seed_database.py

    # Or with explicit URL:
    DATABASE_URL=postgresql://user:pass@neon-host:5432/visionos python scripts/seed_database.py
"""

import asyncio
import logging
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def seed() -> None:
    """Run database seeding process."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)

    # Convert to async URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    logger.info("Connecting to database...")
    engine = create_async_engine(database_url, pool_pre_ping=True)

    try:
        async with engine.begin() as conn:
            # Step 1: Enable pgvector extension
            logger.info("Enabling pgvector extension...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✓ pgvector extension enabled")

            # Step 2: Verify extension
            result = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            if row:
                logger.info("✓ pgvector version: %s", row[1])
            else:
                logger.warning("pgvector extension not found after creation")

        logger.info("Database seeding complete!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run: alembic upgrade head")
        logger.info("  2. Start the server: uvicorn backend.dashboard.server:app")

    except Exception as e:
        logger.error("Database seeding failed: %s", e)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
