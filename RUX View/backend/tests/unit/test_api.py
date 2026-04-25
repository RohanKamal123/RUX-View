"""
test_api.py — Unit tests for Vision OS API stubs.

Tests trigger endpoints, camera CRUD, user profile, and query endpoints.
Uses FastAPI TestClient with mocked auth dependency.
"""

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
            "tier": "household",
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


@pytest.fixture
def client(app, mock_auth_user):
    """Test client with mocked auth."""
    app.dependency_overrides = {}
    from backend.dashboard.auth import get_current_user

    app.dependency_overrides[get_current_user] = mock_auth_user
    with TestClient(app) as c:
        yield c


@pytest.fixture
def free_client(app, mock_auth_free_user):
    """Test client with free-tier user."""
    app.dependency_overrides = {}
    from backend.dashboard.auth import get_current_user

    app.dependency_overrides[get_current_user] = mock_auth_free_user
    with TestClient(app) as c:
        yield c


# ── Test: Trigger Endpoints ───────────────────────────────────


def test_trigger_endpoint_accepts_jpeg(client):
    """Test that the frame trigger endpoint accepts JPEG uploads."""
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"  # Minimal JPEG

    response = client.post(
        "/triggers/frame",
        files={"jpeg": ("test.jpg", jpeg_bytes, "image/jpeg")},
        data={
            "motion_result": "motion_detected",
            "camera_id": "CAM_FRONT_001",
            "timestamp": "2026-04-25T10:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "incident_id" in data
    assert data["incident_id"].startswith("INC_")


def test_trigger_audio_endpoint(client):
    """Test that the audio trigger endpoint accepts audio uploads."""
    audio_bytes = b"RIFF\x00\x00\x00\x00WAVE"  # Minimal WAV header

    response = client.post(
        "/triggers/audio",
        files={"audio": ("test.wav", audio_bytes, "audio/wav")},
        data={
            "yamnet_result": "scream",
            "camera_id": "CAM_FRONT_001",
            "timestamp": "2026-04-25T10:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "audio_event_id" in data
    assert data["audio_event_id"].startswith("AUD_")


def test_trigger_endpoint_rejects_unauthenticated(app):
    """Test that trigger endpoints reject requests without auth."""
    from backend.dashboard.auth import get_current_user

    async def mock_no_auth():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Unauthorized")

    app.dependency_overrides = {}
    app.dependency_overrides[get_current_user] = mock_no_auth

    with TestClient(app) as c:
        response = c.post(
            "/triggers/frame",
            files={"jpeg": ("test.jpg", b"fake", "image/jpeg")},
            data={
                "motion_result": "none",
                "camera_id": "CAM_001",
                "timestamp": "2026-04-25T10:00:00Z",
            },
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
    """Test creating a camera returns created status."""
    response = client.post(
        "/cameras",
        json={
            "id": "CAM_NEW_001",
            "name": "New Camera",
            "mode": "indoor",
            "location_id": "loc-001",
        },
    )
    assert response.status_code == 200
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


def test_camera_delete(client):
    """Test deleting a camera returns deleted status."""
    response = client.delete("/cameras/CAM_FRONT_001")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["camera_id"] == "CAM_FRONT_001"


# ── Test: User Profile ────────────────────────────────────────


def test_user_profile(client):
    """Test getting user profile returns user info."""
    response = client.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "test-user-123"
    assert data["email"] == "test@example.com"
    assert data["tier"] == "household"
    assert data["subscription_active"] is True


def test_user_update_profile(client):
    """Test updating user profile."""
    response = client.put(
        "/users/me",
        json={"phone": "+8801700000000"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"


# ── Test: Query Endpoint ──────────────────────────────────────


def test_query_endpoint_requires_premium(free_client):
    """Test that free-tier users are blocked from query endpoint."""
    response = free_client.post(
        "/queries",
        json={
            "question": "Who was at the front door?",
        },
    )
    assert response.status_code == 403


def test_query_endpoint_household_allowed(client):
    """Test that household-tier users can access query endpoint."""
    response = client.post(
        "/queries",
        json={
            "question": "Who wore a red shirt this morning?",
            "cameras": ["CAM_FRONT_001"],
            "time_range": "2026-04-25T06:00:00/2026-04-25T12:00:00",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "matching_events" in data
    assert "thumbnails" in data
