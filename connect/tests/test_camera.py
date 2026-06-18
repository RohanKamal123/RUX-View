"""Tests for RTSP Reader and Frame Selector (Sprint 11.7).

All tests use mocking — no real RTSP cameras required.
RTSPReader.read_frame() returns np.ndarray (BGR frame), not JPEG bytes.
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
from connect.camera.rtsp_reader import RTSPReader, StreamInfo


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
def sample_frame() -> np.ndarray:
    """Create a synthetic BGR frame for testing."""
    return np.ones((480, 640, 3), dtype=np.uint8) * 128


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Create a minimal valid JPEG byte array for testing frame_selector."""
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 200
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert success, "Failed to encode test JPEG"
    return encoded.tobytes()


# ═══════════════════════════════════════════════════════════════════════════════
# RTSP Reader Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRTSPReader:
    """Tests for RTSPReader connection and frame reading."""

    def test_init_stores_params(self) -> None:
        """__init__ should store camera parameters."""
        reader = RTSPReader("rtsp://test:554/stream1", "cam_001", reconnect_delay=3)
        assert reader.rtsp_url == "rtsp://test:554/stream1"
        assert reader.camera_id == "cam_001"
        assert reader.reconnect_delay == 3

    def test_is_connected_returns_false_initially(self, rtsp_reader: RTSPReader) -> None:
        """is_connected should return False before connect."""
        assert rtsp_reader.is_connected() is False

    def test_get_stream_info_returns_none_initially(self, rtsp_reader: RTSPReader) -> None:
        """get_stream_info should return None before connect."""
        assert rtsp_reader.get_stream_info() is None

    async def test_release_does_not_crash(self, rtsp_reader: RTSPReader) -> None:
        """release should not crash when called before connect."""
        await rtsp_reader.release()  # Should not raise

    @patch("cv2.VideoCapture")
    async def test_connect_success(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test successful RTSP connection."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FOURCC: 828601953,  # H264 fourcc code
        }.get(prop, 0)
        mock_vc.return_value = mock_cap

        result = await rtsp_reader.connect()

        assert result is True
        assert rtsp_reader.is_connected() is True
        mock_vc.assert_called_once_with(rtsp_reader.rtsp_url)

    @patch("cv2.VideoCapture")
    async def test_connect_failure(
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
        assert rtsp_reader.is_connected() is False

    @patch("cv2.VideoCapture")
    async def test_read_frame_returns_numpy_array(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
        sample_frame: np.ndarray,
    ) -> None:
        """Test that read_frame returns a numpy array (BGR frame)."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, sample_frame)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        frame = await rtsp_reader.read_frame()

        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (480, 640, 3)

    @patch("cv2.VideoCapture")
    async def test_read_frame_returns_none_on_failure(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_frame returns None when read fails."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        result = await rtsp_reader.read_frame()

        assert result is None

    @patch("cv2.VideoCapture")
    async def test_read_frame_raises_when_not_connected(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that read_frame raises ConnectionError when not connected."""
        with pytest.raises(ConnectionError, match="is not connected"):
            await rtsp_reader.read_frame()

    @patch("cv2.VideoCapture")
    async def test_reconnect(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test reconnection after connection drop."""
        mock_cap_fail = MagicMock()
        mock_cap_fail.isOpened.return_value = False

        mock_cap_success = MagicMock()
        mock_cap_success.isOpened.return_value = True

        mock_vc.side_effect = [mock_cap_fail, mock_cap_success]

        # First connect fails
        result = await rtsp_reader.connect()
        assert result is False

        # Reconnect should succeed
        result = await rtsp_reader.reconnect()
        assert result is True
        assert rtsp_reader.is_connected() is True

    @patch("cv2.VideoCapture")
    async def test_release(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that release cleans up the VideoCapture."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        assert rtsp_reader.is_connected() is True

        await rtsp_reader.release()
        assert rtsp_reader.is_connected() is False
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    async def test_stream_info(
        self,
        mock_vc: MagicMock,
        rtsp_reader: RTSPReader,
    ) -> None:
        """Test that stream info is populated after connect."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_WIDTH: 1920,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080,
            cv2.CAP_PROP_FPS: 25.0,
            cv2.CAP_PROP_FOURCC: 828601953,  # H264 fourcc code
        }.get(prop, 0)
        mock_vc.return_value = mock_cap

        await rtsp_reader.connect()
        info = rtsp_reader.get_stream_info()

        assert info is not None
        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == 25.0
        assert info.is_connected is True


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
        # Frame 1: blank (low score)
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        # Frame 2: has a person-like vertical rectangle (high score)
        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 128
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
        contour = np.array([
            [[0, 0]], [[30, 0]], [[30, 100]], [[0, 100]],
        ], dtype=np.int32)
        assert _person_aspect_ratio(contour) is True

    def test_person_aspect_ratio_invalid(self) -> None:
        """Test that a wide contour fails aspect ratio check."""
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
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)  # blank (low edges)
        frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 255  # white

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
