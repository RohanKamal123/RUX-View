"""Tests for the camera-quota enforcement wired into POST /api/cameras.

Before this, backend/api/cameras.py::add_camera() created the camera
first and only checked quota afterwards for display purposes — the
20-camera limit the endpoint's own docstring/OpenAPI description claimed
to enforce was never actually checked. See CLAUDE.md and
backend/core/camera_limits.py's CameraLimits (a fully-built, previously
unwired validation module).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.api.cameras as cameras_api
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


@pytest.fixture(autouse=True)
def restore_hybrid_crud():
    """cameras.py's hybrid_crud is a bare module-level global — restore it
    after every test so a FakeCrud from this file never leaks into
    unrelated tests running later in the same pytest session."""
    previous = cameras_api.hybrid_crud
    yield
    cameras_api.hybrid_crud = previous


class FakeCamera:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.connection_type = "rtsp"
        self.rtmp_stream_key = ""


class FakeCrud:
    """Stand-in for HybridCRUD with a controllable existing-camera count."""

    def __init__(self, existing_count: int):
        self.existing = [FakeCamera(f"CAM_{i}") for i in range(existing_count)]
        self.create_camera_called = False

    async def get_user_cameras(self, user_id):
        return self.existing

    async def create_camera(self, user_id, name, rtsp_url="", mode="indoor",
                             connection_type="rtsp", p2p_serial="",
                             p2p_username="", p2p_password=""):
        self.create_camera_called = True
        new_cam = FakeCamera(f"CAM_{len(self.existing)}")
        self.existing.append(new_cam)
        return new_cam

    async def get_camera_quota(self, user_id):
        from backend.storage.hybrid_crud import QuotaInfo
        total = len(self.existing)
        return QuotaInfo(total_cameras=total, max_cameras=5, remaining=max(0, 5 - total),
                          usage_percentage=round(total / 5 * 100, 1), tier="free")


@pytest.mark.asyncio
async def test_add_camera_rejects_when_at_limit(client):
    """A user already at the configured limit must get 403, and the
    camera must NOT be created — this is the core bug: previously
    create_camera() ran unconditionally before any check."""
    fake_crud = FakeCrud(existing_count=5)
    cameras_api.hybrid_crud = fake_crud

    with patch("backend.api.cameras.get_max_cameras", AsyncMock(return_value=5)):
        response = client.post("/api/cameras", json={"name": "New Camera"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CAMERA_LIMIT_EXCEEDED"
    assert fake_crud.create_camera_called is False


@pytest.mark.asyncio
async def test_add_camera_allowed_under_limit(client):
    """A user under the limit should succeed and the camera should
    actually get created."""
    fake_crud = FakeCrud(existing_count=2)
    cameras_api.hybrid_crud = fake_crud

    with patch("backend.api.cameras.get_max_cameras", AsyncMock(return_value=5)):
        response = client.post("/api/cameras", json={"name": "New Camera"})

    assert response.status_code == 201
    assert fake_crud.create_camera_called is True


@pytest.mark.asyncio
async def test_add_camera_uses_configured_limit_not_hardcoded_20(client):
    """The limit must come from config_store, not a hardcoded 20 — a user
    at a config-lowered limit of 3 should be rejected even though they're
    well under the old hardcoded default."""
    fake_crud = FakeCrud(existing_count=3)
    cameras_api.hybrid_crud = fake_crud

    with patch("backend.api.cameras.get_max_cameras", AsyncMock(return_value=3)):
        response = client.post("/api/cameras", json={"name": "New Camera"})

    assert response.status_code == 403
    assert fake_crud.create_camera_called is False
