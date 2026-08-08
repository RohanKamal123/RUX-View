"""Tests for the camera rtsp_url/connection_type/p2p_* fields end-to-end
through POST /api/cameras and GET /api/cameras.

Before this, the Camera SQLAlchemy model had no rtsp_url column at all --
pg_crud.upsert_camera() silently discarded whatever the caller passed, so
every camera's connection details were lost on creation and always read
back empty. See CLAUDE.md and backend/storage/database.py.
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
    previous = cameras_api.hybrid_crud
    yield
    cameras_api.hybrid_crud = previous


class FakeCamera:
    def __init__(self, camera_id, **kwargs):
        self.camera_id = camera_id
        self.user_id = "user_001"
        self.name = kwargs.get("name", "")
        self.rtsp_url = kwargs.get("rtsp_url", "")
        self.mode = kwargs.get("mode", "indoor")
        self.is_active = True
        self.created_at = ""
        self.last_seen_at = ""
        self.connection_type = kwargs.get("connection_type", "rtsp")
        self.p2p_serial = kwargs.get("p2p_serial", "")
        self.p2p_username = kwargs.get("p2p_username", "")
        self.rtmp_stream_key = kwargs.get("rtmp_stream_key", "")


class RecordingCrud:
    """Records exactly what create_camera() was called with, so tests can
    assert the API layer forwards every field (including that
    p2p_password is passed through as plaintext for hybrid_crud to
    encrypt, never pre-encrypted or dropped by the API layer)."""

    def __init__(self):
        self.create_camera_calls: list[dict] = []
        self.cameras: list[FakeCamera] = []

    async def get_user_cameras(self, user_id):
        return self.cameras

    async def create_camera(self, user_id, name, rtsp_url="", mode="indoor",
                             connection_type="rtsp", p2p_serial="",
                             p2p_username="", p2p_password=""):
        self.create_camera_calls.append({
            "user_id": user_id, "name": name, "rtsp_url": rtsp_url, "mode": mode,
            "connection_type": connection_type, "p2p_serial": p2p_serial,
            "p2p_username": p2p_username, "p2p_password": p2p_password,
        })
        camera_id = f"CAM_{len(self.cameras)}"
        rtmp_stream_key = f"{camera_id}_testkey" if connection_type == "rtmp_push" else ""
        cam = FakeCamera(
            camera_id, name=name, rtsp_url=rtsp_url, mode=mode,
            connection_type=connection_type, p2p_serial=p2p_serial, p2p_username=p2p_username,
            rtmp_stream_key=rtmp_stream_key,
        )
        self.cameras.append(cam)
        return cam

    async def get_camera_quota(self, user_id):
        from backend.storage.hybrid_crud import QuotaInfo
        return QuotaInfo(total_cameras=len(self.cameras), max_cameras=20,
                          remaining=20 - len(self.cameras), usage_percentage=0.0, tier="free")


@pytest.fixture
def recording_crud():
    crud = RecordingCrud()
    cameras_api.hybrid_crud = crud
    return crud


def _no_limit():
    return patch("backend.api.cameras.get_max_cameras", AsyncMock(return_value=20))


class TestAddCameraRtsp:
    def test_rtsp_camera_persists_url(self, client, recording_crud):
        with _no_limit():
            response = client.post("/api/cameras", json={
                "name": "Front Gate",
                "rtsp_url": "rtsp://admin:pass@192.168.1.50:554/stream1",
                "mode": "outdoor",
            })
        assert response.status_code == 201
        call = recording_crud.create_camera_calls[0]
        assert call["connection_type"] == "rtsp"
        assert call["rtsp_url"] == "rtsp://admin:pass@192.168.1.50:554/stream1"
        assert call["p2p_password"] == ""


class TestAddCameraDahuaP2P:
    def test_p2p_camera_forwards_credentials(self, client, recording_crud):
        with _no_limit():
            response = client.post("/api/cameras", json={
                "name": "Building Lobby",
                "mode": "indoor",
                "connection_type": "dahua_p2p",
                "p2p_serial": "AB1234567",
                "p2p_username": "admin",
                "p2p_password": "hunter2",
            })
        assert response.status_code == 201
        call = recording_crud.create_camera_calls[0]
        assert call["connection_type"] == "dahua_p2p"
        assert call["p2p_serial"] == "AB1234567"
        assert call["p2p_username"] == "admin"
        assert call["p2p_password"] == "hunter2"

    def test_invalid_connection_type_rejected(self, client, recording_crud):
        with _no_limit():
            response = client.post("/api/cameras", json={
                "name": "Bad Camera",
                "connection_type": "hikvision_cloud",
            })
        assert response.status_code == 422
        assert recording_crud.create_camera_calls == []


class TestAddCameraRtmpPush:
    def test_rtmp_push_camera_gets_generated_push_url(self, client, recording_crud):
        with _no_limit():
            response = client.post("/api/cameras", json={
                "name": "Shop Front DVR",
                "mode": "outdoor",
                "connection_type": "rtmp_push",
            })
        assert response.status_code == 201
        body = response.json()
        assert body["connection_type"] == "rtmp_push"
        assert body["rtmp_push_url"] is not None
        assert body["rtmp_push_url"].startswith("rtmp://")
        assert "/live/" in body["rtmp_push_url"]
        # No connection details required up front -- rtmp_stream_key is
        # server-generated, not user-supplied.
        call = recording_crud.create_camera_calls[0]
        assert call["rtsp_url"] == ""
        assert call["p2p_password"] == ""

    def test_rtsp_camera_has_no_rtmp_push_url(self, client, recording_crud):
        with _no_limit():
            response = client.post("/api/cameras", json={
                "name": "Front Gate",
                "rtsp_url": "rtsp://192.168.1.50:554/stream1",
            })
        assert response.json()["rtmp_push_url"] is None


class TestListCamerasReturnsConnectionFields:
    def test_list_includes_connection_type_and_p2p_serial_not_password(
        self, client, recording_crud,
    ):
        with _no_limit():
            client.post("/api/cameras", json={
                "name": "Building Lobby",
                "connection_type": "dahua_p2p",
                "p2p_serial": "AB1234567",
                "p2p_username": "admin",
                "p2p_password": "hunter2",
            })

        response = client.get("/api/cameras")
        assert response.status_code == 200
        cam = response.json()["cameras"][0]
        assert cam["connection_type"] == "dahua_p2p"
        assert cam["p2p_serial"] == "AB1234567"
        assert cam["p2p_username"] == "admin"
        assert "p2p_password" not in cam
        assert "p2p_password_encrypted" not in cam


class TestHybridCrudEncryptsPassword:
    """One layer down from the API -- confirms HybridCRUD.create_camera()
    itself encrypts the plaintext password before it would ever reach
    storage, rather than relying on the API layer to do it."""

    @pytest.mark.asyncio
    async def test_create_camera_encrypts_p2p_password(self):
        from backend.storage.hybrid_crud import HybridCRUD
        from backend.core.crypto import decrypt_secret

        crud = HybridCRUD(pg_crud=None)
        crud._pg_available = True

        captured = {}

        class FakePgCam:
            id = "CAM_TEST"
            user_id = "user_001"
            name = "Test Cam"
            mode = "indoor"
            enabled = True
            created_at = None
            rtsp_url = None
            connection_type = "dahua_p2p"
            p2p_serial = "AB1234567"
            p2p_username = "admin"
            rtmp_stream_key = None

        async def fake_upsert_camera(**kwargs):
            captured.update(kwargs)
            return FakePgCam()

        crud._pg = type("FakePg", (), {"upsert_camera": staticmethod(fake_upsert_camera)})()

        await crud.create_camera(
            user_id="user_001", name="Test Cam", connection_type="dahua_p2p",
            p2p_serial="AB1234567", p2p_username="admin", p2p_password="hunter2",
        )

        assert captured["p2p_password_encrypted"] != "hunter2"
        assert decrypt_secret(captured["p2p_password_encrypted"]) == "hunter2"

    @pytest.mark.asyncio
    async def test_create_camera_generates_rtmp_stream_key_only_for_rtmp_push(self):
        """rtmp_stream_key must be server-generated (never user-supplied,
        since it doubles as the ingest server's auth) and only set when
        connection_type is actually rtmp_push."""
        from backend.storage.hybrid_crud import HybridCRUD

        crud = HybridCRUD(pg_crud=None)
        crud._pg_available = True
        captured = {}

        class FakePgCam:
            id = "CAM_TEST"
            user_id = "user_001"
            name = "Test Cam"
            mode = "indoor"
            enabled = True
            created_at = None
            rtsp_url = None
            connection_type = "rtmp_push"
            p2p_serial = None
            p2p_username = None
            rtmp_stream_key = "CAM_TEST_generated"

        async def fake_upsert_camera(**kwargs):
            captured.update(kwargs)
            return FakePgCam()

        crud._pg = type("FakePg", (), {"upsert_camera": staticmethod(fake_upsert_camera)})()

        result = await crud.create_camera(
            user_id="user_001", name="Test Cam", connection_type="rtmp_push",
        )

        assert captured["rtmp_stream_key"] is not None
        assert captured["rtmp_stream_key"].startswith("CAM_")
        assert result.rtmp_stream_key == "CAM_TEST_generated"
