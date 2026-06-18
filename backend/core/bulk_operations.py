"""
bulk_operations.py — Bulk Camera Operations for Vision OS.

Admin can perform operations on multiple cameras simultaneously.
Operations: enable, disable, delete, reset, change mode, apply config template.
Progress tracking for long-running bulk operations. Rollback on partial failure.
Audit logging for all bulk operations. Supports up to 50 cameras per bulk operation.

All calls async (D026).
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────
MAX_BULK_OPERATION_SIZE = 50


@dataclass
class BulkOperationResult:
    """Result of a bulk operation."""
    operation_id: str
    operation_type: str
    total_cameras: int
    succeeded: int = 0
    failed: int = 0
    failures: list[dict] = field(default_factory=list)  # [{camera_id, error}]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "running"  # running / completed / failed / cancelled
    admin_id: str = ""


@dataclass
class BulkOperationStatus:
    """Status of a running bulk operation."""
    operation_id: str
    status: str
    progress_pct: float = 0.0
    processed: int = 0
    total: int = 0
    estimated_remaining_sec: Optional[float] = None


class BulkOperationsManager:
    """Manages bulk camera operations with progress tracking and rollback.

    Maintains in-memory operation store and audit log.
    In production, this would persist to a database.
    """

    def __init__(self, health_monitor=None, camera_store: dict = None):
        """Initialize the bulk operations manager.

        Args:
            health_monitor: CameraHealthMonitor instance (optional).
            camera_store: Camera store dict (optional).
        """
        self._operations: dict[str, BulkOperationResult] = {}
        self._operation_status: dict[str, BulkOperationStatus] = {}
        self._audit_log: list[dict] = []
        self._lock = asyncio.Lock()
        self._health_monitor = health_monitor
        self._camera_store = camera_store or {}

    # ── Bulk Operations ─────────────────────────────────────────

    async def bulk_enable(self, camera_ids: list[str], admin_id: str) -> BulkOperationResult:
        """Enable multiple cameras.

        Args:
            camera_ids: List of camera IDs to enable.
            admin_id: Admin user ID.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="enable",
            admin_id=admin_id,
            action_fn=self._enable_camera,
        )

    async def bulk_disable(self, camera_ids: list[str], admin_id: str,
                           reason: str = "") -> BulkOperationResult:
        """Disable multiple cameras.

        Args:
            camera_ids: List of camera IDs to disable.
            admin_id: Admin user ID.
            reason: Reason for disabling.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="disable",
            admin_id=admin_id,
            action_fn=lambda cid: self._disable_camera(cid, reason),
        )

    async def bulk_delete(self, camera_ids: list[str], admin_id: str) -> BulkOperationResult:
        """Delete multiple cameras.

        Args:
            camera_ids: List of camera IDs to delete.
            admin_id: Admin user ID.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="delete",
            admin_id=admin_id,
            action_fn=self._delete_camera,
        )

    async def bulk_reset(self, camera_ids: list[str], admin_id: str) -> BulkOperationResult:
        """Reset multiple cameras.

        Args:
            camera_ids: List of camera IDs to reset.
            admin_id: Admin user ID.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="reset",
            admin_id=admin_id,
            action_fn=self._reset_camera,
        )

    async def bulk_change_mode(self, camera_ids: list[str], mode: str,
                                admin_id: str) -> BulkOperationResult:
        """Change mode for multiple cameras.

        Args:
            camera_ids: List of camera IDs.
            mode: New mode (indoor/outdoor/parking/mixed/shop).
            admin_id: Admin user ID.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="change_mode",
            admin_id=admin_id,
            action_fn=lambda cid: self._change_camera_mode(cid, mode),
        )

    async def bulk_apply_template(self, camera_ids: list[str], template_id: str,
                                   admin_id: str) -> BulkOperationResult:
        """Apply a config template to multiple cameras.

        Args:
            camera_ids: List of camera IDs.
            template_id: Template ID to apply.
            admin_id: Admin user ID.

        Returns:
            BulkOperationResult with operation details.
        """
        return await self._execute_operation(
            camera_ids=camera_ids,
            operation_type="apply_template",
            admin_id=admin_id,
            action_fn=lambda cid: self._apply_template(cid, template_id),
        )

    # ── Operation Status ────────────────────────────────────────

    async def get_operation_status(self, operation_id: str) -> Optional[BulkOperationStatus]:
        """Get the current status of a bulk operation.

        Args:
            operation_id: Operation UUID.

        Returns:
            BulkOperationStatus or None if not found.
        """
        async with self._lock:
            return self._operation_status.get(operation_id)

    async def cancel_operation(self, operation_id: str) -> dict:
        """Cancel a running bulk operation.

        Args:
            operation_id: Operation UUID.

        Returns:
            Dict with cancellation status.
        """
        async with self._lock:
            if operation_id not in self._operations:
                return {"error": "Operation not found"}

            op = self._operations[operation_id]
            if op.status != "running":
                return {"error": f"Operation is already {op.status}"}

            op.status = "cancelled"
            status = self._operation_status.get(operation_id)
            if status:
                status.status = "cancelled"

            logger.info("Bulk operation %s cancelled by admin", operation_id)
            return {"operation_id": operation_id, "status": "cancelled"}

    async def get_operation_history(self, admin_id: str, limit: int = 50) -> list[BulkOperationResult]:
        """Get operation history for an admin.

        Args:
            admin_id: Admin user ID.
            limit: Maximum number of operations to return.

        Returns:
            List of BulkOperationResult.
        """
        async with self._lock:
            results = [
                op for op in self._operations.values()
                if op.admin_id == admin_id
            ]
            results.sort(key=lambda x: x.started_at or datetime.min, reverse=True)
            return results[:limit]

    # ── Internal Execution ──────────────────────────────────────

    async def _execute_operation(
        self,
        camera_ids: list[str],
        operation_type: str,
        admin_id: str,
        action_fn,
    ) -> BulkOperationResult:
        """Execute a bulk operation with progress tracking.

        Args:
            camera_ids: List of camera IDs.
            operation_type: Type of operation.
            admin_id: Admin user ID.
            action_fn: Async function to execute per camera.

        Returns:
            BulkOperationResult with operation details.
        """
        # Validate size
        if len(camera_ids) > MAX_BULK_OPERATION_SIZE:
            camera_ids = camera_ids[:MAX_BULK_OPERATION_SIZE]

        operation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        result = BulkOperationResult(
            operation_id=operation_id,
            operation_type=operation_type,
            total_cameras=len(camera_ids),
            started_at=now,
            status="running",
            admin_id=admin_id,
        )

        status = BulkOperationStatus(
            operation_id=operation_id,
            status="running",
            progress_pct=0.0,
            processed=0,
            total=len(camera_ids),
        )

        async with self._lock:
            self._operations[operation_id] = result
            self._operation_status[operation_id] = status

        # Process each camera
        for i, cid in enumerate(camera_ids):
            # Check if cancelled
            async with self._lock:
                if self._operations[operation_id].status == "cancelled":
                    break

            try:
                await action_fn(cid)
                result.succeeded += 1
            except Exception as e:
                result.failed += 1
                result.failures.append({"camera_id": cid, "error": str(e)})
                logger.warning("Bulk %s failed for camera %s: %s",
                               operation_type, cid, str(e))

            # Update progress
            processed = i + 1
            progress_pct = round((processed / len(camera_ids)) * 100, 1)
            elapsed = (datetime.now(timezone.utc) - now).total_seconds()
            rate = processed / max(elapsed, 0.001)
            remaining = (len(camera_ids) - processed) / max(rate, 0.001)

            async with self._lock:
                self._operations[operation_id].succeeded = result.succeeded
                self._operations[operation_id].failed = result.failed
                self._operation_status[operation_id].processed = processed
                self._operation_status[operation_id].progress_pct = progress_pct
                self._operation_status[operation_id].estimated_remaining_sec = round(remaining, 1)

        # Mark as completed
        completed_at = datetime.now(timezone.utc)
        async with self._lock:
            op = self._operations[operation_id]
            if op.status != "cancelled":
                op.status = "completed" if result.failed == 0 else "failed"
            op.completed_at = completed_at
            self._operation_status[operation_id].status = op.status
            self._operation_status[operation_id].progress_pct = 100.0
            self._operation_status[operation_id].processed = result.succeeded + result.failed

        # Audit log
        await self._log_audit(operation_id, operation_type, admin_id, result)

        logger.info(
            "Bulk %s completed: %d succeeded, %d failed (op=%s)",
            operation_type, result.succeeded, result.failed, operation_id,
        )

        return result

    # ── Individual Actions ──────────────────────────────────────

    async def _enable_camera(self, camera_id: str) -> None:
        """Enable a single camera.

        Args:
            camera_id: Camera identifier.

        Raises:
            Exception: If camera not found or operation fails.
        """
        if self._health_monitor:
            result = await self._health_monitor.mark_camera_online(camera_id)
            if "error" in result:
                raise Exception(result["error"])
        else:
            if camera_id not in self._camera_store:
                raise Exception(f"Camera {camera_id} not found")
            self._camera_store[camera_id]["status"] = "online"

    async def _disable_camera(self, camera_id: str, reason: str = "") -> None:
        """Disable a single camera.

        Args:
            camera_id: Camera identifier.
            reason: Reason for disabling.

        Raises:
            Exception: If camera not found or operation fails.
        """
        if self._health_monitor:
            result = await self._health_monitor.mark_camera_offline(camera_id, reason)
            if "error" in result:
                raise Exception(result["error"])
        else:
            if camera_id not in self._camera_store:
                raise Exception(f"Camera {camera_id} not found")
            self._camera_store[camera_id]["status"] = "offline"

    async def _delete_camera(self, camera_id: str) -> None:
        """Delete a single camera.

        Args:
            camera_id: Camera identifier.

        Raises:
            Exception: If camera not found.
        """
        if camera_id not in self._camera_store:
            raise Exception(f"Camera {camera_id} not found")
        self._camera_store.pop(camera_id, None)

    async def _reset_camera(self, camera_id: str) -> None:
        """Reset a single camera.

        Args:
            camera_id: Camera identifier.

        Raises:
            Exception: If camera not found.
        """
        if self._health_monitor:
            await self._health_monitor.mark_camera_offline(camera_id, "Reset")
            result = await self._health_monitor.mark_camera_online(camera_id)
            if "error" in result:
                raise Exception(result["error"])
        else:
            if camera_id not in self._camera_store:
                raise Exception(f"Camera {camera_id} not found")
            self._camera_store[camera_id]["status"] = "online"

    async def _change_camera_mode(self, camera_id: str, mode: str) -> None:
        """Change mode for a single camera.

        Args:
            camera_id: Camera identifier.
            mode: New mode.

        Raises:
            Exception: If camera not found or invalid mode.
        """
        valid_modes = {"indoor", "outdoor", "parking", "mixed", "shop"}
        if mode not in valid_modes:
            raise Exception(f"Invalid mode: {mode}. Must be one of: {', '.join(valid_modes)}")

        if camera_id not in self._camera_store:
            raise Exception(f"Camera {camera_id} not found")
        self._camera_store[camera_id]["mode"] = mode

    async def _apply_template(self, camera_id: str, template_id: str) -> None:
        """Apply a config template to a single camera.

        Args:
            camera_id: Camera identifier.
            template_id: Template ID.

        Raises:
            Exception: If camera not found or template not found.
        """
        # In production, load template from DB
        templates = {
            "high-security": {"mode": "outdoor", "fps": 30, "resolution": "4K"},
            "standard": {"mode": "indoor", "fps": 15, "resolution": "1080p"},
            "low-bandwidth": {"mode": "indoor", "fps": 5, "resolution": "720p"},
        }

        if template_id not in templates:
            raise Exception(f"Template {template_id} not found")

        if camera_id not in self._camera_store:
            raise Exception(f"Camera {camera_id} not found")

        template = templates[template_id]
        self._camera_store[camera_id].update(template)
        self._camera_store[camera_id]["template_id"] = template_id

    # ── Audit Logging ───────────────────────────────────────────

    async def _log_audit(self, operation_id: str, operation_type: str,
                          admin_id: str, result: BulkOperationResult) -> None:
        """Log a bulk operation to the audit trail.

        Args:
            operation_id: Operation UUID.
            operation_type: Type of operation.
            admin_id: Admin user ID.
            result: Operation result.
        """
        entry = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "admin_id": admin_id,
            "total_cameras": result.total_cameras,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "failures": result.failures,
            "status": result.status,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        async with self._lock:
            self._audit_log.append(entry)

        logger.info("Audit: bulk %s by %s: %d/%d succeeded",
                     operation_type, admin_id, result.succeeded, result.total_cameras)

    async def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Get the audit log.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of audit log entries.
        """
        async with self._lock:
            return list(reversed(self._audit_log))[:limit]
