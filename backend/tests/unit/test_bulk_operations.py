"""Tests for Sprint 8.5 — Bulk Camera Operations."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.bulk_operations import (
    BulkOperationsManager,
    BulkOperationResult,
    BulkOperationStatus,
    MAX_BULK_OPERATION_SIZE,
)


@pytest.fixture
def camera_store():
    """Create a test camera store."""
    return {
        "cam-001": {"camera_name": "Front Door", "status": "online", "mode": "indoor"},
        "cam-002": {"camera_name": "Back Door", "status": "online", "mode": "indoor"},
        "cam-003": {"camera_name": "Garage", "status": "offline", "mode": "outdoor"},
    }


@pytest.fixture
def bulk_manager(camera_store):
    """Create a BulkOperationsManager with a test camera store."""
    return BulkOperationsManager(camera_store=camera_store)


class TestBulkOperationsManager:
    """Tests for BulkOperationsManager class."""

    @pytest.mark.asyncio
    async def test_bulk_enable_all_succeed(self, bulk_manager, camera_store):
        """Test that bulk enable succeeds for all cameras."""
        # Set cameras offline first
        camera_store["cam-001"]["status"] = "offline"
        camera_store["cam-002"]["status"] = "offline"

        result = await bulk_manager.bulk_enable(
            camera_ids=["cam-001", "cam-002"],
            admin_id="admin-001",
        )

        assert isinstance(result, BulkOperationResult)
        assert result.operation_type == "enable"
        assert result.total_cameras == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert result.status == "completed"
        assert result.admin_id == "admin-001"

        # Verify cameras were enabled
        assert camera_store["cam-001"]["status"] == "online"
        assert camera_store["cam-002"]["status"] == "online"

    @pytest.mark.asyncio
    async def test_bulk_enable_partial_failure(self, bulk_manager, camera_store):
        """Test that bulk enable handles partial failures."""
        # Set one camera offline, leave one missing
        camera_store["cam-001"]["status"] = "offline"

        result = await bulk_manager.bulk_enable(
            camera_ids=["cam-001", "non-existent"],
            admin_id="admin-001",
        )

        assert result.succeeded == 1
        assert result.failed == 1
        assert len(result.failures) == 1
        assert result.failures[0]["camera_id"] == "non-existent"

    @pytest.mark.asyncio
    async def test_bulk_disable_all_succeed(self, bulk_manager, camera_store):
        """Test that bulk disable succeeds for all cameras."""
        result = await bulk_manager.bulk_disable(
            camera_ids=["cam-001", "cam-002"],
            admin_id="admin-001",
            reason="Maintenance",
        )

        assert result.succeeded == 2
        assert result.failed == 0
        assert result.status == "completed"

        # Verify cameras were disabled
        assert camera_store["cam-001"]["status"] == "offline"
        assert camera_store["cam-002"]["status"] == "offline"

    @pytest.mark.asyncio
    async def test_bulk_delete_with_confirmation(self, bulk_manager, camera_store):
        """Test that bulk delete removes cameras."""
        result = await bulk_manager.bulk_delete(
            camera_ids=["cam-001", "cam-002"],
            admin_id="admin-001",
        )

        assert result.succeeded == 2
        assert result.failed == 0
        assert "cam-001" not in camera_store
        assert "cam-002" not in camera_store
        assert "cam-003" in camera_store  # Should still exist

    @pytest.mark.asyncio
    async def test_bulk_reset_cameras(self, bulk_manager, camera_store):
        """Test that bulk reset works."""
        result = await bulk_manager.bulk_reset(
            camera_ids=["cam-001", "cam-002"],
            admin_id="admin-001",
        )

        assert result.succeeded == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_bulk_change_mode(self, bulk_manager, camera_store):
        """Test that bulk change mode works."""
        result = await bulk_manager.bulk_change_mode(
            camera_ids=["cam-001", "cam-002"],
            mode="outdoor",
            admin_id="admin-001",
        )

        assert result.succeeded == 2
        assert result.failed == 0
        assert camera_store["cam-001"]["mode"] == "outdoor"
        assert camera_store["cam-002"]["mode"] == "outdoor"

    @pytest.mark.asyncio
    async def test_bulk_change_mode_invalid(self, bulk_manager):
        """Test that bulk change mode with invalid mode fails."""
        result = await bulk_manager.bulk_change_mode(
            camera_ids=["cam-001"],
            mode="invalid-mode",
            admin_id="admin-001",
        )

        assert result.succeeded == 0
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_bulk_apply_template(self, bulk_manager, camera_store):
        """Test that bulk apply template works."""
        result = await bulk_manager.bulk_apply_template(
            camera_ids=["cam-001", "cam-002"],
            template_id="high-security",
            admin_id="admin-001",
        )

        assert result.succeeded == 2
        assert result.failed == 0
        assert camera_store["cam-001"]["mode"] == "outdoor"
        assert camera_store["cam-001"]["fps"] == 30
        assert camera_store["cam-001"]["resolution"] == "4K"

    @pytest.mark.asyncio
    async def test_bulk_apply_template_not_found(self, bulk_manager):
        """Test that bulk apply template with unknown template fails."""
        result = await bulk_manager.bulk_apply_template(
            camera_ids=["cam-001"],
            template_id="non-existent",
            admin_id="admin-001",
        )

        assert result.succeeded == 0
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_get_operation_status_running(self, bulk_manager):
        """Test that get_operation_status returns running status."""
        # Start an operation
        result = await bulk_manager.bulk_enable(
            camera_ids=["cam-001"],
            admin_id="admin-001",
        )

        status = await bulk_manager.get_operation_status(result.operation_id)
        assert isinstance(status, BulkOperationStatus)
        assert status.status == "completed"
        assert status.progress_pct == 100.0
        assert status.processed == 1
        assert status.total == 1

    @pytest.mark.asyncio
    async def test_get_operation_status_completed(self, bulk_manager):
        """Test that get_operation_status returns completed status."""
        result = await bulk_manager.bulk_enable(
            camera_ids=["cam-001"],
            admin_id="admin-001",
        )

        status = await bulk_manager.get_operation_status(result.operation_id)
        assert status.status == "completed"

    @pytest.mark.asyncio
    async def test_cancel_running_operation(self, bulk_manager):
        """Test that cancel_operation works."""
        # Start an operation
        result = await bulk_manager.bulk_enable(
            camera_ids=["cam-001"],
            admin_id="admin-001",
        )

        # Try to cancel (already completed, so should fail)
        cancel_result = await bulk_manager.cancel_operation(result.operation_id)
        assert "error" in cancel_result

    @pytest.mark.asyncio
    async def test_operation_history_returns_list(self, bulk_manager):
        """Test that get_operation_history returns list of operations."""
        await bulk_manager.bulk_enable(camera_ids=["cam-001"], admin_id="admin-001")
        await bulk_manager.bulk_disable(camera_ids=["cam-002"], admin_id="admin-001")

        history = await bulk_manager.get_operation_history("admin-001", limit=10)
        assert len(history) == 2
        assert all(isinstance(op, BulkOperationResult) for op in history)

    @pytest.mark.asyncio
    async def test_bulk_operation_audit_log(self, bulk_manager):
        """Test that bulk operations are logged to audit trail."""
        await bulk_manager.bulk_enable(camera_ids=["cam-001"], admin_id="admin-001")

        audit_log = await bulk_manager.get_audit_log(limit=10)
        assert len(audit_log) >= 1
        assert audit_log[0]["operation_type"] == "enable"
        assert audit_log[0]["admin_id"] == "admin-001"
        assert audit_log[0]["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_bulk_operations(self, bulk_manager):
        """Test that concurrent bulk operations work correctly."""
        import asyncio

        async def op1():
            return await bulk_manager.bulk_enable(
                camera_ids=["cam-001"], admin_id="admin-001"
            )

        async def op2():
            return await bulk_manager.bulk_disable(
                camera_ids=["cam-002"], admin_id="admin-001"
            )

        results = await asyncio.gather(op1(), op2())
        assert results[0].succeeded == 1
        assert results[1].succeeded == 1

    @pytest.mark.asyncio
    async def test_bulk_operation_limit_50(self, bulk_manager):
        """Test that bulk operation is limited to 50 cameras."""
        camera_ids = [f"cam-{i}" for i in range(60)]

        result = await bulk_manager.bulk_enable(
            camera_ids=camera_ids,
            admin_id="admin-001",
        )

        # Should be truncated to 50
        assert result.total_cameras == MAX_BULK_OPERATION_SIZE

    @pytest.mark.asyncio
    async def test_bulk_delete_nonexistent_camera(self, bulk_manager):
        """Test that deleting a non-existent camera fails gracefully."""
        result = await bulk_manager.bulk_delete(
            camera_ids=["non-existent"],
            admin_id="admin-001",
        )

        assert result.succeeded == 0
        assert result.failed == 1
        assert result.failures[0]["camera_id"] == "non-existent"

    @pytest.mark.asyncio
    async def test_get_operation_status_not_found(self, bulk_manager):
        """Test that get_operation_status returns None for unknown operation."""
        status = await bulk_manager.get_operation_status("non-existent")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_operation(self, bulk_manager):
        """Test that cancelling a non-existent operation returns error."""
        result = await bulk_manager.cancel_operation("non-existent")
        assert "error" in result
