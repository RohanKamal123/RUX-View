"""
Tests for Sprint 3.4 — Cross-Camera + Ghost Detection + Repeat Sightings.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.cross_camera import (
    CrossCameraCorrelator,
    CrossCameraResult,
    GhostCheckResult,
)
from backend.core.ghost_detector import GhostDetector, GhostAlert
from backend.core.repeat_sighting import RepeatSightingTracker


class TestCrossCameraCorrelator:
    @pytest.mark.asyncio
    async def test_no_db_factory_returns_no_match(self):
        """Without DB factory, correlate should return no match."""
        correlator = CrossCameraCorrelator(db_session_factory=None)
        result = await correlator.correlate_across_cameras(
            person_uid="PERSON_001",
            source_camera_id="cam-001",
            location_id="loc-001",
            event_timestamp=datetime.now(timezone.utc),
        )
        assert result.matched is False

    def test_impossible_timing_flagged(self):
        """Impossible timing should be detected."""
        correlator = CrossCameraCorrelator()
        topology = {
            "transit_times": {"cam-001→cam-002": 30},
        }
        impossible = correlator._detect_impossible_timing(
            time_gap=5,  # 5 seconds gap, minimum is 30
            cam_a="cam-001",
            cam_b="cam-002",
            topology=topology,
        )
        assert impossible is True

    def test_possible_timing_not_flagged(self):
        """Reasonable timing should not be flagged."""
        correlator = CrossCameraCorrelator()
        topology = {
            "transit_times": {"cam-001→cam-002": 10},
        }
        impossible = correlator._detect_impossible_timing(
            time_gap=30,  # 30 seconds gap, minimum is 10
            cam_a="cam-001",
            cam_b="cam-002",
            topology=topology,
        )
        assert impossible is False

    def test_get_neighbour_cameras(self):
        """Neighbour cameras should be returned from topology."""
        correlator = CrossCameraCorrelator()
        topology = {
            "neighbours": {
                "cam-001": ["cam-002", "cam-003"],
            }
        }
        neighbours = correlator._get_neighbour_cameras("cam-001", topology)
        assert "cam-002" in neighbours
        assert "cam-003" in neighbours

    def test_get_neighbour_cameras_empty(self):
        """Non-existent camera should return empty list."""
        correlator = CrossCameraCorrelator()
        neighbours = correlator._get_neighbour_cameras("cam-999", {})
        assert neighbours == []


class TestGhostDetector:
    @pytest.mark.asyncio
    async def test_track_entry_adds_person(self):
        """track_entry should add person to tracking."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", now)
        assert detector.tracked_count == 1

    @pytest.mark.asyncio
    async def test_ghost_alert_fires_at_10_min(self):
        """MEDIUM alert should fire after 10 minutes."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        # Set entry to 11 minutes ago
        entry_time = now - timedelta(minutes=11)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", entry_time)

        alerts = await detector.check_unaccounted()
        assert len(alerts) >= 1
        medium_alerts = [a for a in alerts if a.alert_level == "MEDIUM"]
        assert len(medium_alerts) >= 1
        assert medium_alerts[0].person_uid == "PERSON_001"

    @pytest.mark.asyncio
    async def test_ghost_alert_fires_at_30_min(self):
        """HIGH alert should fire after 30 minutes."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        # Set entry to 31 minutes ago
        entry_time = now - timedelta(minutes=31)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", entry_time)

        alerts = await detector.check_unaccounted()
        high_alerts = [a for a in alerts if a.alert_level == "HIGH"]
        assert len(high_alerts) >= 1

    @pytest.mark.asyncio
    async def test_ghost_cancelled_on_sighting(self):
        """cancel_ghost should remove person from tracking."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", now)
        assert detector.tracked_count == 1

        cancelled = await detector.cancel_ghost("PERSON_001")
        assert cancelled is True
        assert detector.tracked_count == 0

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_false(self):
        """Cancelling a non-existent tracking should return False."""
        detector = GhostDetector()
        cancelled = await detector.cancel_ghost("PERSON_999")
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_record_exit_cancels_ghost(self):
        """record_exit should cancel ghost tracking."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", now)
        await detector.record_exit("PERSON_001", "cam-002", now)
        assert detector.tracked_count == 0

    @pytest.mark.asyncio
    async def test_no_alert_before_threshold(self):
        """No alert should fire before 10 minutes."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        # Set entry to 5 minutes ago
        entry_time = now - timedelta(minutes=5)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", entry_time)

        alerts = await detector.check_unaccounted()
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_active_entries_property(self):
        """active_entries should return unresolved entries."""
        detector = GhostDetector()
        now = datetime.now(timezone.utc)
        await detector.track_entry("PERSON_001", "cam-001", "loc-001", now)
        await detector.track_entry("PERSON_002", "cam-002", "loc-001", now)
        await detector.cancel_ghost("PERSON_001")

        active = detector.active_entries
        assert len(active) == 1
        assert active[0].person_uid == "PERSON_002"


class TestRepeatSightingTracker:
    @pytest.mark.asyncio
    async def test_first_sighting_returns_none(self):
        """First sighting should return 'none'."""
        tracker = RepeatSightingTracker()
        level = await tracker.record_sighting(
            "PERSON_001", "user-001", datetime.now(timezone.utc)
        )
        assert level == "none"

    @pytest.mark.asyncio
    async def test_second_sighting_returns_low(self):
        """Second sighting should return 'low'."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now)
        level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=1))
        assert level == "low"

    @pytest.mark.asyncio
    async def test_third_sighting_returns_medium(self):
        """Third sighting should return 'medium'."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now)
        await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=1))
        level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=2))
        assert level == "medium"

    @pytest.mark.asyncio
    async def test_fourth_sighting_returns_high(self):
        """Fourth sighting should return 'high'."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        for i in range(3):
            await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=i))
        level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=3))
        assert level == "high"

    @pytest.mark.asyncio
    async def test_repeat_escalation_1st_to_4th(self):
        """Full escalation chain should work correctly."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        hours = [0, 1, 2, 3]

        levels = []
        for i, h in enumerate(hours):
            level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=h))
            levels.append(level)

        assert levels == ["none", "low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_repeat_resets_after_6_hours(self):
        """Sighting count should reset after 6 hours of no sighting."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now)
        await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=1))

        # should_reset uses datetime.now() internally, so we need to
        # set last_seen to 7 hours before now
        record_key = "PERSON_001:user-001"
        record = tracker._records[record_key]
        record.last_seen = datetime.now(timezone.utc) - timedelta(hours=7)

        level = await tracker.record_sighting("PERSON_001", "user-001", datetime.now(timezone.utc))
        # Should reset and start from "none"
        assert level == "none"
        count = await tracker.get_today_count("PERSON_001", "user-001")
        assert count == 1

    @pytest.mark.asyncio
    async def test_repeat_never_resets_at_night(self):
        """Night hours should NOT reset the count."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now, is_night=True)
        await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=1), is_night=True)

        # 7 hours later should NOT reset (is_night=True prevents reset)
        level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=8), is_night=True)
        assert level != "none"  # Should escalate, not reset

    @pytest.mark.asyncio
    async def test_night_escalates_faster(self):
        """Night hours should escalate faster (2nd = medium)."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now, is_night=True)
        level = await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(minutes=5), is_night=True)
        assert level == "medium"  # 2nd sighting at night → medium

    @pytest.mark.asyncio
    async def test_get_today_count(self):
        """get_today_count should return correct count."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now)
        await tracker.record_sighting("PERSON_001", "user-001", now + timedelta(hours=1))
        count = await tracker.get_today_count("PERSON_001", "user-001")
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_today_count_nonexistent(self):
        """get_today_count for unknown person should return 0."""
        tracker = RepeatSightingTracker()
        count = await tracker.get_today_count("PERSON_999", "user-999")
        assert count == 0

    def test_is_night_hours(self):
        """is_night_hours should correctly identify night time."""
        tracker = RepeatSightingTracker()
        # 3 AM should be night
        night_time = datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        assert tracker.is_night_hours(night_time) is True

        # 3 PM should be day
        day_time = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        assert tracker.is_night_hours(day_time) is False

    @pytest.mark.asyncio
    async def test_total_tracked(self):
        """total_tracked should return count of unique person-user pairs."""
        tracker = RepeatSightingTracker()
        now = datetime.now(timezone.utc)
        await tracker.record_sighting("PERSON_001", "user-001", now)
        await tracker.record_sighting("PERSON_002", "user-001", now)
        await tracker.record_sighting("PERSON_001", "user-002", now)
        assert tracker.total_tracked == 3
