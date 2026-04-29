"""
outdoor_mode.py — Outdoor camera mode parameters and detection logic.

Outdoor mode has higher thresholds (more ambient motion: trees, animals, traffic).
Uses MOG2 background subtractor for statistical motion detection.
Supports gate line-crossing counter (centroid-based).
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

MOTION_PARAMS = MotionParams(
    skip_threshold=800,
    check_threshold=4000,
    gemma_threshold=4000,
    urgent_threshold=10000,
)

TIMING_PARAMS = TimingParams(
    cooldown=30,
    burst_interval=2.5,
    urgent_interval=0.8,
    no_motion_timeout=6,
    max_cap_duration=60,
)

LOITER_PARAMS = LoiterParams(
    low_seconds=45,
    medium_seconds=120,
    high_seconds=240,
)


# ── Public API ─────────────────────────────────────────────────


def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for outdoor mode."""
    return MOTION_PARAMS


def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for outdoor mode.

    If is_night=True, cooldown is halved and burst is faster.
    """
    if is_night:
        return TimingParams(
            cooldown=15,
            burst_interval=1.5,
            urgent_interval=0.8,
            no_motion_timeout=6,
            max_cap_duration=60,
        )
    return TIMING_PARAMS


def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers for outdoor/front_gate."""
    return LOITER_PARAMS


def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Outdoor mode does NOT analyse individuals (crowd/public space)."""
    return False


def get_mog2_params() -> dict:
    """Get MOG2 background subtractor parameters.

    Returns:
        Dict with history, varThreshold, detectShadows.
    """
    return {
        "history": 500,
        "varThreshold": 36,
        "detectShadows": True,
    }


def get_crowd_thresholds() -> dict:
    """Get crowd anomaly detection thresholds.

    Returns:
        Dict with person_count_threshold and motion_density_threshold.
    """
    return {
        "person_count_threshold": 10,
        "motion_density_threshold": 0.4,
    }


def get_gate_line_crossing_params() -> dict:
    """Get gate line-crossing detection parameters.

    Returns:
        Dict with line_coordinates and direction_tracking_enabled.
    """
    return {
        "line_coordinates": [0.5, 0.0, 0.5, 1.0],  # vertical center line
        "direction_tracking_enabled": True,
    }
