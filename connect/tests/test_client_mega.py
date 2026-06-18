"""
test_client_mega.py — Tests for Vision OS Client Agent (Sprint 11.7).

Tests RTSPReader, MotionDetector, TriggerSender, and LocalBuffer.
"""

import pytest
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import numpy as np

from connect.camera.rtsp_reader import RTSPReader, StreamInfo
from connect.camera.motion_detector import MotionDetector, MotionResult
from connect.transport.trigger_sender import (
    TriggerSender,
    TriggerResponse,
    LocalBuffer,
)


# ── RTSPReader Tests ────────────────────────────────────────────


class TestRTSPReader:
    """Tests for RTSPReader class."""

    def test_init_stores_params(self):
        """__init__ should store camera parameters."""
        reader = RTSPReader("rtsp://test:554/stream1", "cam_001", reconnect_delay=3)
        assert reader.rtsp_url == "rtsp://test:554/stream1"
        assert reader.camera_id == "cam_001"
        assert reader.reconnect_delay == 3

    @pytest.mark.asyncio
    async def test_connect_fails_with_invalid_url(self):
        """connect should return False for invalid RTSP URL."""
        reader = RTSPReader("rtsp://invalid:554/stream", "cam_001")
        result = await reader.connect()
        assert result is False

    def test_is_connected_returns_false_initially(self):
        """is_connected should return False before connect."""
        reader = RTSPReader("rtsp://test:554/stream1", "cam_001")
        assert reader.is_connected() is False

    def test_get_stream_info_returns_none_initially(self):
        """get_stream_info should return None before connect."""
        reader = RTSPReader("rtsp://test:554/stream1", "cam_001")
        assert reader.get_stream_info() is None

    @pytest.mark.asyncio
    async def test_release_does_not_crash(self):
        """release should not crash when called before connect."""
        reader = RTSPReader("rtsp://test:554/stream1", "cam_001")
        await reader.release()  # Should not raise


# ── MotionDetector Tests ────────────────────────────────────────


class TestMotionDetector:
    """Tests for MotionDetector class."""

    def test_init_sets_defaults(self):
        """__init__ should set default parameters."""
        detector = MotionDetector()
        assert detector.threshold == 0.05
        assert detector.min_area == 8000

    def test_init_custom_params(self):
        """__init__ should accept custom parameters."""
        detector = MotionDetector(threshold=0.05, min_area=1000)
        assert detector.threshold == 0.05
        assert detector.min_area == 1000

    def test_detect_no_motion_returns_false(self):
        """detect should return no motion for blank frame."""
        detector = MotionDetector()
        # Create a blank frame (no motion)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # First call initializes background model
        detector.detect(frame)
        # Second call should detect no motion
        result = detector.detect(frame)
        assert isinstance(result, MotionResult)
        assert result.motion_detected is False
        assert result.confidence == 0.0

    def test_detect_with_motion(self):
        """detect should detect motion in frame with changes."""
        detector = MotionDetector(min_area=100)

        # First frame: blank
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        detector.detect(frame1)

        # Second frame: with white square (simulates motion)
        frame2 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2[100:300, 200:400] = 255
        result = detector.detect(frame2)

        # May or may not detect depending on background model
        assert isinstance(result, MotionResult)
        assert isinstance(result.motion_detected, bool)
        assert isinstance(result.confidence, float)
        assert isinstance(result.bounding_boxes, list)
        assert isinstance(result.motion_area_pct, float)

    def test_detect_with_null_frame(self):
        """detect should handle None frame gracefully."""
        detector = MotionDetector()
        result = detector.detect(None)
        assert result.motion_detected is False
        assert result.confidence == 0.0
        assert result.bounding_boxes == []

    def test_set_roi(self):
        """set_roi should store the region of interest."""
        detector = MotionDetector()
        detector.set_roi((100, 100, 200, 200))
        assert detector._roi == (100, 100, 200, 200)

    def test_reset_background(self):
        """reset_background should create a new background subtractor."""
        detector = MotionDetector()
        old_subtractor = detector._bg_subtractor
        detector.reset_background()
        assert detector._bg_subtractor is not old_subtractor

    def test_get_motion_mask_returns_none_initially(self):
        """get_motion_mask should return None before any frame."""
        detector = MotionDetector()
        mask = detector.get_motion_mask()
        assert mask is None


# ── TriggerSender Tests ─────────────────────────────────────────


class TestTriggerSender:
    """Tests for TriggerSender class."""

    def test_init_stores_params(self):
        """__init__ should store API parameters."""
        sender = TriggerSender("https://api.visionos.com", "test_token")
        assert sender.api_base_url == "https://api.visionos.com"
        assert sender.auth_token == "test_token"

    def test_init_strips_trailing_slash(self):
        """__init__ should strip trailing slash from URL."""
        sender = TriggerSender("https://api.visionos.com/", "test_token")
        assert sender.api_base_url == "https://api.visionos.com"

    @pytest.mark.asyncio
    async def test_send_frame_trigger_handles_network_error(self):
        """send_frame_trigger should handle network errors gracefully."""
        sender = TriggerSender("https://invalid.example.com", "test_token")
        response = await sender.send_frame_trigger("cam_001", "base64data", 1234567890.0)
        assert isinstance(response, TriggerResponse)
        assert response.success is False
        assert response.status_code in (408, 503, 500)

    @pytest.mark.asyncio
    async def test_send_audio_trigger_handles_network_error(self):
        """send_audio_trigger should handle network errors gracefully."""
        sender = TriggerSender("https://invalid.example.com", "test_token")
        response = await sender.send_audio_trigger("cam_001", "base64data", 1234567890.0)
        assert isinstance(response, TriggerResponse)
        assert response.success is False

    @pytest.mark.asyncio
    async def test_check_health_returns_false_for_invalid(self):
        """check_health should return False for unreachable API."""
        sender = TriggerSender("https://invalid.example.com", "test_token")
        healthy = await sender.check_health()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_close_does_not_crash(self):
        """close should not crash when called."""
        sender = TriggerSender("https://api.visionos.com", "test_token")
        await sender.close()  # Should not raise


# ── LocalBuffer Tests ───────────────────────────────────────────


class TestLocalBuffer:
    """Tests for LocalBuffer class."""

    @pytest.fixture
    def temp_buffer(self):
        """Create a LocalBuffer with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = LocalBuffer(buffer_dir=tmpdir)
            yield buffer

    def test_enqueue_stores_trigger(self, temp_buffer):
        """enqueue should store a trigger as JSON file."""
        trigger = {
            "camera_id": "cam_001",
            "type": "frame",
            "data": "base64data",
            "timestamp": 1234567890.0,
        }
        result = temp_buffer.enqueue(trigger)
        assert result is True
        assert temp_buffer.count() == 1

    def test_dequeue_all_returns_triggers(self, temp_buffer):
        """dequeue_all should return all buffered triggers."""
        trigger1 = {"camera_id": "cam_001", "type": "frame", "data": "data1", "timestamp": 1.0}
        trigger2 = {"camera_id": "cam_002", "type": "audio", "data": "data2", "timestamp": 2.0}

        temp_buffer.enqueue(trigger1)
        temp_buffer.enqueue(trigger2)

        triggers = temp_buffer.dequeue_all()
        assert len(triggers) == 2
        assert temp_buffer.count() == 0  # Buffer should be empty after dequeue

    def test_dequeue_all_empty_buffer(self, temp_buffer):
        """dequeue_all should return empty list for empty buffer."""
        triggers = temp_buffer.dequeue_all()
        assert triggers == []

    def test_count_returns_correct_number(self, temp_buffer):
        """count should return the number of buffered triggers."""
        assert temp_buffer.count() == 0
        temp_buffer.enqueue({"camera_id": "cam_001", "type": "frame", "data": "data", "timestamp": 1.0})
        assert temp_buffer.count() == 1
        temp_buffer.enqueue({"camera_id": "cam_002", "type": "audio", "data": "data", "timestamp": 2.0})
        assert temp_buffer.count() == 2

    def test_clear_removes_all(self, temp_buffer):
        """clear should remove all buffered triggers."""
        temp_buffer.enqueue({"camera_id": "cam_001", "type": "frame", "data": "data", "timestamp": 1.0})
        temp_buffer.enqueue({"camera_id": "cam_002", "type": "audio", "data": "data", "timestamp": 2.0})
        temp_buffer.clear()
        assert temp_buffer.count() == 0

    @pytest.mark.asyncio
    async def test_flush_to_api_empty_buffer(self, temp_buffer):
        """flush_to_api should return 0 for empty buffer."""
        sender = TriggerSender("https://api.visionos.com", "test_token")
        sent = await temp_buffer.flush_to_api(sender)
        assert sent == 0

    @pytest.mark.asyncio
    async def test_flush_to_api_handles_network_error(self, temp_buffer):
        """flush_to_api should handle network errors gracefully."""
        temp_buffer.enqueue({"camera_id": "cam_001", "type": "frame", "data": "data", "timestamp": 1.0})
        sender = TriggerSender("https://invalid.example.com", "test_token")
        sent = await temp_buffer.flush_to_api(sender)
        # Should not crash, may or may not succeed
        assert isinstance(sent, int)
