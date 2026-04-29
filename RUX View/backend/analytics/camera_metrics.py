"""
camera_metrics.py — Per-Camera Metrics & Analytics for Vision OS.

Tracks per-camera: triggers/day, AI cost, bandwidth usage, events generated.
Daily metrics stored for 90 days. Cost estimates based on Gemini 2.0 Flash
pricing ($0.00010/image). Supports up to 10 cameras per user.

All calls async (D026).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────
METRICS_RETENTION_DAYS = 90
GEMINI_FLASH_COST_PER_IMAGE = 0.00010  # $0.00010/image
STORAGE_COST_PER_GB_PER_DAY = 0.003  # $0.003/GB/day
BANDWIDTH_COST_PER_GB = 0.02  # $0.02/GB


@dataclass
class DailyCameraMetrics:
    """Aggregated metrics for a single camera on a single day."""
    camera_id: str
    date: date
    total_triggers: int = 0
    ai_calls: int = 0
    ai_cost_total: float = 0.0
    bandwidth_bytes: int = 0
    events_generated: int = 0
    high_threat_events: int = 0
    avg_frame_size_bytes: float = 0.0
    uptime_pct: float = 100.0


@dataclass
class CostBreakdown:
    """Cost breakdown for a camera over a period."""
    camera_id: str
    period_days: int
    total_ai_cost: float = 0.0
    total_storage_cost: float = 0.0
    total_bandwidth_cost: float = 0.0
    total_cost: float = 0.0
    cost_per_day: float = 0.0
    cost_per_trigger: float = 0.0


@dataclass
class BandwidthSummary:
    """Bandwidth usage summary for a camera over a period."""
    camera_id: str
    period_days: int
    total_bytes: int = 0
    total_mb: float = 0.0
    avg_daily_mb: float = 0.0
    peak_daily_mb: float = 0.0


class CameraMetricsCollector:
    """Collects and analyzes per-camera metrics.

    Maintains in-memory stores for triggers, AI calls, and daily metrics.
    In production, this would persist to a database.
    """

    def __init__(self):
        """Initialize the metrics collector with empty stores."""
        self._triggers: dict[str, list[dict]] = {}  # camera_id -> trigger events
        self._ai_calls: dict[str, list[dict]] = {}  # camera_id -> AI call records
        self._daily_metrics: dict[str, dict[date, DailyCameraMetrics]] = {}  # camera_id -> date -> metrics
        self._lock = asyncio.Lock()

    # ── Recording ───────────────────────────────────────────────

    async def record_trigger(self, camera_id: str, frame_size_bytes: int) -> dict:
        """Record a trigger event for a camera.

        Args:
            camera_id: Camera identifier.
            frame_size_bytes: Size of the frame in bytes.

        Returns:
            Dict with trigger acknowledgement.
        """
        now = datetime.now(timezone.utc)

        async with self._lock:
            if camera_id not in self._triggers:
                self._triggers[camera_id] = []

            self._triggers[camera_id].append({
                "timestamp": now,
                "frame_size_bytes": frame_size_bytes,
            })

            # Update daily metrics
            today = now.date()
            await self._ensure_daily_metrics(camera_id, today)
            dm = self._daily_metrics[camera_id][today]
            dm.total_triggers += 1
            dm.bandwidth_bytes += frame_size_bytes

            # Recalculate average frame size
            total_frames = dm.total_triggers
            dm.avg_frame_size_bytes = round(
                (dm.avg_frame_size_bytes * (total_frames - 1) + frame_size_bytes) / total_frames,
                2,
            )

        return {
            "camera_id": camera_id,
            "trigger_count": self._triggers[camera_id][-1:][0],
            "total_triggers_today": dm.total_triggers,
        }

    async def record_ai_call(self, camera_id: str, model: str, cost: float) -> dict:
        """Record an AI call for a camera.

        Args:
            camera_id: Camera identifier.
            model: AI model used (e.g., "gemini-2.0-flash").
            cost: Cost of the AI call in USD.

        Returns:
            Dict with AI call acknowledgement.
        """
        now = datetime.now(timezone.utc)

        async with self._lock:
            if camera_id not in self._ai_calls:
                self._ai_calls[camera_id] = []

            self._ai_calls[camera_id].append({
                "timestamp": now,
                "model": model,
                "cost": cost,
            })

            # Update daily metrics
            today = now.date()
            await self._ensure_daily_metrics(camera_id, today)
            dm = self._daily_metrics[camera_id][today]
            dm.ai_calls += 1
            dm.ai_cost_total = round(dm.ai_cost_total + cost, 6)

        return {
            "camera_id": camera_id,
            "model": model,
            "cost": cost,
            "total_ai_calls_today": dm.ai_calls,
        }

    # ── Metrics Queries ─────────────────────────────────────────

    async def get_daily_metrics(self, camera_id: str, query_date: date) -> Optional[DailyCameraMetrics]:
        """Get daily metrics for a specific camera and date.

        Args:
            camera_id: Camera identifier.
            query_date: Date to query.

        Returns:
            DailyCameraMetrics or None if not found.
        """
        async with self._lock:
            if camera_id not in self._daily_metrics:
                return None
            return self._daily_metrics[camera_id].get(query_date)

    async def get_metrics_range(self, camera_id: str, start: date, end: date) -> list[DailyCameraMetrics]:
        """Get daily metrics for a camera over a date range.

        Args:
            camera_id: Camera identifier.
            start: Start date (inclusive).
            end: End date (inclusive).

        Returns:
            List of DailyCameraMetrics sorted by date.
        """
        async with self._lock:
            if camera_id not in self._daily_metrics:
                return []

            results = []
            for d in self._daily_metrics[camera_id]:
                if start <= d <= end:
                    results.append(self._daily_metrics[camera_id][d])

            return sorted(results, key=lambda x: x.date)

    async def get_all_cameras_metrics(self, user_id: str, query_date: date) -> list[DailyCameraMetrics]:
        """Get daily metrics for all cameras of a user on a specific date.

        Args:
            user_id: User UUID.
            query_date: Date to query.

        Returns:
            List of DailyCameraMetrics.
        """
        async with self._lock:
            results = []
            for cid, metrics_dict in self._daily_metrics.items():
                if query_date in metrics_dict:
                    results.append(metrics_dict[query_date])
            return results

    async def get_cost_breakdown(self, camera_id: str, days: int = 30) -> CostBreakdown:
        """Get cost breakdown for a camera over a period.

        Args:
            camera_id: Camera identifier.
            days: Number of days to analyze.

        Returns:
            CostBreakdown dataclass.
        """
        end = date.today()
        start = end - timedelta(days=days)

        metrics_list = await self.get_metrics_range(camera_id, start, end)

        total_ai = sum(m.ai_cost_total for m in metrics_list)
        total_triggers = sum(m.total_triggers for m in metrics_list)
        total_bandwidth_bytes = sum(m.bandwidth_bytes for m in metrics_list)
        total_bandwidth_gb = total_bandwidth_bytes / (1024 ** 3)

        # Storage cost: estimate based on events stored
        total_events = sum(m.events_generated for m in metrics_list)
        estimated_storage_gb = total_events * 0.0005  # ~0.5MB per event
        total_storage = estimated_storage_gb * STORAGE_COST_PER_GB_PER_DAY * days

        total_bandwidth_cost = total_bandwidth_gb * BANDWIDTH_COST_PER_GB
        total_cost = total_ai + total_storage + total_bandwidth_cost
        cost_per_day = total_cost / max(days, 1)
        cost_per_trigger = total_cost / max(total_triggers, 1)

        return CostBreakdown(
            camera_id=camera_id,
            period_days=days,
            total_ai_cost=round(total_ai, 6),
            total_storage_cost=round(total_storage, 6),
            total_bandwidth_cost=round(total_bandwidth_cost, 6),
            total_cost=round(total_cost, 6),
            cost_per_day=round(cost_per_day, 6),
            cost_per_trigger=round(cost_per_trigger, 6),
        )

    async def get_bandwidth_usage(self, camera_id: str, days: int = 30) -> BandwidthSummary:
        """Get bandwidth usage summary for a camera over a period.

        Args:
            camera_id: Camera identifier.
            days: Number of days to analyze.

        Returns:
            BandwidthSummary dataclass.
        """
        end = date.today()
        start = end - timedelta(days=days)

        metrics_list = await self.get_metrics_range(camera_id, start, end)

        if not metrics_list:
            return BandwidthSummary(
                camera_id=camera_id,
                period_days=days,
            )

        total_bytes = sum(m.bandwidth_bytes for m in metrics_list)
        total_mb = total_bytes / (1024 * 1024)
        daily_mbs = [m.bandwidth_bytes / (1024 * 1024) for m in metrics_list]
        avg_daily_mb = total_mb / max(len(metrics_list), 1)
        peak_daily_mb = max(daily_mbs) if daily_mbs else 0.0

        return BandwidthSummary(
            camera_id=camera_id,
            period_days=days,
            total_bytes=total_bytes,
            total_mb=round(total_mb, 2),
            avg_daily_mb=round(avg_daily_mb, 2),
            peak_daily_mb=round(peak_daily_mb, 2),
        )

    async def get_trigger_trend(self, camera_id: str, days: int = 30) -> list[dict]:
        """Get trigger count trend for a camera over a period.

        Args:
            camera_id: Camera identifier.
            days: Number of days to analyze.

        Returns:
            List of dicts with date and trigger_count.
        """
        end = date.today()
        start = end - timedelta(days=days)

        metrics_list = await self.get_metrics_range(camera_id, start, end)

        return [
            {
                "date": m.date.isoformat(),
                "trigger_count": m.total_triggers,
                "ai_calls": m.ai_calls,
                "events_generated": m.events_generated,
            }
            for m in metrics_list
        ]

    async def compute_daily_summary(self, camera_id: str, summary_date: date) -> DailyCameraMetrics:
        """Compute daily summary for a camera by aggregating raw data.

        Args:
            camera_id: Camera identifier.
            summary_date: Date to compute summary for.

        Returns:
            DailyCameraMetrics with aggregated data.
        """
        async with self._lock:
            # Count triggers for the day
            trigger_count = 0
            total_frame_bytes = 0
            if camera_id in self._triggers:
                day_triggers = [
                    t for t in self._triggers[camera_id]
                    if t["timestamp"].date() == summary_date
                ]
                trigger_count = len(day_triggers)
                total_frame_bytes = sum(t["frame_size_bytes"] for t in day_triggers)

            # Count AI calls for the day
            ai_count = 0
            ai_cost = 0.0
            if camera_id in self._ai_calls:
                day_calls = [
                    c for c in self._ai_calls[camera_id]
                    if c["timestamp"].date() == summary_date
                ]
                ai_count = len(day_calls)
                ai_cost = sum(c["cost"] for c in day_calls)

            avg_frame = round(total_frame_bytes / max(trigger_count, 1), 2)

            metrics = DailyCameraMetrics(
                camera_id=camera_id,
                date=summary_date,
                total_triggers=trigger_count,
                ai_calls=ai_count,
                ai_cost_total=round(ai_cost, 6),
                bandwidth_bytes=total_frame_bytes,
                events_generated=0,
                high_threat_events=0,
                avg_frame_size_bytes=avg_frame,
                uptime_pct=100.0,
            )

            # Store the computed summary
            await self._ensure_daily_metrics(camera_id, summary_date)
            self._daily_metrics[camera_id][summary_date] = metrics

            return metrics

    async def get_top_triggers_cameras(self, user_id: str, limit: int = 10) -> list[dict]:
        """Get cameras with the most triggers, ordered descending.

        Args:
            user_id: User UUID.
            limit: Maximum number of cameras to return.

        Returns:
            List of dicts with camera_id and total_triggers.
        """
        async with self._lock:
            camera_totals = []
            for cid, metrics_dict in self._daily_metrics.items():
                total = sum(m.total_triggers for m in metrics_dict.values())
                camera_totals.append({
                    "camera_id": cid,
                    "total_triggers": total,
                })

            camera_totals.sort(key=lambda x: x["total_triggers"], reverse=True)
            return camera_totals[:limit]

    # ── Internal Helpers ────────────────────────────────────────

    async def _ensure_daily_metrics(self, camera_id: str, target_date: date) -> None:
        """Ensure daily metrics entry exists for a camera and date.

        Args:
            camera_id: Camera identifier.
            target_date: Date to ensure metrics for.
        """
        if camera_id not in self._daily_metrics:
            self._daily_metrics[camera_id] = {}

        if target_date not in self._daily_metrics[camera_id]:
            self._daily_metrics[camera_id][target_date] = DailyCameraMetrics(
                camera_id=camera_id,
                date=target_date,
            )

    async def _enforce_retention(self) -> None:
        """Remove metrics older than retention period."""
        cutoff = date.today() - timedelta(days=METRICS_RETENTION_DAYS)

        async with self._lock:
            for cid in list(self._daily_metrics.keys()):
                old_dates = [d for d in self._daily_metrics[cid] if d < cutoff]
                for d in old_dates:
                    del self._daily_metrics[cid][d]
