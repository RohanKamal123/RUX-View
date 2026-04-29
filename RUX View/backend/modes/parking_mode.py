"""
parking_mode.py — Parking camera mode parameters and detection logic.

Parking mode has medium thresholds (vehicles, people walking between cars).
Supports vehicle detection parameters and headlight detection at night.
Night mode uses faster burst intervals.
"""

from dataclasses import dataclass
from datetime import datetime, time


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
    skip_threshold=600,
    check_threshold=3500,
    gemma_threshold=3500,
    urgent_threshold=9000,
)

TIMING_PARAMS = TimingParams(
    cooldown=20,
    burst_interval=2.5,
    urgent_interval=0.8,
    no_motion_timeout=4,
    max_cap_duration=120,
)

LOITER_PARAMS = LoiterParams(
    low_seconds=45,
    medium_seconds=90,
    high_seconds=150,
)


# ── Public API ─────────────────────────────────────────────────


def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for parking mode."""
    return MOTION_PARAMS


def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for parking mode.

    If is_night=True, cooldown is halved and burst is faster.
    """
    if is_night:
        return TimingParams(
            cooldown=10,
            burst_interval=1.5,
            urgent_interval=0.8,
            no_motion_timeout=4,
            max_cap_duration=120,
        )
    return TIMING_PARAMS


def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers for parking."""
    return LOITER_PARAMS


def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Parking mode analyses individuals (potential theft/vandalism)."""
    return True


def get_vehicle_detection_params() -> dict:
    """Get vehicle detection parameters.

    Returns:
        Dict with min_vehicle_area, aspect_ratio_range, headlight_threshold.
    """
    return {
        "min_vehicle_area": 2000,
        "aspect_ratio_range": [0.8, 2.5],
        "headlight_threshold": 150,
    }


def is_night_time(current_time: datetime | None = None,
                  night_start: str = "22:00",
                  night_end: str = "06:00") -> bool:
    """Check if current time is within night hours."""
    if current_time is None:
        current_time = datetime.now()

    now_time = current_time.time()
    start_parts = night_start.split(":")
    end_parts = night_end.split(":")
    start = time(int(start_parts[0]), int(start_parts[1]))
    end = time(int(end_parts[0]), int(end_parts[1]))

    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def get_night_params() -> dict:
    """Get night-specific parameter overrides for parking.

    Returns:
        Dict with night timing overrides and headlight detection enabled.
    """
    return {
        "cooldown": 10,
        "burst_interval": 1.5,
        "no_motion_timeout": 4,
        "headlight_detection_enabled": True,
    }
