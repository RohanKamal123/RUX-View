"""End-to-End Integration Tests for VisionOS Connect Edge Agent.

Tests the full pipeline: frame capture → motion detection → trigger send.
All external dependencies (RTSP, HTTP, PyAudio) are mocked.
"""

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from connect.camera.motion_detector import MotionDetector, MotionResult
from connect.camera.rtsp_reader import RTSPReader
from connect.transport.trigger_sender import TriggerSender, TriggerResponse


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_frame() -> np.ndarray:
    """Create a synthetic BGR frame (480x640)."""
    return np.ones((480, 640, 3), dtype=np.uint8) * 128


@pytest.fixture
def frame_with_motion() -> np.ndarray:
    """Create a frame with a large white square (simulates motion)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:300, 200:400] = 255
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: RTSP → Motion Detection → Trigger
# ═══════════════════════════════════════════════════════════════════════════════

class TestFrameCaptureToTriggerPipeline:
    """Tests the full frame capture → motion detection → trigger pipeline."""

    @patch("cv2.VideoCapture")
    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_full_pipeline_frame_trigger(
        self,
        mock_httpx_cls: MagicMock,
        mock_vc_cls: MagicMock,
        sample_frame: np.ndarray,
        frame_with_motion: np.ndarray,
    ) -> None:
        """Test: RTSP capture → motion detect → send frame trigger."""
        # ── Mock RTSP ────────────────────────────────────────────────────────
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = [
            (True, sample_frame),      # First frame (baseline)
            (True, frame_with_motion), # Second frame (motion)
        ]
        mock_vc_cls.return_value = mock_cap

        # ── Mock HTTP ────────────────────────────────────────────────────────
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"event_id": "evt-int-001", "message": "ok"}'
        mock_response.json.return_value = {"event_id": "evt-int-001", "message": "ok"}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        # ── Pipeline ─────────────────────────────────────────────────────────
        reader = RTSPReader("rtsp://test:554/stream1", "cam-int-001")
        detector = MotionDetector(threshold=0.02, min_area=5000)
        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )

        # Connect to RTSP
        connected = await reader.connect()
        assert connected is True

        # Read first frame (baseline for background model)
        frame1 = await reader.read_frame()
        assert frame1 is not None
        result1 = detector.detect(frame1)
        assert isinstance(result1, MotionResult)

        # Read second frame (with motion)
        frame2 = await reader.read_frame()
        assert frame2 is not None
        result2 = detector.detect(frame2)

        # If motion detected, send trigger
        if result2.motion_detected:
            # Encode frame to JPEG then base64
            success, encoded = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
            assert success
            image_base64 = base64.b64encode(encoded.tobytes()).decode("utf-8")

            trigger_result = await sender.send_frame_trigger(
                camera_id="cam-int-001",
                image_base64=image_base64,
                timestamp=1234567890.0,
            )

            assert trigger_result.success is True
            assert trigger_result.event_id == "evt-int-001"

        # Cleanup
        await reader.release()
        await sender.close()

    @patch("cv2.VideoCapture")
    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_pipeline_no_motion_no_trigger(
        self,
        mock_httpx_cls: MagicMock,
        mock_vc_cls: MagicMock,
        sample_frame: np.ndarray,
    ) -> None:
        """Test: No motion detected → no trigger sent."""
        # ── Mock RTSP ────────────────────────────────────────────────────────
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, sample_frame)  # Same frame each time
        mock_vc_cls.return_value = mock_cap

        # ── Mock HTTP ────────────────────────────────────────────────────────
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        # ── Pipeline ─────────────────────────────────────────────────────────
        reader = RTSPReader("rtsp://test:554/stream1", "cam-int-002")
        detector = MotionDetector(threshold=0.02, min_area=5000)
        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )

        await reader.connect()

        # Read and detect multiple times with same frame
        for _ in range(3):
            frame = await reader.read_frame()
            result = detector.detect(frame)
            # Motion should not be detected on identical frames
            assert isinstance(result, MotionResult)

        # No trigger should have been sent
        mock_client.post.assert_not_called()

        await reader.release()
        await sender.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Offline Buffer → Flush on Reconnect
# ═══════════════════════════════════════════════════════════════════════════════

class TestOfflineBufferIntegration:
    """Tests the offline buffer → flush pipeline."""

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_buffer_and_flush(
        self,
        mock_httpx_cls: MagicMock,
    ) -> None:
        """Test: Buffer events offline, then flush when online."""
        from connect.buffer.local_queue import LocalQueue

        # ── Mock HTTP (succeeds immediately) ─────────────────────────────────
        mock_client = MagicMock()
        mock_client.is_closed = False

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.content = b'{"event_id": "evt-flush-001", "message": "ok"}'
        success_response.json.return_value = {"event_id": "evt-flush-001", "message": "ok"}

        mock_client.post = AsyncMock(return_value=success_response)
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        # ── Pipeline ─────────────────────────────────────────────────────────
        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )
        queue = LocalQueue(db_path=":memory:", max_events=100, ttl_hours=48)

        # Enqueue a frame event
        queue.enqueue({
            "type": "frame",
            "camera_id": "cam-flush-001",
            "image_base64": "base64data",
            "timestamp": 1234567890.0,
        })
        assert queue.count() == 1

        # Flush to server
        sent = await queue.flush_to_server(sender)
        assert sent == 1
        assert queue.count() == 0

        queue.close()
        await sender.close()

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_buffer_re_enqueue_on_failure(
        self,
        mock_httpx_cls: MagicMock,
    ) -> None:
        """Test: Events stay in buffer when server is unreachable."""
        from connect.buffer.local_queue import LocalQueue

        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=ConnectionError("No internet"))
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )
        queue = LocalQueue(db_path=":memory:", max_events=100, ttl_hours=48)

        queue.enqueue({
            "type": "frame",
            "camera_id": "cam-flush-002",
            "image_base64": "base64data",
            "timestamp": 1234567890.0,
        })

        sent = await queue.flush_to_server(sender)
        assert sent == 0
        # Event should be re-enqueued
        assert queue.count() == 1

        queue.close()
        await sender.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Audio Capture → Trigger Send
# ═══════════════════════════════════════════════════════════════════════════════

class TestAudioCaptureToTriggerPipeline:
    """Tests the audio capture → trigger pipeline."""

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_audio_capture_and_send(
        self,
        mock_httpx_cls: MagicMock,
        mock_pyaudio_cls: MagicMock,
    ) -> None:
        """Test: Capture audio chunk → send audio trigger."""
        from connect.audio.audio_capture import AudioCapture

        # ── Mock PyAudio ─────────────────────────────────────────────────────
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        # Generate audio data above RMS threshold
        audio_data = (np.ones(128000, dtype=np.float32) * 0.1).tobytes()
        mock_stream.read.return_value = audio_data
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        # ── Mock HTTP ────────────────────────────────────────────────────────
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"event_id": "evt-audio-001", "message": "ok"}'
        mock_response.json.return_value = {"event_id": "evt-audio-001", "message": "ok"}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        # ── Pipeline ─────────────────────────────────────────────────────────
        capture = AudioCapture(device_index=0, sample_rate=16000, chunk_duration=8.0)
        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )

        # Start audio stream
        started = await capture.start_stream()
        assert started is True

        # Read audio chunk
        chunk = await capture.read_chunk()
        assert chunk is not None
        assert isinstance(chunk, np.ndarray)

        # Encode and send
        audio_base64 = base64.b64encode(chunk.tobytes()).decode("utf-8")
        result = await sender.send_audio_trigger(
            camera_id="cam-audio-001",
            audio_base64=audio_base64,
            timestamp=1234567890.0,
        )

        assert result.success is True
        assert result.event_id == "evt-audio-001"

        # Cleanup
        await capture.stop_stream()
        await sender.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Health Check → Reconnect
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheckAndReconnect:
    """Tests the health check and reconnection logic."""

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_health_check_then_reconnect(
        self,
        mock_httpx_cls: MagicMock,
    ) -> None:
        """Test: Health check fails → buffer events → health check passes → flush."""
        from connect.buffer.local_queue import LocalQueue

        mock_client = MagicMock()
        mock_client.is_closed = False

        # Health check responses: first fail, then succeed
        mock_get = AsyncMock(side_effect=[
            MagicMock(status_code=503),  # First health check fails
            MagicMock(status_code=200),  # Second health check succeeds
        ])
        mock_client.get = mock_get

        # POST responses
        mock_post = AsyncMock(return_value=MagicMock(
            status_code=200,
            content=b'{"event_id": "evt-hc-001", "message": "ok"}',
            json=lambda: {"event_id": "evt-hc-001", "message": "ok"},
        ))
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()
        mock_httpx_cls.return_value = mock_client

        sender = TriggerSender(
            api_base_url="https://api.visionos.test",
            auth_token="test-token",
        )
        queue = LocalQueue(db_path=":memory:", max_events=100, ttl_hours=48)

        # First health check fails
        healthy = await sender.check_health()
        assert healthy is False

        # Buffer an event
        queue.enqueue({
            "type": "frame",
            "camera_id": "cam-hc-001",
            "image_base64": "base64data",
            "timestamp": 1234567890.0,
        })

        # Second health check succeeds
        healthy = await sender.check_health()
        assert healthy is True

        # Flush buffered events
        sent = await queue.flush_to_server(sender)
        assert sent == 1

        queue.close()
        await sender.close()
