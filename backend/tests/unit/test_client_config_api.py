"""Tests for GET /api/config/client and the db-pool-refresh-on-write wiring
in backend/api/config.py.

GET /client is the endpoint connect/config_sync.py polls so the Windows
client agent can pick up motion_*/rtsp_* tuning-dashboard changes without a
rebuild -- previously there was no path at all for config_store values to
reach connect/, which has no direct Redis access. See CLAUDE.md.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.config import CLIENT_CONFIG_KEYS
from backend.core.config_store import DEFAULTS
from backend.dashboard.auth import get_current_user
from backend.dashboard.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    async def mock_get_user():
        return {"uid": "user_001", "email": "test@example.com", "tier": "free"}

    app.dependency_overrides[get_current_user] = mock_get_user
    yield
    app.dependency_overrides.clear()


def test_client_config_keys_are_the_motion_and_rtsp_subset():
    """The exported key list is exactly what connect/ needs -- not the full
    58-key envelope (which includes server-only concerns like Gemini
    throttling and DB pool sizing that a Windows agent has no use for)."""
    assert set(CLIENT_CONFIG_KEYS) == {
        "motion_min_area",
        "motion_threshold",
        "motion_history",
        "motion_var_threshold",
        "fg_mask_threshold",
        "rtsp_reconnect_delay_sec",
        "rtsp_connect_timeout_sec",
    }


def test_get_client_config_returns_defaults_when_unmodified(client):
    with patch(
        "backend.api.config.get_config",
        AsyncMock(return_value={"values": dict(DEFAULTS)}),
    ):
        response = client.get("/api/config/client")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == set(CLIENT_CONFIG_KEYS)
    for key in CLIENT_CONFIG_KEYS:
        assert body[key] == DEFAULTS[key]


def test_get_client_config_reflects_stored_overrides(client):
    values = dict(DEFAULTS)
    values["motion_min_area"] = 12000
    values["rtsp_reconnect_delay_sec"] = 15

    with patch(
        "backend.api.config.get_config",
        AsyncMock(return_value={"values": values}),
    ):
        response = client.get("/api/config/client")

    body = response.json()
    assert body["motion_min_area"] == 12000
    assert body["rtsp_reconnect_delay_sec"] == 15


def test_get_client_config_requires_auth(client):
    """No auth override installed -- real get_current_user should reject."""
    app.dependency_overrides.clear()
    response = client.get("/api/config/client")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_thresholds_triggers_db_pool_refresh(client):
    """POST /thresholds should attempt an immediate engine refresh so a
    db_pool_* change takes effect on this instance right away, not only on
    the next 5-minute scheduler tick (backend/dashboard/server.py)."""
    with patch("backend.api.config.set_config", AsyncMock(return_value={"values": dict(DEFAULTS)})), \
         patch("backend.storage.engine.refresh_engine_config", AsyncMock(return_value=True)) as mock_refresh:
        response = client.post("/api/config/thresholds", json={"db_pool_size": 8})

    assert response.status_code == 200
    mock_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_thresholds_succeeds_even_if_refresh_fails(client):
    """A DB engine rebuild failure must not break the config write itself --
    the config is already persisted to Redis by the time refresh runs."""
    with patch("backend.api.config.set_config", AsyncMock(return_value={"values": dict(DEFAULTS)})), \
         patch("backend.storage.engine.refresh_engine_config", AsyncMock(side_effect=RuntimeError("boom"))):
        response = client.post("/api/config/thresholds", json={"db_pool_size": 8})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_thresholds_triggers_db_pool_refresh(client):
    with patch("backend.api.config.reset_config", AsyncMock(return_value={"values": dict(DEFAULTS)})), \
         patch("backend.storage.engine.refresh_engine_config", AsyncMock(return_value=False)) as mock_refresh:
        response = client.post("/api/config/thresholds/reset")

    assert response.status_code == 200
    mock_refresh.assert_awaited_once()
