"""Regression coverage for the session-merge fixes in backend/api/triggers.py.

Root cause this guards against: a single continuous visit (e.g. one person
walking across a camera's view for ~20m/20s) used to fragment into 10-15
separate events instead of one. Two distinct bugs contributed:

1. (Fixed in an earlier pass, tested here for the first time) ANY no-change
   pipeline result (a transient YOLO miss from occlusion, motion blur, an
   edge-of-frame moment, or the per-incident throttle) during an *already
   active* session popped the session from `_active_sessions` and reset the
   Gemini throttle -- so the very next motion frame started a brand-new
   event instead of continuing the existing one. Fix: during an active
   session, every no-change result now just extends `last_motion_at` and
   returns "session_updated"; only the time-based `_session_cleanup_loop`
   (session_timeout_sec, default 180s) or the request's own
   session-timed-out check may actually end a session.

2. (Found and fixed while writing this test file) For a brand-new session,
   crud.create_event() ran *before* the pipeline's YOLO-gate verdict was
   known -- so a pure "yolo_gate" miss (no real person/vehicle/animal in
   frame at all, e.g. ambient motion from leaves/shadows that the client's
   OpenCV motion detector already false-triggers on) still wrote a
   permanent, never-closed "PENDING" event to the DB, even though the
   caller was correctly told "no_change". Nothing ever updates or cleans up
   that row since the session it would belong to was never registered.
   Fix: the pipeline now runs first; the event is only created once the
   trigger is confirmed real (change_detected, a non-yolo_gate no-change
   reason like "throttled", or a pipeline evaluation error where we fail
   open and trust the raw motion trigger).

Neither had any test coverage before this file -- both were verified by
code review only.
"""

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import backend.api.triggers as triggers_api
from backend.api.triggers import get_crud
from backend.core.pipeline import PipelineResult
from backend.dashboard.auth import get_current_user
from backend.dashboard.server import app

CAMERA_ID = "CAM_SESSION_MERGE_TEST"
FAKE_JPEG_B64 = base64.b64encode(b"fake-jpeg-bytes").decode()


class FakeEvent:
    def __init__(self, event_id: str):
        self.event_id = event_id


class FakeCrud:
    """Stand-in for HybridCRUD that just records what triggers.py did,
    without touching a real database."""

    def __init__(self):
        self.created_events: list[FakeEvent] = []
        self.update_calls: list[dict] = []
        self._counter = 0

    async def create_event(self, user_id, camera_id, event_type, details):
        self._counter += 1
        event = FakeEvent(f"EVT_{self._counter}")
        self.created_events.append(event)
        return event

    async def update_event(self, event_id=None, **kwargs):
        self.update_calls.append({"event_id": event_id, **kwargs})


class FakePipelineV2:
    """Replaces app.state.pipeline_v2. process_frame returns one queued
    PipelineResult per call, in order -- lets a test script an exact
    sequence of YOLO hits/misses across a simulated walk."""

    def __init__(self, results: list[PipelineResult]):
        self.process_frame = AsyncMock(side_effect=results)


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


@pytest.fixture
def fake_crud():
    crud = FakeCrud()
    app.dependency_overrides[get_crud] = lambda: crud
    yield crud
    app.dependency_overrides.pop(get_crud, None)


@pytest.fixture(autouse=True)
def clean_session_state():
    """_active_sessions/_session_locks are bare module-level globals in
    triggers.py -- reset around every test so runs don't leak into each
    other or into unrelated tests running later in the same session."""
    triggers_api._active_sessions.clear()
    triggers_api._session_locks.clear()
    yield
    triggers_api._active_sessions.clear()
    triggers_api._session_locks.clear()


def _post_frame(client, confidence: float = 1.0):
    return client.post(
        "/api/triggers/frame",
        json={
            "camera_id": CAMERA_ID,
            "image_base64": FAKE_JPEG_B64,
            "mode": "outdoor",
            "confidence": confidence,
        },
    )


def _set_pipeline_v2(results: list[PipelineResult]):
    fake_pv2 = FakePipelineV2(results)
    original = getattr(app.state, "pipeline_v2", None)
    app.state.pipeline_v2 = fake_pv2
    return fake_pv2, original


class TestOneWalkIsOneEvent:
    """The core regression: a continuous visit with a realistic mix of
    solid YOLO hits and transient misses must produce exactly one event."""

    def test_walk_with_intermittent_yolo_misses_stays_one_session(
        self, client, fake_crud,
    ):
        results = [
            PipelineResult(change_detected=True, threat_level="LOW"),
            PipelineResult(change_detected=False, skip_reason="yolo_gate"),
            PipelineResult(change_detected=False, skip_reason="yolo_gate"),
            PipelineResult(change_detected=True, threat_level="MEDIUM"),
            PipelineResult(change_detected=False, skip_reason="throttled"),
            PipelineResult(change_detected=True, threat_level="LOW"),
            PipelineResult(change_detected=False, skip_reason="yolo_gate"),
            PipelineResult(change_detected=True, threat_level="MEDIUM"),
            PipelineResult(change_detected=False, skip_reason="throttled"),
            PipelineResult(change_detected=True, threat_level="LOW"),
        ]
        fake_pv2, original = _set_pipeline_v2(results)
        try:
            responses = [_post_frame(client) for _ in results]
        finally:
            app.state.pipeline_v2 = original

        for r in responses:
            assert r.status_code == 200

        # This is the headline assertion: 10 frames over one continuous
        # visit -> exactly one event, not 10 and not "10-15".
        assert len(fake_crud.created_events) == 1

        event_ids = {r.json()["event_id"] for r in responses if "event_id" in r.json()}
        assert event_ids == {fake_crud.created_events[0].event_id}

        last_body = responses[-1].json()
        assert last_body["frame_count"] == len(results)
        assert last_body["max_threat"] == "MEDIUM"

    def test_all_no_change_after_first_frame_still_one_session(
        self, client, fake_crud,
    ):
        """Even a long, unbroken run of transient misses (heavy occlusion,
        subject standing still just off the YOLO confidence threshold)
        must not fragment the session -- only the time-based cleanup loop
        may end it."""
        results = [PipelineResult(change_detected=True, threat_level="LOW")] + [
            PipelineResult(change_detected=False, skip_reason="yolo_gate")
            for _ in range(8)
        ]
        fake_pv2, original = _set_pipeline_v2(results)
        try:
            responses = [_post_frame(client) for _ in results]
        finally:
            app.state.pipeline_v2 = original

        assert len(fake_crud.created_events) == 1
        assert responses[-1].json()["frame_count"] == len(results)


class TestNewSessionYoloGateStillSkipsPending:
    """A lone motion blip that never produces a real YOLO hit still must
    NOT become a session at all -- this is intentionally different from
    the active-session case above, and the fix must not have collapsed
    that distinction."""

    def test_first_frame_yolo_gate_creates_no_session(self, client, fake_crud):
        results = [PipelineResult(change_detected=False, skip_reason="yolo_gate")]
        fake_pv2, original = _set_pipeline_v2(results)
        try:
            response = _post_frame(client)
        finally:
            app.state.pipeline_v2 = original

        assert response.status_code == 200
        assert response.json()["status"] == "no_change"
        assert len(fake_crud.created_events) == 0
        assert CAMERA_ID not in triggers_api._active_sessions

    def test_first_frame_throttled_keeps_session_alive(self, client, fake_crud):
        """Unlike yolo_gate, a first-frame 'throttled' result means a real
        object passed the YOLO gate and a session should still open --
        Gemini is just being rate-limited for this particular frame, not
        rejecting the object entirely."""
        results = [PipelineResult(change_detected=False, skip_reason="throttled")]
        fake_pv2, original = _set_pipeline_v2(results)
        try:
            response = _post_frame(client)
        finally:
            app.state.pipeline_v2 = original

        assert response.status_code == 200
        assert response.json()["status"] == "session_created"
        assert len(fake_crud.created_events) == 1
        assert CAMERA_ID in triggers_api._active_sessions
        assert triggers_api._active_sessions[CAMERA_ID]["max_threat"] == "PENDING"


class TestSessionTimeoutStillWorks:
    """The fix must not have accidentally made sessions immortal --
    a genuinely stale session (last_motion_at older than
    session_timeout_sec) must still close and let a new visit start a new
    event."""

    def test_stale_session_starts_a_new_event(self, client, fake_crud):
        results = [
            PipelineResult(change_detected=True, threat_level="LOW"),
            PipelineResult(change_detected=True, threat_level="LOW"),
        ]
        fake_pv2, original = _set_pipeline_v2(results)
        try:
            first = _post_frame(client)
            assert first.status_code == 200
            assert len(fake_crud.created_events) == 1

            # Simulate the first visit having gone quiet well past
            # session_timeout_sec (default 180s) ago.
            session = triggers_api._active_sessions[CAMERA_ID]
            session["last_motion_at"] = datetime.now(timezone.utc) - timedelta(seconds=999)

            second = _post_frame(client)
            assert second.status_code == 200
        finally:
            app.state.pipeline_v2 = original

        # A second, distinct visit after the timeout must be a new event.
        assert len(fake_crud.created_events) == 2
        assert first.json()["event_id"] != second.json()["event_id"]
