"""Tests for Sprint 8.3 — Admin Camera Management API."""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException


@pytest.fixture
def admin_user():
    """Create a mock admin user."""
    return {"id": "admin-001", "role": "admin", "email": "admin@visionos.com"}


@pytest.fixture
def non_admin_user():
    """Create a mock non-admin user."""
    return {"id": "user-001", "role": "user", "email": "user@example.com"}


class TestAdminCamerasAPI:
    """Tests for admin camera management API."""

    @pytest.mark.asyncio
    async def test_require_admin_passes_for_admin(self, admin_user):
        """Test that require_admin passes for admin users."""
        from backend.api.admin_cameras import require_admin

        result = await require_admin(admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, non_admin_user):
        """Test that non-admin users get 403."""
        from backend.api.admin_cameras import require_admin

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(non_admin_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_cameras_returns_paginated_results(self, admin_user):
        """Test that list_cameras returns paginated results."""
        from backend.api.admin_cameras import list_cameras, _camera_store

        # Add some test cameras
        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door", "user_id": "user-001"}
        _camera_store["cam-002"] = {"camera_name": "Back Door", "user_id": "user-001"}

        # Register with health monitor
        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.register_camera("cam-002", "Back Door")
        await monitor.record_heartbeat("cam-001", "online")
        await monitor.record_heartbeat("cam-002", "online")

        # Patch the health monitor
        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await list_cameras(page=1, per_page=20, admin=admin_user)
            assert "cameras" in result
            assert result["total"] == 2
            assert result["page"] == 1
            assert result["per_page"] == 20

    @pytest.mark.asyncio
    async def test_get_camera_details_includes_health(self, admin_user):
        """Test that get_camera_details includes health data."""
        from backend.api.admin_cameras import get_camera_details, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door", "user_id": "user-001"}

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.record_heartbeat("cam-001", "online")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await get_camera_details("cam-001", admin=admin_user)
            assert result["camera_id"] == "cam-001"
            assert result["camera_name"] == "Front Door"
            assert "health" in result
            assert result["health"]["status"] == "online"

    @pytest.mark.asyncio
    async def test_health_summary_returns_aggregates(self, admin_user):
        """Test that health summary returns aggregate data."""
        from backend.api.admin_cameras import get_health_summary

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.register_camera("cam-002", "Back Door")
        await monitor.record_heartbeat("cam-001", "online")
        await monitor.record_heartbeat("cam-002", "error")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await get_health_summary(admin=admin_user)
            assert result["total_cameras"] == 2
            assert result["online_cameras"] == 1
            assert result["error_cameras"] == 1

    @pytest.mark.asyncio
    async def test_offline_cameras_returns_list(self, admin_user):
        """Test that offline cameras endpoint returns list."""
        from backend.api.admin_cameras import get_offline_cameras

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.mark_camera_offline("cam-001", "Test")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await get_offline_cameras(admin=admin_user)
            assert "offline_camera_ids" in result
            assert "cam-001" in result["offline_camera_ids"]

    @pytest.mark.asyncio
    async def test_camera_health_history(self, admin_user):
        """Test that camera health history endpoint works."""
        from backend.api.admin_cameras import get_camera_health_history

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.record_heartbeat("cam-001", "online")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await get_camera_health_history("cam-001", days=7, admin=admin_user)
            assert result["camera_id"] == "cam-001"
            assert len(result["snapshots"]) >= 1

    @pytest.mark.asyncio
    async def test_camera_metrics_endpoint(self, admin_user):
        """Test that camera metrics endpoint works."""
        from backend.api.admin_cameras import get_camera_metrics

        from backend.analytics.camera_metrics import CameraMetricsCollector
        collector = CameraMetricsCollector()
        await collector.record_trigger("cam-001", 50000)
        await collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)

        with patch("backend.api.admin_cameras._get_metrics_collector", return_value=collector):
            result = await get_camera_metrics("cam-001", days=7, admin=admin_user)
            assert result["camera_id"] == "cam-001"
            assert "daily_metrics" in result
            assert "cost_breakdown" in result
            assert "bandwidth" in result

    @pytest.mark.asyncio
    async def test_bulk_enable_cameras(self, admin_user):
        """Test that bulk enable works."""
        from backend.api.admin_cameras import bulk_operation, BulkOperationRequest, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door"}

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.mark_camera_offline("cam-001", "Test")

        request = BulkOperationRequest(
            camera_ids=["cam-001"],
            operation="enable",
        )

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await bulk_operation(request, admin=admin_user)
            assert result["operation"] == "enable"
            assert result["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_bulk_disable_cameras(self, admin_user):
        """Test that bulk disable works."""
        from backend.api.admin_cameras import bulk_operation, BulkOperationRequest, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door"}

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.record_heartbeat("cam-001", "online")

        request = BulkOperationRequest(
            camera_ids=["cam-001"],
            operation="disable",
            reason="Testing",
        )

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await bulk_operation(request, admin=admin_user)
            assert result["operation"] == "disable"
            assert result["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_bulk_delete_cameras(self, admin_user):
        """Test that bulk delete works."""
        from backend.api.admin_cameras import bulk_operation, BulkOperationRequest, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door"}

        request = BulkOperationRequest(
            camera_ids=["cam-001"],
            operation="delete",
        )

        result = await bulk_operation(request, admin=admin_user)
        assert result["operation"] == "delete"
        assert result["succeeded"] == 1
        assert "cam-001" not in _camera_store

    @pytest.mark.asyncio
    async def test_reset_camera_connection(self, admin_user):
        """Test that reset camera connection works."""
        from backend.api.admin_cameras import reset_camera_connection

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await reset_camera_connection("cam-001", admin=admin_user)
            assert result["status"] == "reset"

    @pytest.mark.asyncio
    async def test_update_camera_config(self, admin_user):
        """Test that updating camera config works."""
        from backend.api.admin_cameras import update_camera_config, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door", "mode": "indoor"}

        config = {"camera_name": "Main Entrance", "mode": "outdoor"}
        result = await update_camera_config("cam-001", config, admin=admin_user)
        assert result["camera_id"] == "cam-001"
        assert result["config"]["camera_name"] == "Main Entrance"
        assert result["config"]["mode"] == "outdoor"

    @pytest.mark.asyncio
    async def test_camera_stats_aggregates(self, admin_user):
        """Test that camera stats endpoint returns aggregates."""
        from backend.api.admin_cameras import get_camera_stats, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door", "user_id": "user-001", "mode": "indoor"}
        _camera_store["cam-002"] = {"camera_name": "Back Door", "user_id": "user-001", "mode": "outdoor"}

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.register_camera("cam-002", "Back Door")
        await monitor.record_heartbeat("cam-001", "online")
        await monitor.record_heartbeat("cam-002", "online")

        from backend.analytics.camera_metrics import CameraMetricsCollector
        collector = CameraMetricsCollector()

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor), \
             patch("backend.api.admin_cameras._get_metrics_collector", return_value=collector):
            result = await get_camera_stats(admin=admin_user)
            assert result.total_cameras == 2
            assert result.online_cameras == 2
            assert result.total_users_with_cameras == 1

    @pytest.mark.asyncio
    async def test_cameras_by_user(self, admin_user):
        """Test that cameras by user endpoint works."""
        from backend.api.admin_cameras import get_cameras_by_user, _camera_store

        _camera_store.clear()
        _camera_store["cam-001"] = {"camera_name": "Front Door", "user_id": "user-001"}
        _camera_store["cam-002"] = {"camera_name": "Back Door", "user_id": "user-002"}

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        await monitor.register_camera("cam-001", "Front Door")
        await monitor.register_camera("cam-002", "Back Door")

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            result = await get_cameras_by_user("user-001", admin=admin_user)
            assert result["user_id"] == "user-001"
            assert result["total_cameras"] == 1
            assert result["cameras"][0]["camera_id"] == "cam-001"

    @pytest.mark.asyncio
    async def test_bulk_operation_limit_50(self, admin_user):
        """Test that bulk operation is limited to 50 cameras."""
        from backend.api.admin_cameras import bulk_operation, BulkOperationRequest

        request = BulkOperationRequest(
            camera_ids=[f"cam-{i}" for i in range(51)],
            operation="enable",
        )

        with pytest.raises(HTTPException) as exc_info:
            await bulk_operation(request, admin=admin_user)

        assert exc_info.value.status_code == 400
        assert "50 cameras" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_camera_details_404(self, admin_user):
        """Test that get_camera_details returns 404 for unknown camera."""
        from backend.api.admin_cameras import get_camera_details

        from backend.core.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()

        with patch("backend.api.admin_cameras._get_health_monitor", return_value=monitor):
            with pytest.raises(HTTPException) as exc_info:
                await get_camera_details("unknown-cam", admin=admin_user)
            assert exc_info.value.status_code == 404
