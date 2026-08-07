"""
Tests for clip_analysis.py — clip upload, dry-run pipeline analysis, and cleanup.

Key test: test_forced_crash_cleanup exercises the REAL try/finally
in clip_analysis.py's event_generator() by mocking process_frame()
directly (not an internal Gemini call).  The exception propagates
to the production finally block and triggers cleanup.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
from pathlib import Path
import tempfile
import uuid

from backend.core.config_store import DEFAULTS
from backend.core.detection.incident_builder import (
    _last_gemini_call,
    _last_track_count,
    cleanup_synthetic_camera,
)


@pytest.fixture(autouse=True)
def clear_clip_store():
    """Clear the in-memory clip store between tests."""
    from backend.api.clip_analysis import _clip_store
    _clip_store.clear()
    yield
    _clip_store.clear()


@pytest.fixture
def mock_video_file(tmp_path):
    """Create a fake 'mp4' file for upload tests."""
    video_path = tmp_path / "test_clip.mp4"
    video_path.write_bytes(b"fake mp4 bytes that won't be probed")
    return video_path


@pytest.fixture
def mock_process_frame():
    """Mock process_frame to return a realistic PipelineResult without real Gemini."""
    from backend.core.pipeline import PipelineResult
    async def fake_process_frame(camera_id, user_id, location_id, mode, jpeg_bytes, camera_profile=None, dry_run=False):
        return PipelineResult(
            incident_id="INC-TEST-001",
            threat_level="HIGH",
            alert_message="Dry-run detection test",
            alert_sent=False,
            change_detected=True,
            dry_run=dry_run,
            suppressed_alerts=[{"threat_level": "HIGH", "alert_message": "Would have sent alert", "person_ids": []}],
            suppressed_db_events=[{"camera_id": camera_id, "user_id": user_id, "incident_id": "INC-TEST-001", "threat_level": "HIGH", "alert_message": "Would have saved"}],
            stage_timings_ms={"yolo_ms": 15.2, "track_ms": 8.7, "incident_builder_ms": 0.3, "pipeline_ms": 450.0, "total_ms": 475.0},
        )
    return fake_process_frame


@pytest.fixture
def mock_clip_store():
    """Populate the clip store with a fake clip entry."""
    from backend.api.clip_analysis import _clip_store
    clip_id = "test-clip-001"
    _clip_store[clip_id] = {
        "path": str(Path(tempfile.gettempdir()) / "clip_analysis" / clip_id / "source.mp4"),
        "fps": 30.0,
        "duration_sec": 2.0,
        "total_frames": 60,
        "frames_done": 0,
        "status": "uploaded",
    }
    return clip_id


@pytest.fixture
def mock_config_store_simple():
    """Mock config_store._get_config, _get_max_frames, _get_gemini_interval."""
    async def fake_get_config():
        return {
            "values": dict(DEFAULTS),
            "defaults": dict(DEFAULTS),
            "modified_keys": [],
            "category_groups": {},
            "live_effective": [],
        }
    with patch("backend.api.clip_analysis._get_config", fake_get_config):
        with patch("backend.api.clip_analysis._get_max_frames", return_value=1800):
            with patch("backend.api.clip_analysis._get_gemini_interval", return_value=60):
                yield


class TestClipUpload:
    """Tests for the upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_returns_valid_clip_id(self, mock_video_file):
        """Upload a valid file and confirm clip_id and metadata are returned."""
        from backend.api.clip_analysis import upload_clip

        file_mock = MagicMock()
        file_mock.filename = "test_clip.mp4"
        file_mock.read = AsyncMock(return_value=mock_video_file.read_bytes())

        # file.read returns the mock data once, then empty to break the upload loop
        file_mock.read = AsyncMock(side_effect=[mock_video_file.read_bytes(), b""])

        # Mock _probe_video to avoid OpenCV probing the fake file
        with patch("backend.api.clip_analysis._probe_video", return_value=(60, 30.0, 2.0)):
            result = await upload_clip(file=file_mock)

        assert "clip_id" in result
        assert isinstance(result["clip_id"], str)
        assert len(result["clip_id"]) == 32  # uuid4 hex
        assert result["total_frames"] == 60
        assert result["source_fps"] == 30.0

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self):
        """File exceeding 200MB returns 413."""
        from backend.api.clip_analysis import upload_clip
        from fastapi import HTTPException

        file_mock = MagicMock()
        file_mock.filename = "too_big.mp4"

        async def oversized_read(chunk_size):
            return b"x" * (chunk_size)
        file_mock.read = oversized_read

        with pytest.raises(HTTPException) as exc_info:
            await upload_clip(file=file_mock)

        assert exc_info.value.status_code == 413
        detail = exc_info.value.detail
        assert detail["code"] == "FILE_TOO_LARGE"


class TestClipRun:
    """Tests for the run (SSE streaming) endpoint."""

    @pytest.mark.asyncio
    async def test_oversized_clip_rejected(self, mock_config_store_simple):
        """Safety rail: clip exceeding max_frames returns 400 before any processing."""
        from backend.api.clip_analysis import _clip_store, run_clip_analysis
        from fastapi import HTTPException
        from starlette.requests import Request

        oversized_clip_id = "oversized-clip"
        _clip_store[oversized_clip_id] = {
            "path": "/fake/path.mp4",
            "fps": 30.0,
            "duration_sec": 300.0,  # 5 minutes → 3000 frames at 10fps
            "total_frames": 9000,
            "frames_done": 0,
            "status": "uploaded",
        }

        mock_request = MagicMock(spec=Request)
        mock_request.app.state.pipeline_v2 = MagicMock()
        mock_request.app.state.pipeline_manager = MagicMock()

        with patch("backend.api.clip_analysis._get_max_frames", return_value=50):
            with pytest.raises(HTTPException) as exc_info:
                await run_clip_analysis(
                    clip_id=oversized_clip_id,
                    request=mock_request,
                    fps=10,
                )

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error"] == "CLIP_TOO_LONG"
        assert "estimated_frames" in detail

    @pytest.mark.asyncio
    async def test_dry_run_true_on_every_frame(self, mock_clip_store, mock_config_store_simple):
        """Every process_frame call receives dry_run=True."""
        from backend.api.clip_analysis import run_clip_analysis
        from starlette.requests import Request

        mock_request = MagicMock(spec=Request)
        mock_pv2 = MagicMock()

        captured_calls = []
        async def tracking_process_frame(**kwargs):
            captured_calls.append(kwargs.get("dry_run", None))
            from backend.core.pipeline import PipelineResult
            return PipelineResult(
                incident_id="INC-TEST",
                threat_level="LOW",
                dry_run=kwargs.get("dry_run", False),
                stage_timings_ms={"total_ms": 10.0},
            )

        mock_pv2.process_frame = AsyncMock(side_effect=tracking_process_frame)
        mock_request.app.state.pipeline_v2 = mock_pv2

        mock_pm = MagicMock()
        mock_pm.cleanup_synthetic_camera = MagicMock()
        mock_request.app.state.pipeline_manager = mock_pm

        # Create a mock frame generator to patch into clip_analysis
        # instead of real OpenCV calls
        import numpy as np
        fake_frames = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None),
        ]

        class FakeCapture:
            def __init__(self, path):
                self._frames = iter(fake_frames)
                self._pos_msec = 0.0

            def isOpened(self):
                return True

            def get(self, prop):
                if prop == 5:  # CAP_PROP_FPS
                    return 30.0
                if prop == 0:  # CAP_PROP_POS_MSEC
                    return self._pos_msec
                return 0.0

            def read(self):
                result = next(self._frames, (False, None))
                if result[0]:
                    self._pos_msec += 33.33  # ~30fps
                return result

            def release(self):
                pass

        # imencode returns (ret, np_array) which has .tobytes()
        import numpy as np
        fake_jpeg_arr = np.frombuffer(b"fake_jpeg", dtype=np.uint8)

        with patch("backend.api.clip_analysis.cv2") as mock_cv2:
            mock_cv2.VideoCapture = FakeCapture
            mock_cv2.imencode.return_value = (True, fake_jpeg_arr)

            response = await run_clip_analysis(
                clip_id="test-clip-001",
                request=mock_request,
                fps=10,
            )
            async for event in response.body_iterator:
                pass

        # Verify every process_frame call had dry_run=True
        if captured_calls:
            for call_dry_run in captured_calls:
                assert call_dry_run is True

    @pytest.mark.asyncio
    async def test_forced_crash_cleanup(self, mock_clip_store, mock_config_store_simple):
        """Type (a) test: mock process_frame directly to raise on 5th call.

        Exception propagation path:
            crashing_process_frame() raises RuntimeError
            → run()'s event_generator() catches it in the outer except
            → run()'s finally block fires (REAL production code)
                → cleanup_synthetic_camera(synthetic_id)   ✅
                → pm.cleanup_synthetic_camera(synthetic_id) ✅
        """
        from backend.api.clip_analysis import run_clip_analysis
        from backend.core.detection.incident_builder import _last_gemini_call, _last_track_count
        from starlette.requests import Request

        synthetic_id = "clip-analysis-test-clip-001"
        _last_gemini_call[synthetic_id] = 1000.0
        _last_track_count[synthetic_id] = 3

        mock_request = MagicMock(spec=Request)
        call_counter = [0]

        async def crashing_process_frame(camera_id=None, user_id=None, location_id=None,
                                          mode=None, jpeg_bytes=None, camera_profile=None, dry_run=False):
            call_counter[0] += 1
            if call_counter[0] == 5:
                raise RuntimeError("Simulated clip-analysis crash on frame 5")
            from backend.core.pipeline import PipelineResult
            return PipelineResult(
                incident_id="INC-TEST",
                threat_level="LOW",
                dry_run=dry_run,
                stage_timings_ms={"total_ms": 10.0},
            )

        mock_pv2 = MagicMock()
        mock_pv2.process_frame = AsyncMock(side_effect=crashing_process_frame)
        mock_request.app.state.pipeline_v2 = mock_pv2

        mock_pm = MagicMock()
        mock_pm.cleanup_synthetic_camera = MagicMock()
        mock_request.app.state.pipeline_manager = mock_pm

        import numpy as np
        fake_frames = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8))
            for _ in range(10)
        ] + [(False, None)]

        class FakeCapture:
            def __init__(self, path):
                self._frames = iter(fake_frames)
                self._pos_msec = 0.0

            def isOpened(self):
                return True

            def get(self, prop):
                if prop == 5:
                    return 30.0
                if prop == 0:
                    return self._pos_msec
                return 0.0

            def read(self):
                result = next(self._frames, (False, None))
                if result[0]:
                    self._pos_msec += 33.33
                return result

            def release(self):
                pass

        import numpy as np
        fake_jpeg_arr = np.frombuffer(b"fake_jpeg", dtype=np.uint8)

        with patch("backend.api.clip_analysis.cv2") as mock_cv2:
            mock_cv2.VideoCapture = FakeCapture
            mock_cv2.imencode.return_value = (True, fake_jpeg_arr)

            events = []
            response = await run_clip_analysis(
                clip_id="test-clip-001",
                request=mock_request,
                fps=30,
            )
            async for event_data in response.body_iterator:
                events.append(event_data)

        # Assertion 1: synthetic_id removed from _last_gemini_call
        assert synthetic_id not in _last_gemini_call, (
            f"Expected {synthetic_id} to be removed from _last_gemini_call"
        )

        # Assertion 2: synthetic_id absent from _last_track_count
        assert synthetic_id not in _last_track_count, (
            f"Expected {synthetic_id} to be removed from _last_track_count"
        )

        # Assertion 3: pm.cleanup_synthetic_camera called with synthetic ID
        mock_pm.cleanup_synthetic_camera.assert_called_with(synthetic_id)

        # Assertion 4: Exactly 4 frame events
        frame_count = 0
        for e in events:
            if e.startswith("data: "):
                try:
                    parsed = json.loads(e[6:])
                    if parsed.get("type") == "frame":
                        frame_count += 1
                except (json.JSONDecodeError, IndexError):
                    pass

        assert frame_count == 4, f"Expected 4 frame events, got {frame_count}"

        # Assertion 5: Error event present
        error_events = []
        for e in events:
            if e.startswith("data: "):
                try:
                    parsed = json.loads(e[6:])
                    if parsed.get("type") == "error":
                        error_events.append(parsed)
                except (json.JSONDecodeError, IndexError):
                    pass

        assert len(error_events) == 1, f"Expected 1 error event, got {len(error_events)}"
        assert "Simulated clip-analysis crash" in error_events[0]["message"]

        # Assertion 6: process_frame called exactly 5 times
        assert call_counter[0] == 5, f"Expected 5 process_frame calls, got {call_counter[0]}"


class TestClipStatus:
    """Tests for the status endpoint."""

    @pytest.mark.asyncio
    async def test_status_returns_progress(self, mock_clip_store):
        """Status returns correct frames_done and status."""
        from backend.api.clip_analysis import get_clip_status
        from backend.api.clip_analysis import _clip_store

        _clip_store["test-clip-001"]["frames_done"] = 15
        _clip_store["test-clip-001"]["status"] = "running"

        result = await get_clip_status("test-clip-001")

        assert result["clip_id"] == "test-clip-001"
        assert result["frames_done"] == 15
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_status_404(self):
        """Status for nonexistent clip returns 404."""
        from backend.api.clip_analysis import get_clip_status
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_clip_status("nonexistent-clip")
        assert exc_info.value.status_code == 404