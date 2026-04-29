"""Motion Detector — pixel-diff based motion detection with zone masking.

Compares consecutive frames using pixel difference.
Supports five camera modes with per-mode thresholds.
Ignores specified zones (e.g. trees, road) via black rectangle masking.
Trigger-only architecture — no continuous streaming (D005).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Thresholds by Mode ─────────────────────────────────────────────────────────
# Each mode defines four diff levels:
#   skip   — below this: no trigger
#   check  — above skip: trigger for human review
#   gemma  — above check: trigger with Gemini analysis
#   urgent — above gemma: trigger with urgent priority
THRESHOLDS: dict[str, dict[str, int]] = {
    "indoor":  {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "outdoor": {"skip": 800, "check": 4000, "gemma": 4000, "urgent": 10000},
    "parking": {"skip": 600, "check": 3500, "gemma": 3500, "urgent": 9000},
    "shop":    {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "night":   {"skip": 300, "check": 2000, "gemma": 2000, "urgent": 5000},
}

# ── Contour Filtering Constants ────────────────────────────────────────────────
PERSON_ASPECT_MIN = 0.3
PERSON_ASPECT_MAX = 1.5
DEFAULT_MIN_AREA = 100
DIFF_THRESHOLD_VALUE = 25  # pixel intensity diff threshold for binary mask


@dataclass
class MotionResult:
    """Result of a single motion detection pass.

    Attributes:
        should_trigger: Whether this frame should trigger an event.
        pixel_diff: Total number of changed pixels (after masking).
        largest_contour_area: Area of the largest filtered contour.
        diff_category: One of "skip" / "check" / "gemma" / "urgent".
        contour_count: Number of contours that passed filtering.
    """
    should_trigger: bool
    pixel_diff: int
    largest_contour_area: int
    diff_category: str
    contour_count: int


class MotionDetector:
    """Pixel-diff based motion detector with zone masking.

    Compares consecutive frames to detect motion.
    Supports five camera modes with per-mode thresholds.
    Ignore zones mask out areas that should not trigger motion
    (e.g. trees, road, static objects).

    Usage:
        detector = MotionDetector(mode="outdoor", ignore_zones=[[0, 0, 100, 50]])
        result = await detector.process(frame_jpeg_bytes)
        if result.should_trigger:
            # handle motion event
    """

    def __init__(
        self,
        mode: str = "indoor",
        ignore_zones: Optional[list[list[int]]] = None,
    ) -> None:
        """Initialize motion detector.

        Args:
            mode: Camera mode. One of "indoor", "outdoor", "parking",
                  "shop", "night".
            ignore_zones: List of [x, y, w, h] rectangles to mask out.
                          Each rectangle defines a region to ignore.

        Raises:
            ValueError: If mode is not recognised.
        """
        if mode not in THRESHOLDS:
            valid = ", ".join(THRESHOLDS.keys())
            raise ValueError(
                f"Unknown mode '{mode}'. Valid modes: {valid}"
            )

        self._mode = mode
        self._thresholds = THRESHOLDS[mode]
        self._ignore_zones: list[list[int]] = ignore_zones or []
        self._prev_gray: Optional[np.ndarray] = None

    # ── Public API ───────────────────────────────────────────────────────────

    async def process(self, frame_jpeg: bytes) -> MotionResult:
        """Process a frame and return motion analysis.

        Pipeline:
        1. Decode JPEG to numpy array
        2. Convert to grayscale
        3. Apply ignore zone mask (black out specified regions)
        4. Compare with previous frame using absolute pixel difference
        5. Threshold diff to create binary motion mask
        6. Find contours in motion mask
        7. Filter contours by minimum area and aspect ratio
        8. Categorise diff level based on mode thresholds
        9. Store current frame as previous for next call

        Args:
            frame_jpeg: JPEG-encoded frame bytes.

        Returns:
            MotionResult with analysis results.
        """
        loop = asyncio.get_running_loop()

        # Run blocking cv2 operations in thread pool
        result = await loop.run_in_executor(None, self._process_sync, frame_jpeg)
        return result

    def apply_ignore_zones(self, frame: np.ndarray) -> np.ndarray:
        """Mask out ignore zones with black rectangles.

        Draws filled black rectangles over each ignore zone,
        effectively zeroing out those regions so they don't
        contribute to pixel diff calculations.

        Args:
            frame: Grayscale or BGR numpy array.

        Returns:
            Frame with ignore zones blacked out (modified in-place).
        """
        for zone in self._ignore_zones:
            x, y, w, h = zone
            cv2.rectangle(frame, (x, y), (x + w, y + h), 0, -1)
        return frame

    def reset(self) -> None:
        """Clear previous frame.

        Call this when the camera mode changes or when you want
        to force a fresh baseline on the next frame.
        """
        self._prev_gray = None
        logger.debug("Motion detector: previous frame cleared")

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        """Get the current camera mode."""
        return self._mode

    @property
    def thresholds(self) -> dict[str, int]:
        """Get the thresholds for the current mode."""
        return dict(self._thresholds)

    # ── Internal: Synchronous Processing ─────────────────────────────────────

    def _process_sync(self, frame_jpeg: bytes) -> MotionResult:
        """Synchronous processing pipeline (runs in thread pool)."""
        # 1. Decode JPEG to numpy array
        if not frame_jpeg:
            logger.warning("Empty JPEG bytes received")
            return MotionResult(
                should_trigger=False,
                pixel_diff=0,
                largest_contour_area=0,
                diff_category="skip",
                contour_count=0,
            )

        np_arr = np.frombuffer(frame_jpeg, dtype=np.uint8)
        frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            logger.warning("Failed to decode JPEG frame")
            return MotionResult(
                should_trigger=False,
                pixel_diff=0,
                largest_contour_area=0,
                diff_category="skip",
                contour_count=0,
            )

        # 2. Convert to grayscale
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        # 3. Apply ignore zone mask
        gray = self.apply_ignore_zones(gray)

        # 4. If no previous frame, store and return no motion
        if self._prev_gray is None:
            self._prev_gray = gray
            return MotionResult(
                should_trigger=False,
                pixel_diff=0,
                largest_contour_area=0,
                diff_category="skip",
                contour_count=0,
            )

        # 5. Compute absolute difference between frames
        diff = cv2.absdiff(self._prev_gray, gray)

        # 6. Threshold to create binary motion mask
        _, thresh = cv2.threshold(diff, DIFF_THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)

        # 7. Count total changed pixels
        pixel_diff = int(cv2.countNonZero(thresh))

        # 8. Find contours in thresholded diff
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 9. Filter contours by minimum area
        filtered = self._contour_filter(contours, min_area=DEFAULT_MIN_AREA)

        # 10. Further filter by aspect ratio (person-like shapes)
        person_contours = [c for c in filtered if self._aspect_ratio_filter(c)]

        # 11. Determine largest contour area
        largest_area = 0
        if person_contours:
            largest_area = int(max(cv2.contourArea(c) for c in person_contours))

        # 12. Categorise diff level
        category = self._categorize_diff(pixel_diff)

        # 13. Store current frame as previous for next call
        self._prev_gray = gray

        return MotionResult(
            should_trigger=(category != "skip"),
            pixel_diff=pixel_diff,
            largest_contour_area=largest_area,
            diff_category=category,
            contour_count=len(person_contours),
        )

    # ── Internal: Contour Filtering ──────────────────────────────────────────

    def _contour_filter(
        self,
        contours: list,
        min_area: int = DEFAULT_MIN_AREA,
    ) -> list:
        """Filter contours by minimum area.

        Args:
            contours: List of OpenCV contours.
            min_area: Minimum contour area in pixels (default: 100).

        Returns:
            List of contours with area >= min_area.
        """
        return [c for c in contours if cv2.contourArea(c) >= min_area]

    def _aspect_ratio_filter(self, contour: np.ndarray) -> bool:
        """Filter contours that look person-like (0.3–1.5 aspect ratio).

        Computes the bounding rectangle and checks if width/height ratio
        falls within the expected range for a standing/walking person.

        Args:
            contour: OpenCV contour array.

        Returns:
            True if aspect ratio is within person-like range.
        """
        x, y, w, h = cv2.boundingRect(contour)

        # Avoid division by zero
        if h == 0:
            return False

        aspect_ratio = w / h
        return PERSON_ASPECT_MIN <= aspect_ratio <= PERSON_ASPECT_MAX

    def _categorize_diff(self, pixel_diff: int) -> str:
        """Categorise diff level based on mode thresholds.

        Args:
            pixel_diff: Total number of changed pixels.

        Returns:
            One of "skip", "check", "gemma", "urgent".
        """
        if pixel_diff >= self._thresholds["urgent"]:
            return "urgent"
        elif pixel_diff >= self._thresholds["gemma"]:
            return "gemma"
        elif pixel_diff >= self._thresholds["check"]:
            return "check"
        else:
            return "skip"
