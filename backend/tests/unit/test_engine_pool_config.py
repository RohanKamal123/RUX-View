"""
Tests for backend/storage/engine.py's live-tunable DB pool config.

db_pool_size / db_max_overflow / db_pool_timeout_sec / db_connect_timeout_sec
used to be baked into a bare module-level engine at import time with no way
to change them short of a redeploy. refresh_engine_config() rebuilds the
engine (and session factory) when config_store's values differ from what
the currently active engine was built with.
"""

from unittest.mock import AsyncMock, patch

import pytest

import backend.storage.engine as engine_module


@pytest.fixture(autouse=True)
def _restore_engine_state():
    """Snapshot and restore engine.py's module globals around each test.

    refresh_engine_config() mutates module-level state shared with the rest
    of the process (and other test files), so tests must not leak a
    replaced engine into whatever runs next.
    """
    original_engine = engine_module._engine
    original_factory = engine_module._async_session_factory
    original_config = dict(engine_module._current_pool_config)
    yield
    engine_module._engine = original_engine
    engine_module._async_session_factory = original_factory
    engine_module._current_pool_config = original_config


@pytest.mark.asyncio
async def test_refresh_is_noop_when_config_unchanged():
    """No rebuild when config_store reports the same pool values already active."""
    original_engine = engine_module._engine
    with patch(
        "backend.core.config_store.get_config",
        AsyncMock(return_value={"values": dict(engine_module._current_pool_config)}),
    ):
        rebuilt = await engine_module.refresh_engine_config()

    assert rebuilt is False
    assert engine_module._engine is original_engine


@pytest.mark.asyncio
async def test_refresh_rebuilds_engine_when_pool_size_changes():
    """A changed db_pool_size triggers a real engine + session factory swap."""
    original_engine = engine_module._engine
    original_factory = engine_module._async_session_factory
    new_values = dict(engine_module._current_pool_config)
    new_values["db_pool_size"] = 10

    with patch(
        "backend.core.config_store.get_config",
        AsyncMock(return_value={"values": new_values}),
    ):
        rebuilt = await engine_module.refresh_engine_config()

    assert rebuilt is True
    assert engine_module._engine is not original_engine
    assert engine_module._async_session_factory is not original_factory
    assert engine_module._current_pool_config["db_pool_size"] == 10
    # Old engine's pool was disposed as part of the swap
    await original_engine.dispose()


@pytest.mark.asyncio
async def test_refresh_rebuilds_on_connect_timeout_change_only():
    """Any of the four tunables changing (not just db_pool_size) triggers a rebuild."""
    new_values = dict(engine_module._current_pool_config)
    new_values["db_connect_timeout_sec"] = 45

    with patch(
        "backend.core.config_store.get_config",
        AsyncMock(return_value={"values": new_values}),
    ):
        rebuilt = await engine_module.refresh_engine_config()

    assert rebuilt is True
    assert engine_module._current_pool_config["db_connect_timeout_sec"] == 45


@pytest.mark.asyncio
async def test_refresh_fails_open_on_config_store_error():
    """A config_store read failure must keep the current engine, not tear it down."""
    original_engine = engine_module._engine
    original_config = dict(engine_module._current_pool_config)

    with patch(
        "backend.core.config_store.get_config",
        AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        rebuilt = await engine_module.refresh_engine_config()

    assert rebuilt is False
    assert engine_module._engine is original_engine
    assert engine_module._current_pool_config == original_config


@pytest.mark.asyncio
async def test_refresh_falls_back_to_defaults_for_missing_keys():
    """A partial values dict (missing db_pool_* keys) falls back to DEFAULTS,
    not to some other stale value or a KeyError."""
    from backend.core.config_store import DEFAULTS

    with patch(
        "backend.core.config_store.get_config",
        AsyncMock(return_value={"values": {}}),
    ):
        await engine_module.refresh_engine_config()

    assert engine_module._current_pool_config == {
        "db_pool_size": DEFAULTS["db_pool_size"],
        "db_max_overflow": DEFAULTS["db_max_overflow"],
        "db_pool_timeout_sec": DEFAULTS["db_pool_timeout_sec"],
        "db_connect_timeout_sec": DEFAULTS["db_connect_timeout_sec"],
    }
