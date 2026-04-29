"""
indoor_mode.py — Indoor camera mode parameters and detection logic.

Indoor mode has lower thresholds (closer quarters, less ambient motion).
Night mode halves cooldown and uses faster burst intervals.
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

NIGHT_TIMING_PARAMS = TimingParams(
    cooldown=8,
    burst_interval=1.5,
    urgent_interval=0.8,
    no_motion_timeout=4,
    max_cap_duration=60,
)

LOITER_PARAMS = LoiterParams(
    low_seconds=60,
    medium_seconds=180,
    high_seconds=300,
)


# ── Public API ─────────────────────────────────────────────────


def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for the given mode.

    Args:
        mode: Camera mode string (indoor/outdoor/parking/shop).

    Returns:
        MotionParams with skip/check/gemma/urgent thresholds.
    """
    if mode == "indoor":
        return MOTION_PARAMS
    if mode == "outdoor":
        from backend.modes.outdoor_mode import MOTION_PARAMS as OP
        return OP
    if mode == "parking":
        from backend.modes.parking_mode import MOTION_PARAMS as PP
        return PP
    if mode == "shop":
        from backend.modes.shop_mode import MOTION_PARAMS as SP
        return SP
    # Fallback to indoor
    return MOTION_PARAMS


def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for the given mode.

    If is_night=True, cooldown is halved and burst is faster.

    Args:
        mode: Camera mode string.
        is_night: Whether night mode is active.

    Returns:
        TimingParams.
    """
    if is_night:
        return NIGHT_TIMING_PARAMS
    return TIMING_PARAMS


def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers.

    Args:
        mode: Camera mode.
        location_type: front_gate/parking_others/parking_afterhrs/indoor_general.

    Returns:
        LoiterParams with low/medium/high thresholds in seconds.
    """
    from backend.modes.outdoor_mode import LOITER_PARAMS as OUTDOOR_LOITER
    from backend.modes.parking_mode import LOITER_PARAMS as PARKING_LOITER

    loiter_map = {
        "front_gate": OUTDOOR_LOITER,
        "parking_others": PARKING_LOITER,
        "parking_afterhrs": LoiterParams(low_seconds=15, medium_seconds=30, high_seconds=60),
        "indoor_general": LOITER_PARAMS,
    }
    return loiter_map.get(location_type, LOITER_PARAMS)


def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Check if individual person analysis should be performed.

    Returns:
        True for indoor/parking, False for outdoor public zone.
    """
    if mode == "outdoor":
        return False
    if mode == "mixed" and zone == "public":
        return False
    return True


def is_night_time(current_time: datetime | None = None,
                  night_start: str = "22:00",
                  night_end: str = "06:00") -> bool:
    """Check if current time is within night hours.

    Args:
        current_time: Datetime to check (defaults to now).
        night_start: Night start time as "HH:MM".
        night_end: Night end time as "HH:MM".

    Returns:
        True if current time is within night hours.
    """
    if current_time is None:
        current_time = datetime.now()

    now_time = current_time.time()
    start_parts = night_start.split(":")
    end_parts = night_end.split(":")
    start = time(int(start_parts[0]), int(start_parts[1]))
    end = time(int(end_parts[0]), int(end_parts[1]))

    if start <= end:
        # Night range doesn't cross midnight (unusual but handle)
        return start <= now_time <= end
    # Night range crosses midnight (e.g., 22:00 to 06:00)
    return now_time >= start or now_time <= end


def get_night_params() -> dict:
    """Get night-specific parameter overrides.

    Returns:
        Dict with night timing overrides.
    """
    return {
        "cooldown": NIGHT_TIMING_PARAMS.cooldown,
        "burst_interval": NIGHT_TIMING_PARAMS.burst_interval,
        "no_motion_timeout": NIGHT_TIMING_PARAMS.no_motion_timeout,
    }
