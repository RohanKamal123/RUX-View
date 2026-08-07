"""
motion_detector.py — Motion Detection for Vision OS Client Agent (Sprint 11.7).

Detects motion in camera frames using background subtraction.
Supports region of interest (ROI) configuration.

Stack: Python + OpenCV + numpy

Key Decisions:
- D026: All calls async
- Uses OpenCV's MOG2 background subtractor
- Configurable threshold and minimum area
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MotionResult:
    """Result of motion detection on a frame."""
    motion_detected: bool
    confidence: float
    bounding_boxes: list[Tuple[int, int, int, int]]
    motion_area_pct: float


class MotionDetector:
    """Detects motion in video frames using background subtraction.

    Uses OpenCV's MOG2 background subtractor for robust motion detection
    with configurable sensitivity and minimum area thresholds.
    """

    def __init__(self, threshold: float = 0.05, min_area: int = 8000,
                 config: Optional[dict] = None):
        """Initialize MotionDetector.

        Args:
            threshold: Motion detection sensitivity (0.0 to 1.0).
                       Lower values detect smaller motions.
            min_area: Minimum contour area in pixels to consider as motion.
            config: Optional runtime config dict (e.g. from config_store).
                    ``motion_min_area``, ``motion_threshold``,
                    ``motion_history``, ``motion_var_threshold``, and
                    ``fg_mask_threshold`` are read from it if provided.
        """
        if config is not None:
            min_area = config.get("motion_min_area", min_area)
            threshold = config.get("motion_threshold", threshold)
        self.threshold = threshold
        self.min_area = min_area
        self._history = config.get("motion_history", 500) if config else 500
        self._var_threshold = config.get("motion_var_threshold", 56) if config else 56
        self._fg_mask_threshold = config.get("fg_mask_threshold", 200) if config else 200
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self._history, varThreshold=self._var_threshold,
            detectShadows=False,
        )
        self._roi: Optional[Tuple[int, int, int, int]] = None
        self._last_frame: Optional[np.ndarray] = None

    def detect(self, frame: np.ndarray) -> MotionResult:
        """Detect motion in a frame.

        Args:
            frame: BGR image as numpy array from RTSPReader.

        Returns:
            MotionResult with detection details.
        """
        if frame is None or frame.size == 0:
            return MotionResult(
                motion_detected=False,
                confidence=0.0,
                bounding_boxes=[],
                motion_area_pct=0.0,
            )

        # Apply ROI if set
        if self._roi is not None:
            x, y, w, h = self._roi
            roi_frame = frame[y:y+h, x:x+w]
        else:
            roi_frame = frame

        # Apply background subtraction
        fg_mask = self._bg_subtractor.apply(roi_frame)

        # Apply threshold to remove noise
        _, fg_mask = cv2.threshold(
            fg_mask, self._fg_mask_threshold, 255, cv2.THRESH_BINARY,
        )

        # Apply morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter contours by area
        bounding_boxes = []
        total_motion_area = 0
        frame_area = roi_frame.shape[0] * roi_frame.shape[1]

        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Adjust coordinates if ROI is set
                if self._roi is not None:
                    x += self._roi[0]
                    y += self._roi[1]
                bounding_boxes.append((x, y, w, h))
                total_motion_area += area

        motion_area_pct = (total_motion_area / max(frame_area, 1)) * 100
        motion_detected = len(bounding_boxes) > 0

        # Calculate confidence based on motion area ratio
        confidence = min(motion_area_pct / 100.0, 1.0) if motion_detected else 0.0

        self._last_frame = frame

        return MotionResult(
            motion_detected=motion_detected,
            confidence=round(confidence, 4),
            bounding_boxes=bounding_boxes,
            motion_area_pct=round(motion_area_pct, 2),
        )

    def update_config(self, config: dict) -> None:
        """Apply updated tunables live, e.g. from connect/config_sync.py's
        periodic poll of the backend's config_store.

        ``motion_min_area``, ``motion_threshold``, and ``fg_mask_threshold``
        take effect immediately since ``detect()`` reads them from
        ``self`` on every call. ``motion_history`` and
        ``motion_var_threshold`` are baked into the MOG2 background
        subtractor at construction time, so changing either rebuilds it --
        that resets the learned background model, so the rebuild only
        happens when one of those two specifically changed.

        Args:
            config: Dict with any subset of the five keys above; missing
                keys leave the current value unchanged.
        """
        self.min_area = config.get("motion_min_area", self.min_area)
        self.threshold = config.get("motion_threshold", self.threshold)
        self._fg_mask_threshold = config.get("fg_mask_threshold", self._fg_mask_threshold)

        new_history = config.get("motion_history", self._history)
        new_var_threshold = config.get("motion_var_threshold", self._var_threshold)
        if new_history != self._history or new_var_threshold != self._var_threshold:
            self._history = new_history
            self._var_threshold = new_var_threshold
            self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=self._history, varThreshold=self._var_threshold,
                detectShadows=False,
            )
            logger.info(
                "Rebuilt MOG2 background subtractor (history=%d, varThreshold=%d)",
                self._history, self._var_threshold,
            )

    def set_roi(self, roi: Tuple[int, int, int, int]) -> None:
        """Set a region of interest for motion detection.

        Only motion within the ROI will be detected.

        Args:
            roi: Tuple of (x, y, width, height) in pixels.
        """
        self._roi = roi
        logger.info("ROI set to: x=%d, y=%d, w=%d, h=%d", *roi)

    def reset_background(self) -> None:
        """Reset the background model.

        Call this when the scene changes significantly (e.g., lighting change)
        to re-learn the background.
        """
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self._history, varThreshold=self._var_threshold,
            detectShadows=False,
        )
        logger.info("Background model reset")

    def get_motion_mask(self) -> Optional[np.ndarray]:
        """Get the current motion mask (foreground mask).

        Returns:
            Binary mask image, or None if no frame has been processed.
        """
        if self._last_frame is None:
            return None

        fg_mask = self._bg_subtractor.apply(self._last_frame)
        _, fg_mask = cv2.threshold(
            fg_mask, self._fg_mask_threshold, 255, cv2.THRESH_BINARY,
        )
        return fg_mask
