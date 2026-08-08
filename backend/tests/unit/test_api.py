"""
test_api.py — Unit tests for Vision OS API routes (triggers, cameras, users, queries).

Uses FastAPI TestClient with a fake HybridCRUD (dependency-overridden, not
a real Postgres connection) and mocked auth. Assertions match the real
route contracts in backend/api/{triggers,cameras,users,queries}.py, not
an earlier "stub" version of the API.
"""

from unittest.mock import AsyncMock, patch

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.storage.hybrid_crud import Camera, Event, QuotaInfo, User
from backend.ai.query_agent import QueryAgentResult

# ── Test App Setup ────────────────────────────────────────────


@pytest.fixture
def app():
    """Create a FastAPI app with all routers for testing."""
    from backend.api.triggers import router as triggers_router
    from backend.api.cameras import router as cameras_router
    from backend.api.users import router as users_router
    from backend.api.queries import router as queries_router

    app = FastAPI()
    app.include_router(triggers_router)
    app.include_router(cameras_router)
    app.include_router(users_router)
    app.include_router(queries_router)
    return app


@pytest.fixture
def mock_auth_user():
    """Override the get_current_user dependency with a mock user."""

    async def mock_get_current_user():
        return {
            "uid": "test-user-123",
            "email": "test@example.com",
            "tier": "guard",
            "subscription_active": True,
        }

    return mock_get_current_user


@pytest.fixture
def mock_auth_free_user():
    """Override the get_current_user dependency with a free-tier user."""

    async def mock_get_current_user():
        return {
            "uid": "free-user-456",
            "email": "free@example.com",
            "tier": "free",
            "subscription_active": False,
        }

    return mock_get_current_user


class FakeCrud:
    """Minimal in-memory stand-in for HybridCRUD -- covers exactly the
    methods the routes under test call, with real dataclass return types
    so response-shape assertions exercise the same field access the real
    routes do."""

    def __init__(self):
        self.cameras = {
            "CAM_FRONT_001": Camera(
                camera_id="CAM_FRONT_001",
                user_id="test-user-123",
                name="Front Door",
                rtsp_url="rtsp://cam.local/stream",
                mode="outdoor",
                is_active=True,
            )
        }
        self.events = []

    async def get_user_cameras(self, user_id):
        return [c for c in self.cameras.values() if c.user_id == user_id]

    async def create_camera(self, user_id, name, rtsp_url="", mode="indoor",
                             connection_type="rtsp", p2p_serial="",
                             p2p_username="", p2p_password=""):
        cam = Camera(
            camera_id="CAM_NEW_001", user_id=user_id, name=name,
            rtsp_url=rtsp_url, mode=mode, connection_type=connection_type,
        )
        self.cameras[cam.camera_id] = cam
        return cam

    async def update_camera(self, camera_id, user_id, updates):
        cam = self.cameras[camera_id]
        cam.name = updates.get("name", cam.name)
        cam.mode = updates.get("mode", cam.mode)
        return cam

    async def delete_camera(self, camera_id, user_id):
        cam = self.cameras.get(camera_id)
        if cam is None or cam.user_id != user_id:
            return False
        del self.cameras[camera_id]
        return True

    async def get_camera_quota(self, user_id):
        total = len(await self.get_user_cameras(user_id))
        return QuotaInfo(total_cameras=total, max_cameras=20, remaining=20 - total)

    async def get_or_create_user(self, user_id, email="", name=""):
        return User(user_id=user_id, email=email, name=name, tier="guard")

    async def update_user(self, user_id, updates):
        return User(
            user_id=user_id, email="", name=updates.get("name", ""), tier="guard",
        )

    async def create_event(self, user_id, camera_id, event_type="motion", details=None):
        event = Event(event_id="EVT_TEST_001", user_id=user_id, camera_id=camera_id,
                      event_type=event_type)
        self.events.append(event)
        return event


@pytest.fixture
def fake_crud():
    return FakeCrud()


@pytest.fixture
def client(app, mock_auth_user, fake_crud):
    """Test client with mocked auth and a fake storage backend."""
    from backend.dashboard.auth import get_current_user
    from backend.api.cameras import get_crud as cameras_get_crud
    from backend.api.users import get_crud as users_get_crud
    from backend.api.queries import get_crud as queries_get_crud
    from backend.api.triggers import get_crud as triggers_get_crud

    app.dependency_overrides = {
        get_current_user: mock_auth_user,
        cameras_get_crud: lambda: fake_crud,
        users_get_crud: lambda: fake_crud,
        queries_get_crud: lambda: fake_crud,
        triggers_get_crud: lambda: fake_crud,
    }
    with TestClient(app) as c:
        yield c


@pytest.fixture
def free_client(app, mock_auth_free_user, fake_crud):
    """Test client with a free-tier user and a fake storage backend."""
    from backend.dashboard.auth import get_current_user
    from backend.api.queries import get_crud as queries_get_crud

    app.dependency_overrides = {
        get_current_user: mock_auth_free_user,
        queries_get_crud: lambda: fake_crud,
    }
    with TestClient(app) as c:
        yield c


# ── Test: Trigger Endpoints ───────────────────────────────────
#
# receive_frame_trigger() is a thin wrapper around process_camera_trigger(),
# which owns the real session-merge/pipeline logic -- that logic already
# has dedicated coverage in test_session_merge.py. These tests patch
# process_camera_trigger directly so they exercise the HTTP layer (auth,
# request validation, response passthrough) without re-mocking the whole
# pipeline stack.


def test_trigger_endpoint_accepts_jpeg(client):
    """Test that the frame trigger endpoint accepts a valid request and
    passes the pipeline result straight through."""
    with patch(
        "backend.api.triggers.process_camera_trigger",
        new=AsyncMock(return_value={"event_id": "EVT_001", "status": "created"}),
    ):
        response = client.post(
            "/triggers/frame",
            json={
                "camera_id": "CAM_FRONT_001",
                "image_base64": "",
                "timestamp": "2026-04-25T10:00:00Z",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"event_id": "EVT_001", "status": "created"}


def test_trigger_endpoint_requires_camera_id(client):
    """Test that a missing camera_id is rejected before reaching the pipeline."""
    response = client.post(
        "/triggers/frame",
        json={"camera_id": "", "image_base64": ""},
    )
    assert response.status_code == 422


def test_trigger_audio_endpoint(client):
    """Test that the audio trigger endpoint accepts audio and creates an event."""
    response = client.post(
        "/triggers/audio",
        json={
            "camera_id": "CAM_FRONT_001",
            "audio_base64": "UklGRg==",
            "timestamp": "2026-04-25T10:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert data["event_id"] == "EVT_TEST_001"


def test_trigger_endpoint_rejects_unauthenticated(app, fake_crud):
    """Test that trigger endpoints reject requests without auth."""
    from backend.dashboard.auth import get_current_user
    from fastapi import HTTPException

    async def mock_no_auth():
        raise HTTPException(status_code=401, detail="Unauthorized")

    app.dependency_overrides = {get_current_user: mock_no_auth}

    with TestClient(app) as c:
        response = c.post(
            "/triggers/frame",
            json={"camera_id": "CAM_001", "image_base64": ""},
        )
        assert response.status_code == 401


# ── Test: Camera CRUD ─────────────────────────────────────────


def test_camera_list(client):
    """Test listing cameras returns expected structure."""
    response = client.get("/cameras")
    assert response.status_code == 200
    data = response.json()
    assert "cameras" in data
    assert "total" in data
    assert len(data["cameras"]) > 0


def test_camera_create(client):
    """Test creating a camera returns 201 with the created camera's id."""
    response = client.post(
        "/cameras",
        json={"name": "New Camera", "mode": "indoor"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "created"
    assert data["id"] == "CAM_NEW_001"


def test_camera_update(client):
    """Test updating a camera returns updated status."""
    response = client.put(
        "/cameras/CAM_FRONT_001",
        json={"name": "Updated Camera", "mode": "outdoor"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["camera_id"] == "CAM_FRONT_001"
    assert data["name"] == "Updated Camera"


def test_camera_update_not_found(client):
    """Test updating a camera the user doesn't own returns 404."""
    response = client.put(
        "/cameras/CAM_DOES_NOT_EXIST",
        json={"name": "X"},
    )
    assert response.status_code == 404


def test_camera_delete(client):
    """Test deleting a camera returns deleted status."""
    response = client.delete("/cameras/CAM_FRONT_001")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["camera_id"] == "CAM_FRONT_001"


def test_camera_delete_not_found(client):
    """Test deleting a camera that doesn't exist returns 404."""
    response = client.delete("/cameras/CAM_DOES_NOT_EXIST")
    assert response.status_code == 404


# ── Test: User Profile ────────────────────────────────────────


def test_user_profile(client):
    """Test getting user profile returns user info."""
    response = client.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test-user-123"
    assert data["tier"] == "guard"
    assert data["is_active"] is True


def test_user_update_profile(client):
    """Test updating user profile."""
    response = client.put(
        "/users/me",
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["name"] == "New Name"


# ── Test: Query Endpoint ──────────────────────────────────────
#
# Natural-language queries aren't currently HTTP-gated by tier -- the
# gate lives inside query_agent.answer_question(), which returns a 200
# with error="free_tier_blocked" rather than a 403. If premium-gating
# this at the route level is wanted, that's a product decision beyond
# this test file's scope.


def test_query_endpoint_blocks_free_tier_in_body(free_client):
    """Test that free-tier users get a 200 with a free_tier_blocked error."""
    response = free_client.post(
        "/queries/natural",
        json={"query": "Who was at the front door?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == "free_tier_blocked"


def test_query_endpoint_guard_tier_allowed(client):
    """Test that guard-tier users reach the query agent (not tier-blocked)."""
    with patch(
        "backend.api.queries.answer_question",
        new=AsyncMock(return_value=QueryAgentResult(
            answer="Nobody in the last hour.", tool_calls=[], error=None
        )),
    ):
        response = client.post(
            "/queries/natural",
            json={"query": "Who wore a red shirt this morning?"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["error"] is None
