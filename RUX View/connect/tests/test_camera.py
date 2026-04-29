"""Tests for RTSP Reader and Frame Selector (Sprint 2.1).

All tests use mocking — no real RTSP cameras required.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from connect.camera.frame_selector import (
    _person_aspect_ratio,
    _score_frame,
    select_best_frame,
)
from connect.camera.rtsp_reader import RTSPReader


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def rtsp_reader() -> RTSPReader:
    """Create an RTSPReader instance for testing."""
    return RTSPReader(
        rtsp_url="rtsp://admin:pass@192.168.1.100:554/stream1",
        camera_id="test-cam-001",
        reconnect_delay=1,
    )


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Create a minimal valid JPEG byte array for testing."""
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 200
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert success, "Failed to encode test JPEG"
    return encoded.tobytes()


# ═══════════════════════════════════════════════════════════════════════════════
# RTSP Reader Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRTSPReader:
    """Tests for RTSPReader connection and frame reading."""

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_rtsp_connection_local(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test successful RTSP connection."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc.return_value = mock_cap

        result = await rtsp_reader.connect()

        assert result is True
        assert rtsp_reader.is_connected is True
        mock_vc.assert_called_once_with(rtsp_reader.rtsp_url)

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_invalid_rtsp_url_raises_error(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test connection failure with invalid RTSP URL."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc.return_value = mock_cap

        result = await rtsp_reader.connect()

        assert result is False
        assert rtsp_reader.is_connected is False

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_reconnect_on_drop(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test reconnection after connection drop with exponential backoff."""
        # First call to connect fails, second succeeds
        mock_cap_fail = MagicMock()
        mock_cap_fail.isOpened.return_value = False

        mock_cap_success = MagicMock()
        mock_cap_success.isOpened.return_value = True

        mock_vc.side_effect = [mock_cap_fail, mock_cap_success]

        # First connect fails
        result = await rtsp_reader.connect()
        assert result is False

        # Reconnect should succeed on second attempt
        result = await rtsp_reader.reconnect()
        assert result is True
        assert rtsp_reader.is_connected is True

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_reconnect_exhausts_retries(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test reconnect raises ConnectionError after exhausting retries."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc.return_value = mock_cap

        # First connect fails
        await rtsp_reader.connect()

        # Reconnect should exhaust all retries and raise
        with pytest.raises(ConnectionError, match="failed to reconnect"):
            await rtsp_reader.reconnect()

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_jpeg_encoding(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_frame returns valid JPEG bytes."""
        # Create a synthetic frame
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, frame)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        jpeg_bytes = await rtsp_reader.read_frame()

        assert jpeg_bytes is not None
        assert isinstance(jpeg_bytes, bytes)
        assert len(jpeg_bytes) > 0
        # JPEG files start with FF D8
        assert jpeg_bytes[:2] == b"\xff\xd8"

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_read_burst_returns_n_frames(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_burst returns exactly N frames."""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, frame)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        burst = await rtsp_reader.read_burst(n_frames=5)

        assert len(burst) == 5
        for f in burst:
            assert isinstance(f, bytes)
            assert f[:2] == b"\xff\xd8"

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_empty_frames_returns_none(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_frame returns None when no frame available."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        result = await rtsp_reader.read_frame()

        assert result is None

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_disconnect_releases_resource(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that disconnect releases the VideoCapture."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        assert rtsp_reader.is_connected is True

        await rtsp_reader.disconnect()
        assert rtsp_reader.is_connected is False
        mock_cap.release.assert_called_once()

    @patch("connect.camera.rtsp_reader.cv2.VideoCapture")
    async def test_read_frame_when_not_connected(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_frame returns None when not connected."""
        result = await rtsp_reader.read_frame()
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Frame Selector Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFrameSelector:
    """Tests for frame selection logic."""

    def test_select_best_frame_single_frame(self, sample_jpeg_bytes: bytes) -> None:
        """Test that single frame is returned as-is."""
        result = select_best_frame([sample_jpeg_bytes])
        assert result == sample_jpeg_bytes

    def test_select_best_frame_empty_list(self) -> None:
        """Test that empty list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot select best frame from empty list"):
            select_best_frame([])

    def test_select_best_frame_picks_highest_score(self) -> None:
        """Test that frame with highest person-contour score is selected."""
        # Create frames with different content
        # Frame 1: blank (low score)
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        # Frame 2: has a person-like vertical rectangle (high score)
        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        # Draw a person-like contour (tall rectangle, aspect ~0.4)
        cv2.rectangle(frame2, (80, 20), (120, 180), (255, 255, 255), -1)

        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1 and success2

        frames = [encoded1.tobytes(), encoded2.tobytes()]
        result = select_best_frame(frames)

        # Frame 2 should be selected (has person-like contour)
        assert result == encoded2.tobytes()

    def test_score_frame_returns_float(self, sample_jpeg_bytes: bytes) -> None:
        """Test that _score_frame returns a non-negative float."""
        score = _score_frame(sample_jpeg_bytes)
        assert isinstance(score, float)
        assert score >= 0.0

    def test_person_aspect_ratio_valid(self) -> None:
        """Test that a person-like contour passes aspect ratio check."""
        # Create a tall rectangle contour (person-like)
        contour = np.array([
            [[0, 0]], [[30, 0]], [[30, 100]], [[0, 100]],
        ], dtype=np.int32)
        assert _person_aspect_ratio(contour) is True

    def test_person_aspect_ratio_invalid(self) -> None:
        """Test that a wide contour fails aspect ratio check."""
        # Create a wide rectangle contour (not person-like)
        contour = np.array([
            [[0, 0]], [[200, 0]], [[200, 50]], [[0, 50]],
        ], dtype=np.int32)
        assert _person_aspect_ratio(contour) is False

    def test_person_aspect_ratio_zero_height(self) -> None:
        """Test that zero-height contour returns False."""
        contour = np.array([
            [[0, 0]], [[10, 0]], [[10, 0]], [[0, 0]],
        ], dtype=np.int32)
        assert _person_aspect_ratio(contour) is False

    def test_select_best_frame_fallback_edge_density(self) -> None:
        """Test fallback to edge density when no person contours found."""
        # Create two frames with different edge densities
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)  # blank (low edges)
        frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 255  # white (more edges)

        # Add noise to frame2 for higher edge density
        noise = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        frame2 = cv2.addWeighted(frame2, 0.5, noise, 0.5, 0)

        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1 and success2

        frames = [encoded1.tobytes(), encoded2.tobytes()]
        result = select_best_frame(frames)

        # Frame 2 (noisy) should have higher edge density
        assert result == encoded2.tobytes()
