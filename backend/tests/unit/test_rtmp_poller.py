"""Tests for backend/core/ingest/rtmp_poller.py -- the periodic sampler
for connection_type="rtmp_push" cameras that feeds frames through the
exact same session-merge/pipeline logic an HTTP motion trigger uses
(backend.api.triggers.process_camera_trigger).
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.core.ingest.rtmp_poller import poll_rtmp_cameras


class FakeCamera:
    def __init__(self, camera_id, user_id="user_001", mode="outdoor", rtmp_stream_key="key123"):
        self.camera_id = camera_id
        self.user_id = user_id
        self.mode = mode
        self.rtmp_stream_key = rtmp_stream_key


class FakeCrud:
    def __init__(self, cameras):
        self._cameras = cameras
        self.requested_connection_type = None

    async def get_cameras_by_connection_type(self, connection_type):
        self.requested_connection_type = connection_type
        return self._cameras


@pytest.mark.asyncio
async def test_no_cameras_is_a_noop():
    crud = FakeCrud([])
    with patch("backend.core.ingest.rtmp_poller.sample_frame") as mock_sample:
        await poll_rtmp_cameras(crud, pipeline_v2=None, rtsp_base="rtsp://mediamtx:8554")
    mock_sample.assert_not_called()
    assert crud.requested_connection_type == "rtmp_push"


@pytest.mark.asyncio
async def test_camera_with_no_live_frame_is_skipped_not_errored():
    crud = FakeCrud([FakeCamera("CAM_1")])
    with patch("backend.core.ingest.rtmp_poller.sample_frame", return_value=None) as mock_sample, \
         patch("backend.api.triggers.process_camera_trigger", new_callable=AsyncMock) as mock_process:
        await poll_rtmp_cameras(crud, pipeline_v2=None, rtsp_base="rtsp://mediamtx:8554")

    mock_sample.assert_called_once_with("key123", "rtsp://mediamtx:8554")
    mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_camera_with_frame_calls_process_camera_trigger():
    crud = FakeCrud([FakeCamera("CAM_1", user_id="user_42", mode="indoor", rtmp_stream_key="the-key")])
    fake_pipeline_v2 = object()

    with patch("backend.core.ingest.rtmp_poller.sample_frame", return_value=b"\xff\xd8\xff\xd9"), \
         patch("backend.api.triggers.process_camera_trigger", new_callable=AsyncMock) as mock_process:
        await poll_rtmp_cameras(crud, pipeline_v2=fake_pipeline_v2, rtsp_base="rtsp://mediamtx:8554")

    mock_process.assert_called_once()
    call_kwargs = mock_process.call_args.kwargs
    assert call_kwargs["camera_id"] == "CAM_1"
    assert call_kwargs["user_id"] == "user_42"
    assert call_kwargs["location_id"] == "user_42"
    assert call_kwargs["mode"] == "indoor"
    assert call_kwargs["jpeg_bytes"] == b"\xff\xd8\xff\xd9"
    assert call_kwargs["pipeline_v2"] is fake_pipeline_v2
    assert call_kwargs["crud"] is crud
    # jpeg re-encoded as base64 for the event's details payload
    import base64
    assert call_kwargs["image_base64"] == base64.b64encode(b"\xff\xd8\xff\xd9").decode("ascii")


@pytest.mark.asyncio
async def test_cameras_without_stream_key_are_skipped():
    crud = FakeCrud([FakeCamera("CAM_NO_KEY", rtmp_stream_key="")])
    with patch("backend.core.ingest.rtmp_poller.sample_frame") as mock_sample:
        await poll_rtmp_cameras(crud, pipeline_v2=None, rtsp_base="rtsp://mediamtx:8554")
    mock_sample.assert_not_called()


@pytest.mark.asyncio
async def test_one_camera_failure_does_not_stop_others():
    crud = FakeCrud([FakeCamera("CAM_BAD"), FakeCamera("CAM_GOOD")])

    call_count = {"n": 0}

    def sample_side_effect(stream_key, rtsp_base):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("decoder crashed")
        return b"\xff\xd8\xff\xd9"

    with patch("backend.core.ingest.rtmp_poller.sample_frame", side_effect=sample_side_effect), \
         patch("backend.api.triggers.process_camera_trigger", new_callable=AsyncMock) as mock_process:
        await poll_rtmp_cameras(crud, pipeline_v2=None, rtsp_base="rtsp://mediamtx:8554")

    # The second (good) camera's frame should still have been processed
    # despite the first raising.
    mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_list_failure_returns_gracefully():
    class FailingCrud:
        async def get_cameras_by_connection_type(self, connection_type):
            raise RuntimeError("db down")

    # Must not raise -- a poll failing to even list cameras shouldn't
    # crash the scheduler job.
    await poll_rtmp_cameras(FailingCrud(), pipeline_v2=None, rtsp_base="rtsp://mediamtx:8554")
