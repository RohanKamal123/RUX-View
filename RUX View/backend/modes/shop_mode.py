"""
shop_mode.py — Shop camera mode parameters and detection logic.

Shop mode has indoor-like thresholds with business hours awareness.
During business hours: loitering is disabled (normal customer behaviour).
After hours: switches to night/security mode with full alerting.
Supports staff entrance zones (no alert for staff during business hours).
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
    cooldown=10,
    burst_interval=2.5,
    urgent_interval=0.8,
    no_motion_timeout=3,
    max_cap_duration=300,
)

LOITER_PARAMS = LoiterParams(
    low_seconds=60,
    medium_seconds=180,
    high_seconds=300,
)


# ── Public API ─────────────────────────────────────────────────


def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for shop mode."""
    return MOTION_PARAMS


def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for shop mode.

    If is_night=True, cooldown is halved and burst is faster.
    """
    if is_night:
        return TimingParams(
            cooldown=5,
            burst_interval=1.5,
            urgent_interval=0.8,
            no_motion_timeout=3,
            max_cap_duration=300,
        )
    return TIMING_PARAMS


def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers for shop mode."""
    return LOITER_PARAMS


def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Shop mode analyses individuals (customer counting, theft detection)."""
    return True


def get_business_hours(shop_hours_open: str = "09:00",
                       shop_hours_close: str = "21:00") -> dict:
    """Get business hours configuration.

    Args:
        shop_hours_open: Opening time as "HH:MM".
        shop_hours_close: Closing time as "HH:MM".

    Returns:
        Dict with open, close, is_open_now.
    """
    now = datetime.now()
    now_time = now.time()

    open_parts = shop_hours_open.split(":")
    close_parts = shop_hours_close.split(":")
    open_time = time(int(open_parts[0]), int(open_parts[1]))
    close_time = time(int(close_parts[0]), int(close_parts[1]))

    if open_time <= close_time:
        is_open = open_time <= now_time <= close_time
    else:
        # Crosses midnight (e.g., 22:00 to 06:00)
        is_open = now_time >= open_time or now_time <= close_time

    return {
        "open": shop_hours_open,
        "close": shop_hours_close,
        "is_open_now": is_open,
    }


def is_staff_entrance(zone: str) -> bool:
    """Check if zone is a staff-only entrance.

    Args:
        zone: Zone name/identifier.

    Returns:
        True if zone is a staff-only entrance.
    """
    staff_zones = {"staff_entrance", "staff_only", "back_office", "storage"}
    return zone.lower() in staff_zones if zone else False


def get_after_hours_params() -> dict:
    """Get after-hours security mode parameters (same as night mode).

    Returns:
        Dict with after-hours timing overrides.
    """
    return {
        "cooldown": 5,
        "burst_interval": 1.5,
        "no_motion_timeout": 3,
        "max_cap_duration": 300,
        "loitering_enabled": True,
        "staff_entrance_alert": True,
    }
