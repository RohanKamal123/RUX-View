"""Tests for backend/core/ingest/rtmp_ingest.py's sample_frame().

Verified working against a real MediaMTX instance + a real ffmpeg RTMP
push in dev (see the module docstring) -- these are the fast, CI-safe
unit tests covering the failure paths that don't need a live media server.
"""

from unittest.mock import MagicMock, patch

from backend.core.ingest.rtmp_ingest import sample_frame


class TestSampleFrame:
    @patch("cv2.VideoCapture")
    def test_returns_none_when_stream_not_live(self, mock_vc):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc.return_value = mock_cap

        result = sample_frame("test_key", "rtsp://mediamtx:8554")

        assert result is None
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_returns_none_when_read_fails(self, mock_vc):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc.return_value = mock_cap

        result = sample_frame("test_key", "rtsp://mediamtx:8554")

        assert result is None

    @patch("cv2.imencode")
    @patch("cv2.VideoCapture")
    def test_returns_jpeg_bytes_on_success(self, mock_vc, mock_imencode):
        import numpy as np

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype="uint8"))
        mock_vc.return_value = mock_cap
        mock_imencode.return_value = (True, np.frombuffer(b"\xff\xd8\xff\xd9", dtype="uint8"))

        result = sample_frame("test_key", "rtsp://mediamtx:8554")

        assert result == b"\xff\xd8\xff\xd9"

    @patch("cv2.VideoCapture")
    def test_builds_url_from_stream_key_and_base(self, mock_vc):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc.return_value = mock_cap

        sample_frame("AB1234567_abc", "rtsp://mediamtx.internal:8554")

        mock_vc.assert_called_once_with("rtsp://mediamtx.internal:8554/live/AB1234567_abc")

    @patch("cv2.VideoCapture", side_effect=RuntimeError("decoder crashed"))
    def test_exception_returns_none_not_raises(self, mock_vc):
        assert sample_frame("test_key", "rtsp://mediamtx:8554") is None
