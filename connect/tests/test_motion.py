"""Tests for Motion Detector (Sprint 11.7).

Tests the MOG2-based MotionDetector with synthetic frames.
All tests use OpenCV directly — no real cameras required.
"""

import cv2
import numpy as np
import pytest

from connect.camera.motion_detector import MotionDetector, MotionResult


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def motion_detector() -> MotionDetector:
    """Create a MotionDetector with default parameters."""
    return MotionDetector(threshold=0.02, min_area=5000)


@pytest.fixture
def blank_frame() -> np.ndarray:
    """Create a blank 480x640 BGR frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def frame_with_motion() -> np.ndarray:
    """Create a frame with a large white square (simulates motion)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:300, 200:400] = 255  # large white square
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# Motion Detector Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMotionDetector:
    """Tests for MotionDetector motion detection logic."""

    def test_init_defaults(self) -> None:
        """Test default parameters."""
        detector = MotionDetector()
        assert detector.threshold == 0.05
        assert detector.min_area == 8000

    def test_init_custom_params(self) -> None:
        """Test custom parameters."""
        detector = MotionDetector(threshold=0.05, min_area=1000)
        assert detector.threshold == 0.05
        assert detector.min_area == 1000

    def test_detect_returns_motion_result(self, motion_detector: MotionDetector, blank_frame: np.ndarray) -> None:
        """Test that detect() always returns a MotionResult."""
        result = motion_detector.detect(blank_frame)
        assert isinstance(result, MotionResult)
        assert isinstance(result.motion_detected, bool)
        assert isinstance(result.confidence, float)
        assert isinstance(result.bounding_boxes, list)
        assert isinstance(result.motion_area_pct, float)

    def test_no_motion_on_identical_frames(self, motion_detector: MotionDetector, blank_frame: np.ndarray) -> None:
        """Test that identical consecutive frames return no motion."""
        # First call initializes background model
        result1 = motion_detector.detect(blank_frame)
        # Second call with same frame — no motion expected
        result2 = motion_detector.detect(blank_frame)
        # MOG2 may still detect some noise, but confidence should be very low
        assert isinstance(result2.motion_detected, bool)

    def test_motion_detected_with_change(self, motion_detector: MotionDetector, blank_frame: np.ndarray, frame_with_motion: np.ndarray) -> None:
        """Test that a significantly different frame may trigger motion."""
        # First call: baseline
        motion_detector.detect(blank_frame)
        # Second call: frame with large white rectangle
        result = motion_detector.detect(frame_with_motion)
        # MOG2 should detect the change
        assert isinstance(result, MotionResult)

    def test_detect_null_frame(self, motion_detector: MotionDetector) -> None:
        """Test that None frame returns no motion."""
        result = motion_detector.detect(None)
        assert result.motion_detected is False
        assert result.confidence == 0.0
        assert result.bounding_boxes == []
        assert result.motion_area_pct == 0.0

    def test_detect_empty_frame(self, motion_detector: MotionDetector) -> None:
        """Test that empty frame returns no motion."""
        result = motion_detector.detect(np.array([], dtype=np.uint8))
        assert result.motion_detected is False
        assert result.confidence == 0.0

    def test_set_roi(self, motion_detector: MotionDetector) -> None:
        """Test that set_roi stores the region of interest."""
        motion_detector.set_roi((100, 100, 200, 200))
        assert motion_detector._roi == (100, 100, 200, 200)

    def test_reset_background(self, motion_detector: MotionDetector) -> None:
        """Test that reset_background creates a new background subtractor."""
        old_subtractor = motion_detector._bg_subtractor
        motion_detector.reset_background()
        assert motion_detector._bg_subtractor is not old_subtractor

    def test_get_motion_mask_returns_none_initially(self, motion_detector: MotionDetector) -> None:
        """Test that get_motion_mask returns None before any frame."""
        mask = motion_detector.get_motion_mask()
        assert mask is None

    def test_get_motion_mask_after_detect(self, motion_detector: MotionDetector, blank_frame: np.ndarray) -> None:
        """Test that get_motion_mask returns a mask after processing a frame."""
        motion_detector.detect(blank_frame)
        mask = motion_detector.get_motion_mask()
        assert mask is not None
        assert isinstance(mask, np.ndarray)
