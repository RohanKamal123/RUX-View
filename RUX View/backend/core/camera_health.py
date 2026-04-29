"""
camera_health.py — Camera Health Monitoring for Vision OS.

Tracks online/offline status, uptime, error count, last heartbeat
for all cameras. Health data retained for 30 days, then aggregated
to daily summaries. Supports up to 10 cameras per user.

All calls async (D026).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Retention policy ────────────────────────────────────────────
HEALTH_RETENTION_DAYS = 30
OFFLINE_THRESHOLD_MINUTES = 5


@dataclass
class CameraHealth:
    """Current health snapshot for a single camera."""
    camera_id: str
    camera_name: str
    status: str  # online / offline / error
    last_heartbeat: Optional[datetime] = None
    uptime_pct_24h: float = 100.0
    uptime_pct_7d: float = 100.0
    error_count_24h: int = 0
    error_count_7d: int = 0
    location_id: str = ""
    location_name: str = ""


@dataclass
class HealthSnapshot:
    """A single health data point at a point in time."""
    timestamp: datetime
    status: str
    latency_ms: float = 0.0
    error_count: int = 0
    frames_processed: int = 0


@dataclass
class HealthSummary:
    """Aggregated health summary for all cameras of a user."""
    total_cameras: int = 0
    online_cameras: int = 0
    offline_cameras: int = 0
    error_cameras: int = 0
    avg_uptime_pct: float = 100.0
    total_errors_24h: int = 0
    last_updated: Optional[datetime] = None


class CameraHealthMonitor:
    """Monitors and tracks health status for all cameras.

    Maintains in-memory state for heartbeat tracking, health snapshots,
    and aggregated summaries. In production, this would persist to DB.
    """

    def __init__(self):
        """Initialize the health monitor with empty stores."""
        self._heartbeats: dict[str, dict] = {}  # camera_id -> last heartbeat info
        self._health_history: dict[str, list[HealthSnapshot]] = {}  # camera_id -> snapshots
        self._camera_info: dict[str, dict] = {}  # camera_id -> metadata
        self._lock = asyncio.Lock()

    # ── Camera Registration ─────────────────────────────────────

    async def register_camera(self, camera_id: str, camera_name: str,
                               location_id: str = "", location_name: str = "") -> dict:
        """Register a camera for health tracking.

        Args:
            camera_id: Unique camera identifier.
            camera_name: Human-readable camera name.
            location_id: Location UUID.
            location_name: Location display name.

        Returns:
            Dict with registration status.
        """
        async with self._lock:
            self._camera_info[camera_id] = {
                "camera_name": camera_name,
                "location_id": location_id,
                "location_name": location_name,
            }
            if camera_id not in self._heartbeats:
                self._heartbeats[camera_id] = {
                    "status": "offline",
                    "last_heartbeat": None,
                    "error_count": 0,
                    "uptime_start": None,
                    "total_uptime_24h": 0.0,
                    "total_uptime_7d": 0.0,
                    "total_seconds_24h": 0.0,
                    "total_seconds_7d": 0.0,
                }
            if camera_id not in self._health_history:
                self._health_history[camera_id] = []

        logger.info("Camera %s registered for health monitoring", camera_id)
        return {"camera_id": camera_id, "status": "registered"}

    # ── Heartbeat Recording ─────────────────────────────────────

    async def record_heartbeat(self, camera_id: str, status: str = "online") -> dict:
        """Record a heartbeat from a camera.

        Args:
            camera_id: Camera identifier.
            status: Current status (online/error).

        Returns:
            Dict with heartbeat acknowledgement.
        """
        now = datetime.now(timezone.utc)

        async with self._lock:
            if camera_id not in self._heartbeats:
                # Auto-register if not found (use lock-free registration)
                name = self._camera_info.get(camera_id, {}).get("camera_name", camera_id)
                self._camera_info[camera_id] = {
                    "camera_name": name,
                    "location_id": "",
                    "location_name": "",
                }
                self._heartbeats[camera_id] = {
                    "status": "offline",
                    "last_heartbeat": None,
                    "error_count": 0,
                    "uptime_start": None,
                    "total_uptime_24h": 0.0,
                    "total_uptime_7d": 0.0,
                    "total_seconds_24h": 0.0,
                    "total_seconds_7d": 0.0,
                }
                self._health_history[camera_id] = []

            prev_status = self._heartbeats[camera_id]["status"]
            self._heartbeats[camera_id]["status"] = status
            self._heartbeats[camera_id]["last_heartbeat"] = now

            if status == "error":
                self._heartbeats[camera_id]["error_count"] += 1

            # Track uptime transitions
            if prev_status == "offline" and status == "online":
                self._heartbeats[camera_id]["uptime_start"] = now

            # Record snapshot
            snapshot = HealthSnapshot(
                timestamp=now,
                status=status,
                latency_ms=0.0,
                error_count=self._heartbeats[camera_id]["error_count"],
                frames_processed=0,
            )
            self._health_history[camera_id].append(snapshot)

            # Enforce retention
            await self._enforce_retention(camera_id)

        logger.debug("Heartbeat recorded for %s: status=%s", camera_id, status)
        return {"camera_id": camera_id, "status": status, "timestamp": now.isoformat()}

    # ── Health Queries ──────────────────────────────────────────

    async def get_camera_health(self, camera_id: str) -> Optional[CameraHealth]:
        """Get current health for a single camera.

        Args:
            camera_id: Camera identifier.

        Returns:
            CameraHealth dataclass or None if camera not found.
        """
        async with self._lock:
            if camera_id not in self._heartbeats:
                return None

            info = self._camera_info.get(camera_id, {})
            hb = self._heartbeats[camera_id]
            now = datetime.now(timezone.utc)

            # Auto-detect offline
            status = hb["status"]
            if status == "online" and hb["last_heartbeat"]:
                elapsed = (now - hb["last_heartbeat"]).total_seconds()
                if elapsed > OFFLINE_THRESHOLD_MINUTES * 60:
                    status = "offline"

            # Calculate uptime percentages (use lock-free helpers to avoid deadlock)
            uptime_24h = await self._get_camera_uptime_locked(camera_id, since=now - timedelta(hours=24))
            uptime_7d = await self._get_camera_uptime_locked(camera_id, since=now - timedelta(hours=168))
            errors_24h = await self._get_camera_error_count_locked(camera_id, since=now - timedelta(hours=24))
            errors_7d = await self._get_camera_error_count_locked(camera_id, since=now - timedelta(days=7))

            return CameraHealth(
                camera_id=camera_id,
                camera_name=info.get("camera_name", camera_id),
                status=status,
                last_heartbeat=hb["last_heartbeat"],
                uptime_pct_24h=round(uptime_24h, 2),
                uptime_pct_7d=round(uptime_7d, 2),
                error_count_24h=errors_24h,
                error_count_7d=errors_7d,
                location_id=info.get("location_id", ""),
                location_name=info.get("location_name", ""),
            )

    async def get_all_cameras_health(self, user_id: str) -> list[CameraHealth]:
        """Get health for all cameras belonging to a user.

        Args:
            user_id: User UUID.

        Returns:
            List of CameraHealth dataclasses.
        """
        # In production, filter by user_id from DB
        # For now, return all tracked cameras
        async with self._lock:
            camera_ids = list(self._heartbeats.keys())

        results = []
        for cid in camera_ids:
            # Use the lock-free internal method to avoid deadlock
            health = await self._get_camera_health_locked(cid)
            if health:
                results.append(health)

        return results

    async def get_offline_cameras(self, threshold_minutes: int = 5) -> list[str]:
        """Get list of cameras that are offline beyond threshold.

        Args:
            threshold_minutes: Minutes without heartbeat to consider offline.

        Returns:
            List of offline camera IDs.
        """
        now = datetime.now(timezone.utc)
        offline = []

        async with self._lock:
            for cid, hb in self._heartbeats.items():
                if hb["status"] == "offline":
                    offline.append(cid)
                elif hb["last_heartbeat"]:
                    elapsed = (now - hb["last_heartbeat"]).total_seconds()
                    if elapsed > threshold_minutes * 60:
                        offline.append(cid)

        return offline

    async def get_camera_uptime(self, camera_id: str, since: datetime) -> float:
        """Calculate uptime percentage since a given time.

        Args:
            camera_id: Camera identifier.
            since: Start of the period.

        Returns:
            Uptime percentage (0.0-100.0).
        """
        async with self._lock:
            if camera_id not in self._health_history:
                return 100.0

            snapshots = [s for s in self._health_history[camera_id] if s.timestamp >= since]
            if not snapshots:
                return 100.0

            online_count = sum(1 for s in snapshots if s.status == "online")
            return (online_count / len(snapshots)) * 100.0

    async def get_camera_error_count(self, camera_id: str, since: datetime) -> int:
        """Get error count for a camera since a given time.

        Args:
            camera_id: Camera identifier.
            since: Start of the period.

        Returns:
            Number of error heartbeats.
        """
        async with self._lock:
            if camera_id not in self._health_history:
                return 0

            snapshots = [s for s in self._health_history[camera_id] if s.timestamp >= since]
            return sum(1 for s in snapshots if s.status == "error")

    async def get_health_history(self, camera_id: str, days: int = 7) -> list[HealthSnapshot]:
        """Get health snapshot history for a camera.

        Args:
            camera_id: Camera identifier.
            days: Number of days of history to return.

        Returns:
            List of HealthSnapshot dataclasses.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with self._lock:
            if camera_id not in self._health_history:
                return []

            return [s for s in self._health_history[camera_id] if s.timestamp >= since]

    # ── Status Management ───────────────────────────────────────

    async def mark_camera_offline(self, camera_id: str, reason: str = "") -> dict:
        """Manually mark a camera as offline.

        Args:
            camera_id: Camera identifier.
            reason: Reason for going offline.

        Returns:
            Dict with status update.
        """
        async with self._lock:
            if camera_id not in self._heartbeats:
                return {"error": "Camera not found"}

            self._heartbeats[camera_id]["status"] = "offline"
            self._heartbeats[camera_id]["uptime_start"] = None

            snapshot = HealthSnapshot(
                timestamp=datetime.now(timezone.utc),
                status="offline",
                error_count=self._heartbeats[camera_id]["error_count"],
            )
            self._health_history[camera_id].append(snapshot)

        logger.info("Camera %s marked offline: %s", camera_id, reason)
        return {"camera_id": camera_id, "status": "offline", "reason": reason}

    async def mark_camera_online(self, camera_id: str) -> dict:
        """Manually mark a camera as online.

        Args:
            camera_id: Camera identifier.

        Returns:
            Dict with status update.
        """
        async with self._lock:
            if camera_id not in self._heartbeats:
                return {"error": "Camera not found"}

            self._heartbeats[camera_id]["status"] = "online"
            self._heartbeats[camera_id]["uptime_start"] = datetime.now(timezone.utc)

            snapshot = HealthSnapshot(
                timestamp=datetime.now(timezone.utc),
                status="online",
            )
            self._health_history[camera_id].append(snapshot)

        logger.info("Camera %s marked online", camera_id)
        return {"camera_id": camera_id, "status": "online"}

    async def get_health_summary(self, user_id: str) -> HealthSummary:
        """Get aggregated health summary for all cameras of a user.

        Args:
            user_id: User UUID.

        Returns:
            HealthSummary dataclass.
        """
        cameras = await self.get_all_cameras_health(user_id)
        now = datetime.now(timezone.utc)

        total = len(cameras)
        online = sum(1 for c in cameras if c.status == "online")
        offline = sum(1 for c in cameras if c.status == "offline")
        error_cams = sum(1 for c in cameras if c.status == "error")
        avg_uptime = sum(c.uptime_pct_24h for c in cameras) / max(total, 1)
        total_errors = sum(c.error_count_24h for c in cameras)

        return HealthSummary(
            total_cameras=total,
            online_cameras=online,
            offline_cameras=offline,
            error_cameras=error_cams,
            avg_uptime_pct=round(avg_uptime, 2),
            total_errors_24h=total_errors,
            last_updated=now,
        )

    # ── Internal Helpers ────────────────────────────────────────

    async def _calculate_uptime(self, camera_id: str, hours: int) -> float:
        """Calculate uptime percentage for a given period.

        Args:
            camera_id: Camera identifier.
            hours: Period length in hours.

        Returns:
            Uptime percentage (0.0-100.0).
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return await self._get_camera_uptime_locked(camera_id, since)

    async def _enforce_retention(self, camera_id: str) -> None:
        """Remove health snapshots older than retention period.

        Args:
            camera_id: Camera identifier.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=HEALTH_RETENTION_DAYS)
        if camera_id in self._health_history:
            self._health_history[camera_id] = [
                s for s in self._health_history[camera_id] if s.timestamp >= cutoff
            ]

    # ── Lock-Free Internal Helpers (caller must hold self._lock) ─

    async def _get_camera_health_locked(self, camera_id: str) -> Optional[CameraHealth]:
        """Get camera health without acquiring lock (caller must hold lock).

        Args:
            camera_id: Camera identifier.

        Returns:
            CameraHealth dataclass or None if camera not found.
        """
        if camera_id not in self._heartbeats:
            return None

        info = self._camera_info.get(camera_id, {})
        hb = self._heartbeats[camera_id]
        now = datetime.now(timezone.utc)

        # Auto-detect offline
        status = hb["status"]
        if status == "online" and hb["last_heartbeat"]:
            elapsed = (now - hb["last_heartbeat"]).total_seconds()
            if elapsed > OFFLINE_THRESHOLD_MINUTES * 60:
                status = "offline"

        # Calculate uptime percentages (lock-free helpers)
        uptime_24h = await self._get_camera_uptime_locked(camera_id, since=now - timedelta(hours=24))
        uptime_7d = await self._get_camera_uptime_locked(camera_id, since=now - timedelta(hours=168))
        errors_24h = await self._get_camera_error_count_locked(camera_id, since=now - timedelta(hours=24))
        errors_7d = await self._get_camera_error_count_locked(camera_id, since=now - timedelta(days=7))

        return CameraHealth(
            camera_id=camera_id,
            camera_name=info.get("camera_name", camera_id),
            status=status,
            last_heartbeat=hb["last_heartbeat"],
            uptime_pct_24h=round(uptime_24h, 2),
            uptime_pct_7d=round(uptime_7d, 2),
            error_count_24h=errors_24h,
            error_count_7d=errors_7d,
            location_id=info.get("location_id", ""),
            location_name=info.get("location_name", ""),
        )

    async def _get_camera_uptime_locked(self, camera_id: str, since: datetime) -> float:
        """Calculate uptime without acquiring lock (caller must hold lock).

        Args:
            camera_id: Camera identifier.
            since: Start of the period.

        Returns:
            Uptime percentage (0.0-100.0).
        """
        if camera_id not in self._health_history:
            return 100.0

        snapshots = [s for s in self._health_history[camera_id] if s.timestamp >= since]
        if not snapshots:
            return 100.0

        online_count = sum(1 for s in snapshots if s.status == "online")
        return (online_count / len(snapshots)) * 100.0

    async def _get_camera_error_count_locked(self, camera_id: str, since: datetime) -> int:
        """Get error count without acquiring lock (caller must hold lock).

        Args:
            camera_id: Camera identifier.
            since: Start of the period.

        Returns:
            Number of error heartbeats.
        """
        if camera_id not in self._health_history:
            return 0

        snapshots = [s for s in self._health_history[camera_id] if s.timestamp >= since]
        return sum(1 for s in snapshots if s.status == "error")
