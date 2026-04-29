"""
admin_cameras.py — Admin-Only Camera Management API for Vision OS.

Provides admin-only FastAPI endpoints for managing all cameras across
all users. Supports bulk operations, health monitoring, and configuration
management. Admin authentication via Firebase Auth with admin role check.

All calls async (D026).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/cameras", tags=["admin-cameras"])

# ── In-memory stores (replace with DB in production) ───────────
_camera_store: dict[str, dict] = {}
_health_monitor = None
_metrics_collector = None


def _get_health_monitor():
    """Get or create the health monitor singleton."""
    global _health_monitor
    if _health_monitor is None:
        from backend.core.camera_health import CameraHealthMonitor
        _health_monitor = CameraHealthMonitor()
    return _health_monitor


def _get_metrics_collector():
    """Get or create the metrics collector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        from backend.analytics.camera_metrics import CameraMetricsCollector
        _metrics_collector = CameraMetricsCollector()
    return _metrics_collector


# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class BulkOperationRequest:
    """Request body for bulk camera operations."""
    camera_ids: list[str]
    operation: str  # enable / disable / delete / reset
    reason: Optional[str] = None


@dataclass
class CameraStats:
    """Aggregate camera statistics."""
    total_cameras: int = 0
    online_cameras: int = 0
    offline_cameras: int = 0
    error_cameras: int = 0
    total_users_with_cameras: int = 0
    avg_cameras_per_user: float = 0.0
    total_triggers_24h: int = 0
    total_ai_cost_24h: float = 0.0
    cameras_by_mode: dict[str, int] = field(default_factory=dict)


# ── Auth Dependencies ──────────────────────────────────────────


async def get_current_admin() -> dict:
    """Dependency: Get current authenticated admin user.

    In production, validates Firebase Auth token and checks admin role.
    """
    return {"id": "admin-001", "role": "admin", "email": "admin@visionos.com"}


async def require_admin(user: dict = Depends(get_current_admin)) -> dict:
    """Check if user has admin role.

    Args:
        user: Authenticated user dict.

    Returns:
        User dict if admin.

    Raises:
        HTTPException: 403 if not admin.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return user


# ── Endpoints ──────────────────────────────────────────────────


@router.get("")
async def list_cameras(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    """List all cameras across all users (paginated).

    Args:
        page: Page number (1-indexed).
        per_page: Items per page (max 100).
        status: Filter by status (online/offline/error).
        user_id: Filter by user ID.
        admin: Admin user.

    Returns:
        Dict with cameras, total, page, per_page.
    """
    monitor = _get_health_monitor()
    all_cameras = []

    # In production, query from DB
    for cid, info in _camera_store.items():
        health = await monitor.get_camera_health(cid)
        if health:
            if status and health.status != status:
                continue
            if user_id and info.get("user_id") != user_id:
                continue
            all_cameras.append({
                "camera_id": cid,
                "camera_name": info.get("camera_name", cid),
                "user_id": info.get("user_id", ""),
                "location_id": info.get("location_id", ""),
                "status": health.status,
                "last_heartbeat": health.last_heartbeat.isoformat() if health.last_heartbeat else None,
                "uptime_pct_24h": health.uptime_pct_24h,
                "error_count_24h": health.error_count_24h,
            })

    total = len(all_cameras)
    start = (page - 1) * per_page
    end = start + per_page
    page_cameras = all_cameras[start:end]

    return {
        "cameras": page_cameras,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/{camera_id}")
async def get_camera_details(
    camera_id: str,
    admin: dict = Depends(require_admin),
):
    """Get camera details including health.

    Args:
        camera_id: Camera identifier.
        admin: Admin user.

    Returns:
        Dict with camera info and health data.
    """
    monitor = _get_health_monitor()
    health = await monitor.get_camera_health(camera_id)

    if health is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    info = _camera_store.get(camera_id, {})

    return {
        "camera_id": camera_id,
        "camera_name": info.get("camera_name", camera_id),
        "user_id": info.get("user_id", ""),
        "location_id": info.get("location_id", ""),
        "mode": info.get("mode", "indoor"),
        "health": {
            "status": health.status,
            "last_heartbeat": health.last_heartbeat.isoformat() if health.last_heartbeat else None,
            "uptime_pct_24h": health.uptime_pct_24h,
            "uptime_pct_7d": health.uptime_pct_7d,
            "error_count_24h": health.error_count_24h,
            "error_count_7d": health.error_count_7d,
        },
    }


@router.get("/health")
async def get_health_summary(
    admin: dict = Depends(require_admin),
):
    """Get health summary for all cameras.

    Args:
        admin: Admin user.

    Returns:
        HealthSummary dataclass as dict.
    """
    monitor = _get_health_monitor()
    summary = await monitor.get_health_summary("__all__")
    return {
        "total_cameras": summary.total_cameras,
        "online_cameras": summary.online_cameras,
        "offline_cameras": summary.offline_cameras,
        "error_cameras": summary.error_cameras,
        "avg_uptime_pct": summary.avg_uptime_pct,
        "total_errors_24h": summary.total_errors_24h,
        "last_updated": summary.last_updated.isoformat() if summary.last_updated else None,
    }


@router.get("/offline")
async def get_offline_cameras(
    threshold_minutes: int = Query(5, ge=1),
    admin: dict = Depends(require_admin),
):
    """Get all offline cameras.

    Args:
        threshold_minutes: Minutes without heartbeat to consider offline.
        admin: Admin user.

    Returns:
        Dict with offline_camera_ids list.
    """
    monitor = _get_health_monitor()
    offline = await monitor.get_offline_cameras(threshold_minutes=threshold_minutes)
    return {"offline_camera_ids": offline, "count": len(offline)}


@router.get("/{camera_id}/health")
async def get_camera_health_history(
    camera_id: str,
    days: int = Query(7, ge=1, le=30),
    admin: dict = Depends(require_admin),
):
    """Get health history for a specific camera.

    Args:
        camera_id: Camera identifier.
        days: Number of days of history.
        admin: Admin user.

    Returns:
        Dict with health history list.
    """
    monitor = _get_health_monitor()
    history = await monitor.get_health_history(camera_id, days=days)
    return {
        "camera_id": camera_id,
        "days": days,
        "snapshots": [
            {
                "timestamp": s.timestamp.isoformat(),
                "status": s.status,
                "latency_ms": s.latency_ms,
                "error_count": s.error_count,
                "frames_processed": s.frames_processed,
            }
            for s in history
        ],
    }


@router.get("/{camera_id}/metrics")
async def get_camera_metrics(
    camera_id: str,
    days: int = Query(7, ge=1, le=90),
    admin: dict = Depends(require_admin),
):
    """Get metrics for a specific camera.

    Args:
        camera_id: Camera identifier.
        days: Number of days of metrics.
        admin: Admin user.

    Returns:
        Dict with metrics data.
    """
    collector = _get_metrics_collector()

    end = date.today()
    start = end - timedelta(days=days)

    metrics_list = await collector.get_metrics_range(camera_id, start, end)
    cost = await collector.get_cost_breakdown(camera_id, days=days)
    bandwidth = await collector.get_bandwidth_usage(camera_id, days=days)
    trend = await collector.get_trigger_trend(camera_id, days=days)

    return {
        "camera_id": camera_id,
        "days": days,
        "daily_metrics": [
            {
                "date": m.date.isoformat(),
                "total_triggers": m.total_triggers,
                "ai_calls": m.ai_calls,
                "ai_cost_total": m.ai_cost_total,
                "bandwidth_bytes": m.bandwidth_bytes,
                "events_generated": m.events_generated,
                "avg_frame_size_bytes": m.avg_frame_size_bytes,
            }
            for m in metrics_list
        ],
        "cost_breakdown": {
            "total_ai_cost": cost.total_ai_cost,
            "total_storage_cost": cost.total_storage_cost,
            "total_bandwidth_cost": cost.total_bandwidth_cost,
            "total_cost": cost.total_cost,
            "cost_per_day": cost.cost_per_day,
            "cost_per_trigger": cost.cost_per_trigger,
        },
        "bandwidth": {
            "total_bytes": bandwidth.total_bytes,
            "total_mb": bandwidth.total_mb,
            "avg_daily_mb": bandwidth.avg_daily_mb,
            "peak_daily_mb": bandwidth.peak_daily_mb,
        },
        "trigger_trend": trend,
    }


@router.post("/bulk")
async def bulk_operation(
    request: BulkOperationRequest,
    admin: dict = Depends(require_admin),
):
    """Perform bulk operation on multiple cameras.

    Args:
        request: BulkOperationRequest with camera_ids and operation.
        admin: Admin user.

    Returns:
        Dict with operation results.

    Raises:
        HTTPException: 400 if operation invalid or limit exceeded.
    """
    valid_operations = {"enable", "disable", "delete", "reset"}
    if request.operation not in valid_operations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operation. Must be one of: {', '.join(valid_operations)}",
        )

    if len(request.camera_ids) > 50:
        raise HTTPException(
            status_code=400,
            detail="Bulk operation limited to 50 cameras per request",
        )

    monitor = _get_health_monitor()
    results = []

    for cid in request.camera_ids:
        try:
            if request.operation == "enable":
                result = await monitor.mark_camera_online(cid)
            elif request.operation == "disable":
                result = await monitor.mark_camera_offline(
                    cid, reason=request.reason or "Admin action"
                )
            elif request.operation == "delete":
                # Remove from store
                _camera_store.pop(cid, None)
                result = {"camera_id": cid, "status": "deleted"}
            elif request.operation == "reset":
                # Reset: mark offline then online
                await monitor.mark_camera_offline(cid, "Reset requested")
                result = await monitor.mark_camera_online(cid)
                result["status"] = "reset"
            else:
                result = {"error": f"Unknown operation: {request.operation}"}

            results.append(result)
        except Exception as e:
            results.append({"camera_id": cid, "error": str(e)})

    succeeded = sum(1 for r in results if "error" not in r)
    failed = sum(1 for r in results if "error" in r)

    return {
        "operation": request.operation,
        "total": len(request.camera_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@router.post("/{camera_id}/reset")
async def reset_camera_connection(
    camera_id: str,
    admin: dict = Depends(require_admin),
):
    """Reset a camera's connection.

    Args:
        camera_id: Camera identifier.
        admin: Admin user.

    Returns:
        Dict with reset status.
    """
    monitor = _get_health_monitor()
    await monitor.mark_camera_offline(camera_id, "Connection reset by admin")
    result = await monitor.mark_camera_online(camera_id)
    return {
        "camera_id": camera_id,
        "status": "reset",
        "message": f"Camera {camera_id} connection reset successfully",
    }


@router.put("/{camera_id}/config")
async def update_camera_config(
    camera_id: str,
    config: dict,
    admin: dict = Depends(require_admin),
):
    """Update camera configuration.

    Args:
        camera_id: Camera identifier.
        config: Configuration dict to update.
        admin: Admin user.

    Returns:
        Dict with updated config.
    """
    if camera_id not in _camera_store:
        raise HTTPException(status_code=404, detail="Camera not found")

    allowed_keys = {"camera_name", "mode", "location_id", "rtsp_url", "fps", "resolution"}
    for key, value in config.items():
        if key in allowed_keys:
            _camera_store[camera_id][key] = value

    logger.info("Admin %s updated config for camera %s", admin["id"], camera_id)
    return {
        "camera_id": camera_id,
        "config": {k: _camera_store[camera_id].get(k) for k in allowed_keys},
    }


@router.get("/stats")
async def get_camera_stats(
    admin: dict = Depends(require_admin),
):
    """Get aggregate camera statistics.

    Args:
        admin: Admin user.

    Returns:
        CameraStats dataclass as dict.
    """
    monitor = _get_health_monitor()
    collector = _get_metrics_collector()

    cameras = await monitor.get_all_cameras_health("__all__")

    total = len(cameras)
    online = sum(1 for c in cameras if c.status == "online")
    offline = sum(1 for c in cameras if c.status == "offline")
    error_cams = sum(1 for c in cameras if c.status == "error")

    # Count unique users
    user_ids = set()
    for cid in _camera_store:
        uid = _camera_store[cid].get("user_id")
        if uid:
            user_ids.add(uid)
    total_users = len(user_ids)
    avg_per_user = round(total / max(total_users, 1), 2)

    # Count by mode
    modes = {}
    for info in _camera_store.values():
        mode = info.get("mode", "indoor")
        modes[mode] = modes.get(mode, 0) + 1

    # Get today's metrics
    today = date.today()
    all_metrics = await collector.get_all_cameras_metrics("__all__", today)
    total_triggers = sum(m.total_triggers for m in all_metrics)
    total_ai_cost = sum(m.ai_cost_total for m in all_metrics)

    return CameraStats(
        total_cameras=total,
        online_cameras=online,
        offline_cameras=offline,
        error_cameras=error_cams,
        total_users_with_cameras=total_users,
        avg_cameras_per_user=avg_per_user,
        total_triggers_24h=total_triggers,
        total_ai_cost_24h=round(total_ai_cost, 6),
        cameras_by_mode=modes,
    )


@router.get("/by-user/{user_id}")
async def get_cameras_by_user(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    """List all cameras for a specific user.

    Args:
        user_id: User UUID.
        admin: Admin user.

    Returns:
        Dict with cameras list for the user.
    """
    monitor = _get_health_monitor()
    user_cameras = []

    for cid, info in _camera_store.items():
        if info.get("user_id") == user_id:
            health = await monitor.get_camera_health(cid)
            user_cameras.append({
                "camera_id": cid,
                "camera_name": info.get("camera_name", cid),
                "location_id": info.get("location_id", ""),
                "mode": info.get("mode", "indoor"),
                "status": health.status if health else "unknown",
                "last_heartbeat": health.last_heartbeat.isoformat() if health and health.last_heartbeat else None,
            })

    return {
        "user_id": user_id,
        "total_cameras": len(user_cameras),
        "cameras": user_cameras,
    }
