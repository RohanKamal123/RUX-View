"""
Alembic environment configuration for Vision OS.

Uses async SQLAlchemy engine for Neon PostgreSQL + pgvector.
Targets the models defined in backend/storage/database.py.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them
from backend.storage.database import Base  # noqa: E402

# Import all model classes to ensure they're registered with Base.metadata
from backend.storage.database import (  # noqa: E402, F401
    Event,
    Person,
    PersonSighting,
    SceneState,
    AudioEvent,
    ShopAnalytic,
    Camera,
    Location,
    User,
    ApiKey,
    ApiKeyUsage,
)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from environment or config.

    Priority:
    1. DATABASE_URL environment variable
    2. alembic.ini sqlalchemy.url
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        # Convert sync URL to async if needed
        if env_url.startswith("postgresql://"):
            return env_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if env_url.startswith("postgresql+psycopg2://"):
            return env_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        return env_url
    cfg_url = config.get_main_option("sqlalchemy.url", "")
    return cfg_url or "postgresql+asyncpg://localhost:5432/visionos"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given SQL string.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations with a connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = get_database_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
