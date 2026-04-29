"""
incident_tracker.py — Per-camera incident state machine.

State machine: IDLE → TRACKING → CLOSE
- IDLE: Gemma OFF, cost $0
- TRACKING: Gemma ON, burst every 2.5s when behaviour changes
- CLOSE: Send full timeline to Gemini, route alert, save to DB

Timing parameters vary by camera mode.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class CamState(Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    CLOSE = "close"


class IncidentAction(Enum):
    GEMMA_CALL = "gemma_call"
    BURST = "burst"
    CLOSE_INCIDENT = "close_incident"
    NONE = "none"


@dataclass
class TriggerData:
    camera_id: str
    timestamp: datetime
    pixel_diff: int
    diff_category: str  # skip/check/gemma/urgent
    jpeg_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    yamnet_result: Optional[dict] = None


@dataclass
class IncidentState:
    incident_id: str
    state: CamState = CamState.IDLE
    start_time: Optional[datetime] = None
    last_gemma_time: Optional[datetime] = None
    last_motion_time: Optional[datetime] = None
    last_loiter_escalation: str = "none"  # none/low/medium/high
    timeline: list = field(default_factory=list)
    burst_count: int = 0
    person_ids: list = field(default_factory=list)


# ── Timing Parameters by Mode ──────────────────────────────────

TIMING = {
    "indoor":  {"cooldown": 15, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 60},
    "outdoor": {"cooldown": 30, "burst": 2.5, "urgent": 0.8, "no_motion": 6, "max_cap": 60},
    "parking": {"cooldown": 20, "burst": 2.5, "urgent": 0.8, "no_motion": 4, "max_cap": 120},
    "shop":    {"cooldown": 10, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 300},
    "night":   {"cooldown": 8,  "burst": 1.5, "urgent": 0.8, "no_motion": 4, "max_cap": 60},
}

# Pixel diff thresholds by mode
THRESHOLDS = {
    "indoor":  {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "outdoor": {"skip": 800, "check": 4000, "gemma": 4000, "urgent": 10000},
    "parking": {"skip": 600, "check": 3500, "gemma": 3500, "urgent": 9000},
    "night":   {"skip": 300, "check": 2000, "gemma": 2000, "urgent": 5000},
}

# Loitering escalation timers by location type
LOITER = {
    "front_gate":       {"low": 45, "medium": 120, "high": 240},
    "parking_others":   {"low": 45, "medium": 90, "high": 150},
    "parking_afterhrs": {"low": 15, "medium": 30, "high": 60},
    "indoor_general":   {"low": 60, "medium": 180, "high": 300},
}


class IncidentTracker:
    """Per-camera incident state machine."""

    def __init__(self, camera_id: str, mode: str = "indoor",
                 location_type: str = "indoor_general"):
        """Initialize tracker for a camera.

        Args:
            camera_id: Unique camera identifier.
            mode: Camera mode (indoor/outdoor/parking/shop).
            location_type: For loiter params (front_gate/parking_others/etc).
        """
        self.camera_id = camera_id
        self.mode = mode
        self.location_type = location_type
        self._state = IncidentState(incident_id="")
        self._night_mode = False

    async def process(self, trigger: TriggerData) -> IncidentAction:
        """Process a motion trigger through the state machine.

        Args:
            trigger: TriggerData with motion detection results.

        Returns:
            IncidentAction indicating what the pipeline should do next.
        """
        # Add to timeline
        self._state.timeline.append({
            "timestamp": trigger.timestamp.isoformat(),
            "pixel_diff": trigger.pixel_diff,
            "diff_category": trigger.diff_category,
        })

        # IDLE state
        if self._state.state == CamState.IDLE:
            # Skip low diff triggers
            if trigger.diff_category == "skip":
                return IncidentAction.NONE

            # Transition to tracking
            action = self._transition_idle_to_tracking(trigger)
            self._state.last_motion_time = trigger.timestamp
            return action

        # TRACKING state
        if self._state.state == CamState.TRACKING:
            action = self._process_tracking(trigger)
            # Update last motion time AFTER processing (so no_motion check works)
            self._state.last_motion_time = trigger.timestamp
            return action

        # CLOSE state — ignore new triggers until reset
        return IncidentAction.NONE

    def _transition_idle_to_tracking(self, trigger: TriggerData) -> IncidentAction:
        """IDLE → TRACKING: Start new incident, return GEMMA_CALL."""
        self._state.incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        self._state.state = CamState.TRACKING
        self._state.start_time = trigger.timestamp
        self._state.last_gemma_time = trigger.timestamp
        self._state.burst_count = 0
        self._state.last_loiter_escalation = "none"
        self._state.person_ids = []

        return IncidentAction.GEMMA_CALL

    def _process_tracking(self, trigger: TriggerData) -> IncidentAction:
        """TRACKING state logic.

        Priority order:
        1. No-motion timeout → CLOSE_INCIDENT
        2. Urgent threshold → BURST (override cooldown)
        3. Cooldown elapsed → GEMMA_CALL
        4. Loitering escalation → GEMMA_CALL
        5. Max cap duration → CLOSE_INCIDENT
        6. Otherwise → NONE
        """
        now = trigger.timestamp
        timing = self._get_timing_params()
        thresholds = self._get_thresholds()

        # Calculate time since last motion
        if self._state.last_motion_time:
            no_motion_sec = (now - self._state.last_motion_time).total_seconds()
        else:
            no_motion_sec = 0

        # Calculate incident duration
        if self._state.start_time:
            duration_sec = (now - self._state.start_time).total_seconds()
        else:
            duration_sec = 0

        # 1. Check no-motion timeout → CLOSE
        if no_motion_sec >= timing["no_motion"]:
            return IncidentAction.CLOSE_INCIDENT

        # 2. Check urgent threshold → BURST (override cooldown)
        if trigger.pixel_diff >= thresholds["urgent"]:
            self._state.burst_count += 1
            return IncidentAction.BURST

        # 3. Check cooldown elapsed → GEMMA_CALL
        if self._state.last_gemma_time:
            gemma_elapsed = (now - self._state.last_gemma_time).total_seconds()
        else:
            gemma_elapsed = timing["cooldown"] + 1  # Force call

        if gemma_elapsed >= timing["cooldown"]:
            self._state.last_gemma_time = now
            return IncidentAction.GEMMA_CALL

        # 4. Check loitering escalation (monotonic: only escalates upward)
        escalation = self._check_loiter_escalation()
        if escalation:
            return IncidentAction.GEMMA_CALL

        # 5. Check max cap duration → CLOSE
        if duration_sec >= timing["max_cap"]:
            return IncidentAction.CLOSE_INCIDENT

        # 6. Otherwise → NONE
        return IncidentAction.NONE

    def _check_loiter_escalation(self) -> Optional[str]:
        """Check if loitering time has crossed escalation threshold.

        Escalation is monotonic: none → low → medium → high.
        Only escalates upward, never downward.

        Returns:
            New escalation level or None.
        """
        if not self._state.start_time or not self._state.last_motion_time:
            return None

        loiter_params = LOITER.get(self.location_type, LOITER["indoor_general"])
        duration = (self._state.last_motion_time - self._state.start_time).total_seconds()

        current = self._state.last_loiter_escalation
        level_order = ["none", "low", "medium", "high"]
        current_idx = level_order.index(current)

        thresholds = [
            ("low", loiter_params["low"]),
            ("medium", loiter_params["medium"]),
            ("high", loiter_params["high"]),
        ]

        new_level = current
        for level_name, threshold_sec in thresholds:
            if duration >= threshold_sec:
                new_level = level_name

        # Only escalate upward (monotonic)
        new_idx = level_order.index(new_level)
        if new_idx > current_idx:
            self._state.last_loiter_escalation = new_level
            return new_level

        return None

    def _get_timing_params(self) -> dict:
        """Get timing parameters for current mode."""
        mode_key = "night" if self._night_mode else self.mode
        return TIMING.get(mode_key, TIMING["indoor"])

    def _get_thresholds(self) -> dict:
        """Get pixel diff thresholds for current mode."""
        mode_key = "night" if self._night_mode else self.mode
        return THRESHOLDS.get(mode_key, THRESHOLDS["indoor"])

    def set_night_mode(self, is_night: bool) -> None:
        """Enable or disable night mode (halves cooldown, faster burst)."""
        self._night_mode = is_night

    def reset(self) -> None:
        """Reset tracker to IDLE state."""
        self._state = IncidentState(incident_id="")

    @property
    def current_state(self) -> CamState:
        """Get current state."""
        return self._state.state

    @property
    def incident_duration(self) -> float:
        """Get incident duration in seconds."""
        if self._state.start_time and self._state.last_motion_time:
            return (self._state.last_motion_time - self._state.start_time).total_seconds()
        return 0.0

    @property
    def incident_id(self) -> str:
        """Get current incident ID."""
        return self._state.incident_id

    @property
    def timeline(self) -> list:
        """Get incident timeline."""
        return self._state.timeline

    @property
    def person_ids(self) -> list:
        """Get person IDs associated with this incident."""
        return self._state.person_ids

    @person_ids.setter
    def person_ids(self, ids: list) -> None:
        self._state.person_ids = ids
