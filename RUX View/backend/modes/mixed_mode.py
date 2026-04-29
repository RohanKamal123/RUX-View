"""
mixed_mode.py — Mixed camera mode (public + property zones).

Mixed mode splits the camera view into public zone and property zone.
Public zone uses outdoor logic (no individual analysis).
Property zone uses indoor logic (full analysis).
Supports zone-crossing detection for people moving from public to property.
"""

from dataclasses import dataclass


@dataclass
class MotionParams:
    skip_threshold: int
    check_threshold: int
    gemma_threshold: int
    urgent_threshold: int


@dataclass
class TimingParams:
    cooldown: int
    burst_interval: float
    urgent_interval: float
    no_motion_timeout: int
    max_cap_duration: int


@dataclass
class LoiterParams:
    low_seconds: int
    medium_seconds: int
    high_seconds: int


# ── Default Parameters ────────────────────────────────────────
# Mixed mode uses indoor thresholds by default (property zone is primary)

MOTION_PARAMS = MotionParams(
    skip_threshold=400,
    check_threshold=2500,
    gemma_threshold=2500,
    urgent_threshold=7000,
)

TIMING_PARAMS = TimingParams(
    cooldown=15,
    burst_interval=2.5,
    urgent_interval=0.8,
    no_motion_timeout=3,
    max_cap_duration=60,
)

LOITER_PARAMS = LoiterParams(
    low_seconds=60,
    medium_seconds=180,
    high_seconds=300,
)


# ── Public API ─────────────────────────────────────────────────


def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for mixed mode."""
    return MOTION_PARAMS


def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for mixed mode.

    If is_night=True, cooldown is halved and burst is faster.
    """
    if is_night:
        return TimingParams(
            cooldown=8,
            burst_interval=1.5,
            urgent_interval=0.8,
            no_motion_timeout=4,
            max_cap_duration=60,
        )
    return TIMING_PARAMS


def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers for mixed mode."""
    return LOITER_PARAMS


def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Mixed mode analyses individuals only in property zone.

    Args:
        zone: "public" or "property". If None, defaults to True.
    """
    if zone == "public":
        return False
    return True


def get_zone_config() -> dict:
    """Get zone-based split configuration.

    Returns:
        Dict with public_zone_coords, property_zone_coords, crossing_line.
    """
    return {
        "public_zone_coords": [0.0, 0.0, 1.0, 0.5],  # bottom half
        "property_zone_coords": [0.0, 0.5, 1.0, 1.0],  # top half
        "crossing_line": [0.0, 0.5, 1.0, 0.5],  # horizontal center
    }


def is_crossing_public_to_property(track_history: list) -> bool:
    """Check if a person crossed from public zone to property zone.

    Args:
        track_history: List of (x, y) centroid positions over time.

    Returns:
        True if the person crossed from bottom (public) to top (property).
    """
    if len(track_history) < 2:
        return False

    # Check if movement is from bottom (y > 0.5) to top (y < 0.5)
    first_y = track_history[0][1]
    last_y = track_history[-1][1]
    crossing_y = 0.5

    return first_y > crossing_y > last_y


def get_public_zone_mode() -> str:
    """Public zone uses outdoor logic only."""
    return "outdoor"
