"""Tests for Sprint 8.1 — Camera Health Monitoring."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.camera_health import (
    CameraHealthMonitor,
    CameraHealth,
    HealthSnapshot,
    HealthSummary,
    HEALTH_RETENTION_DAYS,
    OFFLINE_THRESHOLD_MINUTES,
)


@pytest.fixture
def health_monitor():
    """Create a fresh CameraHealthMonitor for each test."""
    return CameraHealthMonitor()


class TestCameraHealthMonitor:
    """Tests for CameraHealthMonitor class."""

    @pytest.mark.asyncio
    async def test_record_heartbeat_updates_status(self, health_monitor):
        """Test that recording a heartbeat updates camera status."""
        await health_monitor.register_camera("cam-001", "Front Door")
        result = await health_monitor.record_heartbeat("cam-001", "online")
        assert result["camera_id"] == "cam-001"
        assert result["status"] == "online"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_camera_health_returns_correct_data(self, health_monitor):
        """Test that get_camera_health returns correct CameraHealth."""
        await health_monitor.register_camera(
            "cam-001", "Front Door", location_id="loc-001", location_name="Home"
        )
        await health_monitor.record_heartbeat("cam-001", "online")

        health = await health_monitor.get_camera_health("cam-001")
        assert health is not None
        assert health.camera_id == "cam-001"
        assert health.camera_name == "Front Door"
        assert health.status == "online"
        assert health.location_id == "loc-001"
        assert health.location_name == "Home"
        assert health.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_get_all_cameras_health_returns_list(self, health_monitor):
        """Test that get_all_cameras_health returns list of CameraHealth."""
        await health_monitor.register_camera("cam-001", "Front Door")
        await health_monitor.register_camera("cam-002", "Back Door")
        await health_monitor.record_heartbeat("cam-001", "online")
        await health_monitor.record_heartbeat("cam-002", "online")

        cameras = await health_monitor.get_all_cameras_health("user-001")
        assert len(cameras) == 2
        assert all(isinstance(c, CameraHealth) for c in cameras)

    @pytest.mark.asyncio
    async def test_offline_detection_after_threshold(self, health_monitor):
        """Test that cameras are detected as offline after threshold."""
        await health_monitor.register_camera("cam-001", "Front Door")
        await health_monitor.record_heartbeat("cam-001", "online")

        # Manually set last heartbeat far in the past
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        health_monitor._heartbeats["cam-001"]["last_heartbeat"] = past_time

        offline = await health_monitor.get_offline_cameras(threshold_minutes=5)
        assert "cam-001" in offline

    @pytest.mark.asyncio
    async def test_uptime_calculation_24h(self, health_monitor):
        """Test that uptime calculation for 24h works correctly."""
        await health_monitor.register_camera("cam-001", "Front Door")

        # Record 8 online heartbeats and 2 error heartbeats
        for _ in range(8):
            await health_monitor.record_heartbeat("cam-001", "online")
        for _ in range(2):
            await health_monitor.record_heartbeat("cam-001", "error")

        uptime = await health_monitor.get_camera_uptime(
            "cam-001", since=datetime.now(timezone.utc) - timedelta(hours=24)
        )
        assert uptime == 80.0  # 8/10 = 80%

    @pytest.mark.asyncio
    async def test_uptime_calculation_7d(self, health_monitor):
        """Test that uptime calculation for 7 days works correctly."""
        await health_monitor.register_camera("cam-001", "Front Door")

        # Record 15 online and 5 error over the period
        for _ in range(15):
            await health_monitor.record_heartbeat("cam-001", "online")
        for _ in range(5):
            await health_monitor.record_heartbeat("cam-001", "error")

        uptime = await health_monitor.get_camera_uptime(
            "cam-001", since=datetime.now(timezone.utc) - timedelta(days=7)
        )
        assert uptime == 75.0  # 15/20 = 75%

    @pytest.mark.asyncio
    async def test_error_count_24h(self, health_monitor):
        """Test that error count for 24h is correct."""
        await health_monitor.register_camera("cam-001", "Front Door")

        for _ in range(3):
            await health_monitor.record_heartbeat("cam-001", "error")

        errors = await health_monitor.get_camera_error_count(
            "cam-001", since=datetime.now(timezone.utc) - timedelta(hours=24)
        )
        assert errors == 3

    @pytest.mark.asyncio
    async def test_health_history_returns_snapshots(self, health_monitor):
        """Test that health history returns list of HealthSnapshots."""
        await health_monitor.register_camera("cam-001", "Front Door")

        for _ in range(5):
            await health_monitor.record_heartbeat("cam-001", "online")

        history = await health_monitor.get_health_history("cam-001", days=7)
        assert len(history) == 5
        assert all(isinstance(h, HealthSnapshot) for h in history)

    @pytest.mark.asyncio
    async def test_mark_offline_sets_status(self, health_monitor):
        """Test that mark_camera_offline sets status to offline."""
        await health_monitor.register_camera("cam-001", "Front Door")
        await health_monitor.record_heartbeat("cam-001", "online")

        result = await health_monitor.mark_camera_offline("cam-001", "Network issue")
        assert result["status"] == "offline"
        assert result["reason"] == "Network issue"

        health = await health_monitor.get_camera_health("cam-001")
        assert health.status == "offline"

    @pytest.mark.asyncio
    async def test_mark_online_clears_offline(self, health_monitor):
        """Test that mark_camera_online sets status to online."""
        await health_monitor.register_camera("cam-001", "Front Door")
        await health_monitor.mark_camera_offline("cam-001", "Test")

        result = await health_monitor.mark_camera_online("cam-001")
        assert result["status"] == "online"

        health = await health_monitor.get_camera_health("cam-001")
        assert health.status == "online"

    @pytest.mark.asyncio
    async def test_health_summary_aggregates_correctly(self, health_monitor):
        """Test that health summary aggregates correctly."""
        await health_monitor.register_camera("cam-001", "Front Door")
        await health_monitor.register_camera("cam-002", "Back Door")
        await health_monitor.register_camera("cam-003", "Garage")

        await health_monitor.record_heartbeat("cam-001", "online")
        await health_monitor.record_heartbeat("cam-002", "online")
        await health_monitor.record_heartbeat("cam-003", "error")

        summary = await health_monitor.get_health_summary("user-001")
        assert summary.total_cameras == 3
        assert summary.online_cameras == 2
        assert summary.offline_cameras == 0
        assert summary.error_cameras == 1
        assert summary.total_errors_24h == 1
        assert summary.last_updated is not None

    @pytest.mark.asyncio
    async def test_concurrent_heartbeat_updates(self, health_monitor):
        """Test that concurrent heartbeat updates work correctly."""
        import asyncio

        await health_monitor.register_camera("cam-001", "Front Door")

        async def send_heartbeat():
            await health_monitor.record_heartbeat("cam-001", "online")

        # Send 10 heartbeats concurrently
        tasks = [send_heartbeat() for _ in range(10)]
        await asyncio.gather(*tasks)

        history = await health_monitor.get_health_history("cam-001", days=1)
        assert len(history) == 10

    @pytest.mark.asyncio
    async def test_health_data_retention_30_days(self, health_monitor):
        """Test that health data older than 30 days is removed."""
        await health_monitor.register_camera("cam-001", "Front Door")

        # Add some recent snapshots
        for _ in range(3):
            await health_monitor.record_heartbeat("cam-001", "online")

        # Manually add old snapshots (older than 30 days)
        old_time = datetime.now(timezone.utc) - timedelta(days=31)
        old_snapshot = HealthSnapshot(
            timestamp=old_time,
            status="online",
        )
        health_monitor._health_history["cam-001"].append(old_snapshot)

        # Trigger retention enforcement
        await health_monitor._enforce_retention("cam-001")

        history = await health_monitor.get_health_history("cam-001", days=60)
        assert len(history) == 3  # Old one should be removed

    @pytest.mark.asyncio
    async def test_get_camera_health_returns_none_for_unknown(self, health_monitor):
        """Test that get_camera_health returns None for unknown camera."""
        health = await health_monitor.get_camera_health("unknown-cam")
        assert health is None

    @pytest.mark.asyncio
    async def test_register_camera_creates_entries(self, health_monitor):
        """Test that register_camera creates heartbeat and history entries."""
        result = await health_monitor.register_camera(
            "cam-001", "Front Door", "loc-001", "Home"
        )
        assert result["status"] == "registered"

        assert "cam-001" in health_monitor._heartbeats
        assert "cam-001" in health_monitor._health_history
        assert health_monitor._camera_info["cam-001"]["camera_name"] == "Front Door"
