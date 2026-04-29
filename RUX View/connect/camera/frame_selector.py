"""Frame Selector — selects the best frame from a burst of N frames.

Scoring prioritises person-shaped contours (aspect ratio 0.3–1.5).
If no person contours found, falls back to highest overall edge density.
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
PERSON_ASPECT_MIN = 0.3
PERSON_ASPECT_MAX = 1.5
CANNY_THRESHOLD_1 = 50
CANNY_THRESHOLD_2 = 150


def select_best_frame(frames: list[bytes]) -> bytes:
    """Select the best frame from a burst of N frames.

    Scoring: largest person-shaped contour area wins.
    If no person contours found, pick frame with highest overall edge density.

    Args:
        frames: List of JPEG byte arrays (from read_burst).

    Returns:
        Best JPEG frame bytes.

    Raises:
        ValueError: If frames list is empty.
    """
    if not frames:
        raise ValueError("Cannot select best frame from empty list")

    if len(frames) == 1:
        return frames[0]

    best_frame: Optional[bytes] = None
    best_score: float = -1.0
    all_zero_scores = True

    for frame_bytes in frames:
        score = _score_frame(frame_bytes)
        if score > 0:
            all_zero_scores = False
        if score > best_score:
            best_score = score
            best_frame = frame_bytes

    # If all frames scored 0 (no person contours), fall back to edge density
    if all_zero_scores and best_frame is not None:
        logger.debug("No person contours found, falling back to edge density")
        return _select_by_edge_density(frames)

    # best_frame should never be None since frames is non-empty
    assert best_frame is not None
    return best_frame


def _score_frame(jpeg_bytes: bytes) -> float:
    """Score a frame by person-shaped contour area.

    1. Decode JPEG to numpy array
    2. Convert to grayscale
    3. Apply Canny edge detection
    4. Find contours
    5. Filter by aspect ratio (person-like: 0.3–1.5 width/height)
    6. Return sum of filtered contour areas

    Args:
        jpeg_bytes: JPEG-encoded frame bytes.

    Returns:
        Sum of person-shaped contour areas (float).
    """
    # Decode JPEG to numpy array
    np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        logger.warning("Failed to decode JPEG frame")
        return 0.0

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply Canny edge detection
    edges = cv2.Canny(gray, CANNY_THRESHOLD_1, CANNY_THRESHOLD_2)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by person-like aspect ratio and sum areas
    total_area = 0.0
    for contour in contours:
        if _person_aspect_ratio(contour):
            area = cv2.contourArea(contour)
            total_area += area

    return total_area


def _person_aspect_ratio(contour: np.ndarray) -> bool:
    """Check if contour aspect ratio matches a person (0.3–1.5).

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


def _select_by_edge_density(frames: list[bytes]) -> bytes:
    """Fallback: pick frame with highest overall edge density.

    Computes mean edge pixel intensity from Canny edge detection
    and returns the frame with the highest mean (most detail).

    Args:
        frames: List of JPEG byte arrays.

    Returns:
        Frame with highest edge density.
    """
    best_frame = frames[0]
    best_density = -1.0

    for frame_bytes in frames:
        np_arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, CANNY_THRESHOLD_1, CANNY_THRESHOLD_2)
        density = float(np.mean(edges))

        if density > best_density:
            best_density = density
            best_frame = frame_bytes

    return best_frame
