"""Tests for Motion Detector (Sprint 2.2).

All tests use synthetic frames — no real cameras required.
"""

import asyncio
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from connect.camera.motion_detector import (
    MotionDetector,
    MotionResult,
    THRESHOLDS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def motion_detector() -> MotionDetector:
    """Create a MotionDetector with default (indoor) mode."""
    return MotionDetector(mode="indoor")


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Create a minimal valid JPEG byte array (solid gray)."""
    frame = np.ones((200, 200, 3), dtype=np.uint8) * 128
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert success, "Failed to encode test JPEG"
    return encoded.tobytes()


@pytest.fixture
def diff_jpeg_bytes() -> bytes:
    """Create a JPEG with a large white rectangle (high diff)."""
    frame = np.ones((200, 200, 3), dtype=np.uint8) * 128
    # Draw a large white rectangle to create significant pixel diff
    cv2.rectangle(frame, (20, 20), (180, 180), (255, 255, 255), -1)
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert success, "Failed to encode diff JPEG"
    return encoded.tobytes()


# ═══════════════════════════════════════════════════════════════════════════════
# Motion Detector Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMotionDetector:
    """Tests for MotionDetector motion detection logic."""

    # ── No Motion ──────────────────────────────────────────────────────────

    async def test_no_motion_returns_false(
        self,
        motion_detector: MotionDetector,
        sample_jpeg_bytes: bytes,
    ) -> None:
        """Test that identical consecutive frames return no trigger."""
        # First call stores the frame as baseline
        result1 = await motion_detector.process(sample_jpeg_bytes)
        assert result1.should_trigger is False
        assert result1.pixel_diff == 0
        assert result1.diff_category == "skip"

        # Second call with same frame — no motion
        result2 = await motion_detector.process(sample_jpeg_bytes)
        assert result2.should_trigger is False
        assert result2.pixel_diff == 0
        assert result2.diff_category == "skip"

    # ── Large Motion ───────────────────────────────────────────────────────

    async def test_large_motion_returns_true(
        self,
        motion_detector: MotionDetector,
        sample_jpeg_bytes: bytes,
        diff_jpeg_bytes: bytes,
    ) -> None:
        """Test that a significantly different frame triggers motion."""
        # First call: baseline
        await motion_detector.process(sample_jpeg_bytes)

        # Second call: frame with large white rectangle
        result = await motion_detector.process(diff_jpeg_bytes)
        assert result.should_trigger is True
        assert result.pixel_diff > 0
        assert result.diff_category in ("check", "gemma", "urgent")
        assert result.contour_count > 0

    # ── Ignore Zones ───────────────────────────────────────────────────────

    async def test_ignore_zone_masks_motion(self) -> None:
        """Test that motion inside an ignore zone is masked out."""
        # Create detector with an ignore zone covering the entire frame
        detector = MotionDetector(mode="indoor", ignore_zones=[[0, 0, 200, 200]])

        # Create two different frames
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1

        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 255
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success2

        # Baseline
        await detector.process(encoded1.tobytes())

        # Different frame, but entire frame is in ignore zone
        result = await detector.process(encoded2.tobytes())
        assert result.should_trigger is False
        assert result.pixel_diff == 0

    async def test_ignore_zone_partial_masking(self) -> None:
        """Test that only the ignore zone portion is masked."""
        # Ignore zone covers only the left half
        detector = MotionDetector(mode="indoor", ignore_zones=[[0, 0, 100, 200]])

        # Frame 1: solid gray
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1

        # Frame 2: white rectangle on the right half (outside ignore zone)
        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame2, (120, 20), (190, 180), (255, 255, 255), -1)
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success2

        # Baseline
        await detector.process(encoded1.tobytes())

        # Motion on the right (outside ignore zone) should still trigger
        result = await detector.process(encoded2.tobytes())
        assert result.should_trigger is True
        assert result.pixel_diff > 0

    # ── Aspect Ratio Filtering ─────────────────────────────────────────────

    async def test_aspect_ratio_filters_wide_objects(self) -> None:
        """Test that wide (non-person-like) contours are filtered out."""
        detector = MotionDetector(mode="indoor")

        # Frame 1: solid gray
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1

        # Frame 2: wide horizontal bar (aspect ratio ~2.0, not person-like)
        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame2, (10, 90), (190, 110), (255, 255, 255), -1)
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success2

        # Baseline
        await detector.process(encoded1.tobytes())

        # Wide bar should be filtered out by aspect ratio
        result = await detector.process(encoded2.tobytes())
        # Pixel diff exists, but no person-like contours
        assert result.contour_count == 0
        # should_trigger depends on pixel_diff category
        # The wide bar creates ~4000 diff pixels which is >= check threshold
        # But contour_count=0 means no person-like shapes detected
        # The trigger is based on pixel_diff, not contour count
        # So it may still trigger — that's by design (pixel diff is the primary signal)

    async def test_aspect_ratio_accepts_tall_objects(self) -> None:
        """Test that tall (person-like) contours pass aspect ratio filter."""
        detector = MotionDetector(mode="indoor")

        # Frame 1: solid gray
        frame1 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success1, encoded1 = cv2.imencode(".jpg", frame1, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success1

        # Frame 2: tall vertical rectangle (aspect ratio ~0.5, person-like)
        # w=60, h=120 → aspect=0.5, within 0.3–1.5 range
        frame2 = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame2, (70, 40), (130, 160), (255, 255, 255), -1)
        success2, encoded2 = cv2.imencode(".jpg", frame2, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success2

        # Baseline
        await detector.process(encoded1.tobytes())

        # Tall bar should pass aspect ratio filter
        result = await detector.process(encoded2.tobytes())
        assert result.contour_count > 0
        assert result.largest_contour_area > 0

    # ── Diff Categories ────────────────────────────────────────────────────

    async def test_diff_categories_per_mode(self) -> None:
        """Test all diff categories (skip, gemma, urgent) for indoor mode.

        Note: In all modes, check=gemma (same threshold value), so
        the "check" category is unreachable — anything >= check/gemma
        threshold is categorised as "gemma" (checked first).
        """
        base = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success, encoded_base = cv2.imencode(".jpg", base, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        # Test "skip" — very small change (below 400)
        det_skip = MotionDetector(mode="indoor")
        await det_skip.process(encoded_base.tobytes())
        frame_skip = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame_skip, (95, 95), (105, 105), (200, 200, 200), -1)
        success, enc_skip = cv2.imencode(".jpg", frame_skip, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success
        result = await det_skip.process(enc_skip.tobytes())
        assert result.diff_category == "skip"
        assert result.should_trigger is False

        # Test "gemma" — moderate change (between 2500 and 7000)
        # 50x50 white rectangle → ~2601 px diff (>= indoor gemma=2500)
        det_gemma = MotionDetector(mode="indoor")
        await det_gemma.process(encoded_base.tobytes())
        frame_gemma = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame_gemma, (75, 75), (125, 125), (255, 255, 255), -1)
        success, enc_gemma = cv2.imencode(".jpg", frame_gemma, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success
        result = await det_gemma.process(enc_gemma.tobytes())
        assert result.diff_category == "gemma"
        assert result.should_trigger is True

        # Test "urgent" — large change (above 7000)
        det_urgent = MotionDetector(mode="indoor")
        await det_urgent.process(encoded_base.tobytes())
        frame_urgent = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(frame_urgent, (10, 10), (190, 190), (255, 255, 255), -1)
        success, enc_urgent = cv2.imencode(".jpg", frame_urgent, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success
        result = await det_urgent.process(enc_urgent.tobytes())
        assert result.diff_category == "urgent"
        assert result.should_trigger is True

    # ── Mode Threshold Comparison ──────────────────────────────────────────

    async def test_outdoor_higher_threshold(self) -> None:
        """Test that outdoor mode requires more pixel diff to trigger."""
        indoor_detector = MotionDetector(mode="indoor")
        outdoor_detector = MotionDetector(mode="outdoor")

        # Create a moderate-diff frame pair
        base = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success, enc_base = cv2.imencode(".jpg", base, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        # Use a 45x45 white rectangle → ~2025 px diff
        # Indoor check=2500 → 2025 < 2500 → "skip" for indoor too!
        # Need diff between indoor check=2500 and outdoor check=4000
        # Use 55x55 → ~3025 px diff
        diff_frame = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(diff_frame, (72, 72), (127, 127), (255, 255, 255), -1)
        success, enc_diff = cv2.imencode(".jpg", diff_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        # Indoor: should trigger (diff ~3025 > indoor check=2500)
        await indoor_detector.process(enc_base.tobytes())
        indoor_result = await indoor_detector.process(enc_diff.tobytes())

        # Outdoor: should NOT trigger (diff ~3025 < outdoor check=4000)
        await outdoor_detector.process(enc_base.tobytes())
        outdoor_result = await outdoor_detector.process(enc_diff.tobytes())

        assert indoor_result.should_trigger is True
        assert outdoor_result.should_trigger is False
        assert indoor_result.diff_category in ("check", "gemma")
        assert outdoor_result.diff_category == "skip"

    async def test_night_lowest_threshold(self) -> None:
        """Test that night mode has the lowest thresholds."""
        night_detector = MotionDetector(mode="night")
        indoor_detector = MotionDetector(mode="indoor")

        base = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success, enc_base = cv2.imencode(".jpg", base, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        # Use a 30x30 white rectangle → ~961 px diff
        # Night check=2000 → 961 < 2000 → "skip" for night
        # Indoor check=2500 → 961 < 2500 → "skip" for indoor
        # Both should be "skip" — this test verifies night has lower
        # thresholds by checking the threshold values directly
        small_diff = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(small_diff, (85, 85), (115, 115), (255, 255, 255), -1)
        success, enc_diff = cv2.imencode(".jpg", small_diff, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        await night_detector.process(enc_base.tobytes())
        night_result = await night_detector.process(enc_diff.tobytes())

        await indoor_detector.process(enc_base.tobytes())
        indoor_result = await indoor_detector.process(enc_diff.tobytes())

        # Both should be "skip" for this small diff
        assert night_result.diff_category == "skip"
        assert indoor_result.diff_category == "skip"

        # Verify night thresholds are lower than indoor
        assert THRESHOLDS["night"]["check"] < THRESHOLDS["indoor"]["check"]
        assert THRESHOLDS["night"]["urgent"] < THRESHOLDS["indoor"]["urgent"]

    # ── Contour Filtering ──────────────────────────────────────────────────

    async def test_contour_filter_min_area(self) -> None:
        """Test that tiny contours are filtered out by min_area."""
        detector = MotionDetector(mode="indoor")

        base = np.ones((200, 200, 3), dtype=np.uint8) * 128
        success, enc_base = cv2.imencode(".jpg", base, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        # Frame with a tiny 5x5 pixel change (area=25, below min_area=100)
        tiny_diff = np.ones((200, 200, 3), dtype=np.uint8) * 128
        cv2.rectangle(tiny_diff, (97, 97), (102, 102), (255, 255, 255), -1)
        success, enc_diff = cv2.imencode(".jpg", tiny_diff, [cv2.IMWRITE_JPEG_QUALITY, 85])
        assert success

        await detector.process(enc_base.tobytes())
        result = await detector.process(enc_diff.tobytes())

        # Pixel diff exists but tiny contour should be filtered out
        assert result.pixel_diff > 0
        assert result.contour_count == 0

    # ── Reset ──────────────────────────────────────────────────────────────

    async def test_reset_clears_previous_frame(
        self,
        motion_detector: MotionDetector,
        sample_jpeg_bytes: bytes,
        diff_jpeg_bytes: bytes,
    ) -> None:
        """Test that reset() clears the previous frame."""
        # First call: baseline
        await motion_detector.process(sample_jpeg_bytes)

        # Reset clears the previous frame
        motion_detector.reset()

        # After reset, the next frame becomes the new baseline (no motion)
        result = await motion_detector.process(diff_jpeg_bytes)
        assert result.should_trigger is False
        assert result.pixel_diff == 0
        assert result.diff_category == "skip"

    # ── Invalid Mode ───────────────────────────────────────────────────────

    def test_invalid_mode_raises_error(self) -> None:
        """Test that an invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            MotionDetector(mode="invalid_mode")

    # ── Mode Property ──────────────────────────────────────────────────────

    def test_mode_property(self) -> None:
        """Test that mode property returns the correct mode."""
        detector = MotionDetector(mode="parking")
        assert detector.mode == "parking"

    # ── Thresholds Property ────────────────────────────────────────────────

    def test_thresholds_property(self) -> None:
        """Test that thresholds property returns correct values."""
        detector = MotionDetector(mode="outdoor")
        expected = THRESHOLDS["outdoor"]
        assert detector.thresholds == expected

    # ── Multiple Modes ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("mode", ["indoor", "outdoor", "parking", "shop", "night"])
    async def test_all_modes_accept_valid_mode(self, mode: str) -> None:
        """Test that all five modes are accepted."""
        detector = MotionDetector(mode=mode)
        assert detector.mode == mode

    # ── Edge Cases ─────────────────────────────────────────────────────────

    async def test_empty_jpeg_returns_no_motion(
        self,
        motion_detector: MotionDetector,
    ) -> None:
        """Test that an empty/invalid JPEG returns no motion."""
        result = await motion_detector.process(b"")
        assert result.should_trigger is False
        assert result.pixel_diff == 0
        assert result.diff_category == "skip"

    async def test_first_frame_always_no_motion(
        self,
        motion_detector: MotionDetector,
        sample_jpeg_bytes: bytes,
    ) -> None:
        """Test that the first frame always returns no motion (baseline)."""
        result = await motion_detector.process(sample_jpeg_bytes)
        assert result.should_trigger is False
        assert result.pixel_diff == 0
