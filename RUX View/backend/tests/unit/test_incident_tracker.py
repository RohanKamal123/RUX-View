"""
Tests for Sprint 3.1 — Incident Tracker.

Tests the state machine: IDLE → TRACKING → CLOSE
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.incident_tracker import (
    CamState,
    IncidentAction,
    IncidentTracker,
    TriggerData,
)


def _make_trigger(camera_id: str = "cam-001",
                  pixel_diff: int = 3000,
                  diff_category: str = "check",
                  seconds_ago: float = 0) -> TriggerData:
    """Helper to create a TriggerData with a relative timestamp."""
    return TriggerData(
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
        pixel_diff=pixel_diff,
        diff_category=diff_category,
    )


class TestIncidentTracker:
    @pytest.mark.asyncio
    async def test_idle_transitions_to_tracking_on_trigger(self):
        """IDLE → TRACKING when a non-skip trigger arrives."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")

        action = await tracker.process(trigger)

        assert tracker.current_state == CamState.TRACKING
        assert action == IncidentAction.GEMMA_CALL
        assert tracker.incident_id.startswith("INC-")

    @pytest.mark.asyncio
    async def test_idle_ignores_low_diff(self):
        """IDLE stays IDLE when diff_category is 'skip'."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        trigger = _make_trigger(pixel_diff=100, diff_category="skip")

        action = await tracker.process(trigger)

        assert tracker.current_state == CamState.IDLE
        assert action == IncidentAction.NONE

    @pytest.mark.asyncio
    async def test_tracking_closes_on_no_motion(self):
        """TRACKING → CLOSE when no motion for no_motion_timeout seconds."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        # Start incident
        trigger1 = _make_trigger(pixel_diff=3000, diff_category="check", seconds_ago=10)
        await tracker.process(trigger1)
        assert tracker.current_state == CamState.TRACKING

        # Set last_motion_time to 10 seconds before the trigger we're about to send
        trigger2_ts = datetime.now(timezone.utc)
        trigger2 = TriggerData(
            camera_id="cam-001",
            timestamp=trigger2_ts,
            pixel_diff=3000,
            diff_category="check",
        )
        # Set last_motion_time to 10 seconds before trigger timestamp
        tracker._state.last_motion_time = trigger2_ts - timedelta(seconds=10)

        action = await tracker.process(trigger2)
        assert action == IncidentAction.CLOSE_INCIDENT

    @pytest.mark.asyncio
    async def test_burst_fires_at_correct_interval(self):
        """Urgent threshold triggers BURST action."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        trigger = _make_trigger(pixel_diff=7000, diff_category="urgent")

        # Start incident
        await tracker.process(trigger)
        assert tracker.current_state == CamState.TRACKING

        # Another urgent trigger should give BURST
        trigger2 = _make_trigger(pixel_diff=8000, diff_category="urgent", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert action == IncidentAction.BURST

    @pytest.mark.asyncio
    async def test_loitering_escalates_at_correct_times(self):
        """Loitering escalation should progress through levels."""
        tracker = IncidentTracker("cam-001", mode="indoor", location_type="indoor_general")

        # Start incident
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")
        await tracker.process(trigger)

        # Simulate loitering by setting start_time far in past
        now = datetime.now(timezone.utc)
        tracker._state.start_time = now - timedelta(seconds=70)
        tracker._state.last_motion_time = now

        # Process another trigger — should escalate to low
        trigger2 = _make_trigger(pixel_diff=3000, diff_category="check", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert tracker._state.last_loiter_escalation == "low"

    @pytest.mark.asyncio
    async def test_night_mode_halves_cooldown(self):
        """Night mode should use night timing params."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        tracker.set_night_mode(True)

        timing = tracker._get_timing_params()
        assert timing["cooldown"] == 8  # night cooldown
        assert timing["burst"] == 1.5  # night burst

    @pytest.mark.asyncio
    async def test_max_cap_closes_incident(self):
        """Max cap duration should close the incident."""
        tracker = IncidentTracker("cam-001", mode="indoor")

        # Start incident
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")
        await tracker.process(trigger)

        # Set start_time far in the past (beyond max_cap=60)
        # Also set loiter escalation to "high" so loiter check doesn't fire first
        tracker._state.start_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        tracker._state.last_loiter_escalation = "high"

        trigger2 = _make_trigger(pixel_diff=3000, diff_category="check", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert action == IncidentAction.CLOSE_INCIDENT

    @pytest.mark.asyncio
    async def test_gemma_skip_on_no_change(self):
        """GEMMA_CALL should not fire if cooldown hasn't elapsed."""
        tracker = IncidentTracker("cam-001", mode="indoor")

        # Start incident
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")
        await tracker.process(trigger)  # This gives GEMMA_CALL

        # Immediately process another — cooldown hasn't elapsed
        trigger2 = _make_trigger(pixel_diff=3000, diff_category="check", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert action == IncidentAction.NONE

    @pytest.mark.asyncio
    async def test_urgent_overrides_cooldown(self):
        """Urgent threshold should override cooldown and return BURST."""
        tracker = IncidentTracker("cam-001", mode="indoor")

        # Start incident
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")
        await tracker.process(trigger)

        # Immediately send urgent — should get BURST despite cooldown
        trigger2 = _make_trigger(pixel_diff=7000, diff_category="urgent", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert action == IncidentAction.BURST

    @pytest.mark.asyncio
    async def test_loiter_front_gate_escalation_times(self):
        """Front gate loitering should use correct escalation times."""
        tracker = IncidentTracker("cam-001", mode="outdoor", location_type="front_gate")

        # Start incident
        trigger = _make_trigger(pixel_diff=4000, diff_category="check")
        await tracker.process(trigger)

        # Set start_time to 50 seconds ago (past low=45, below medium=120)
        now = datetime.now(timezone.utc)
        tracker._state.start_time = now - timedelta(seconds=50)
        tracker._state.last_motion_time = now

        trigger2 = _make_trigger(pixel_diff=4000, diff_category="check", seconds_ago=0)
        action = await tracker.process(trigger2)
        assert tracker._state.last_loiter_escalation == "low"

    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """Reset should return to IDLE with no incident."""
        tracker = IncidentTracker("cam-001", mode="indoor")
        trigger = _make_trigger(pixel_diff=3000, diff_category="check")
        await tracker.process(trigger)
        assert tracker.current_state == CamState.TRACKING

        tracker.reset()
        assert tracker.current_state == CamState.IDLE
        assert tracker.incident_id == ""
