"""
usage_tracker.py — Usage Tracking for Vision OS.

Tracks per-user resource usage: camera count, events, AI calls, storage, bandwidth.
Usage limits based on tier (but no hard camera limit — supports up to 10).
Usage alerts when approaching limits.
Daily usage snapshots for billing.
Usage history for trend analysis.
Admin dashboard shows usage across all users.

Key decisions:
- D026: All calls async
- Usage tracked daily for billing accuracy
- Soft limits with warnings (not hard blocks)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────

TIER_LIMITS = {
    "free": {
        "max_events_per_day": 100,
        "max_ai_calls_per_day": 50,
        "max_storage_mb": 500,
        "max_bandwidth_mb": 1000,
    },
    "household": {
        "max_events_per_day": 500,
        "max_ai_calls_per_day": 200,
        "max_storage_mb": 2000,
        "max_bandwidth_mb": 5000,
    },
    "business": {
        "max_events_per_day": 2000,
        "max_ai_calls_per_day": 1000,
        "max_storage_mb": 10000,
        "max_bandwidth_mb": 20000,
    },
}

WARNING_THRESHOLD = 0.8  # 80% usage triggers warning
CRITICAL_THRESHOLD = 0.95  # 95% usage triggers critical


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class DailyUsage:
    """Usage data for a single day."""

    user_id: str
    date: date
    events_generated: int = 0
    ai_calls: int = 0
    ai_tokens: int = 0
    storage_bytes: int = 0
    bandwidth_bytes: int = 0
    active_cameras: int = 0
    alerts_sent: int = 0
    high_threat_events: int = 0


@dataclass
class MonthlyUsage:
    """Aggregated usage for a month."""

    user_id: str
    year: int
    month: int
    total_events: int = 0
    total_ai_calls: int = 0
    total_ai_tokens: int = 0
    avg_daily_storage_bytes: float = 0.0
    total_bandwidth_bytes: int = 0
    avg_active_cameras: float = 0.0
    peak_cameras: int = 0
    estimated_cost: float = 0.0


@dataclass
class CurrentUsage:
    """Real-time current usage for a user."""

    user_id: str
    tier: str = "free"
    camera_count: int = 0
    events_today: int = 0
    events_this_month: int = 0
    ai_calls_today: int = 0
    ai_calls_this_month: int = 0
    storage_used_mb: float = 0.0
    bandwidth_used_mb: float = 0.0
    estimated_monthly_cost: float = 0.0


@dataclass
class UsageAlert:
    """An individual usage alert."""

    type: str  # storage/bandwidth/events/ai_calls
    severity: str  # info/warning/critical
    message: str
    current_value: float
    limit_value: float
    usage_pct: float


@dataclass
class UsageAlerts:
    """Collection of usage alerts for a user."""

    alerts: list[UsageAlert] = field(default_factory=list)
    has_warnings: bool = False
    has_critical: bool = False


@dataclass
class UserUsageSummary:
    """Summary of a user's usage for admin dashboard."""

    user_id: str
    email: str
    tier: str
    camera_count: int
    events_24h: int
    ai_calls_24h: int
    storage_mb: float
    estimated_daily_cost: float


# ── In-Memory Store (replace with DB in production) ────────────

_daily_usage: dict[str, dict[str, DailyUsage]] = {}  # user_id -> {date_str -> DailyUsage}
_monthly_usage: dict[str, dict[str, MonthlyUsage]] = {}  # user_id -> {year-month -> MonthlyUsage}
_current_usage: dict[str, CurrentUsage] = {}
_user_tiers: dict[str, str] = {}  # user_id -> tier


# ── UsageTracker ────────────────────────────────────────────────


class UsageTracker:
    """Tracks per-user resource usage and generates alerts."""

    async def record_event(self, user_id: str, event_data: dict) -> dict:
        """Record a detection event.

        Args:
            user_id: Unique user identifier.
            event_data: Dict with event details (type, threat_level, etc.).

        Returns:
            Dict with recording confirmation.
        """
        today = date.today()
        daily = await self._get_or_create_daily(user_id, today)

        daily.events_generated += 1
        if event_data.get("threat_level") in ("HIGH", "EMERGENCY"):
            daily.high_threat_events += 1

        return {
            "recorded": True,
            "user_id": user_id,
            "date": today.isoformat(),
            "total_events_today": daily.events_generated,
        }

    async def record_ai_call(
        self, user_id: str, model: str, tokens: int
    ) -> dict:
        """Record an AI model call.

        Args:
            user_id: Unique user identifier.
            model: AI model name.
            tokens: Number of tokens used.

        Returns:
            Dict with recording confirmation.
        """
        today = date.today()
        daily = await self._get_or_create_daily(user_id, today)

        daily.ai_calls += 1
        daily.ai_tokens += tokens

        return {
            "recorded": True,
            "user_id": user_id,
            "model": model,
            "tokens": tokens,
            "total_ai_calls_today": daily.ai_calls,
        }

    async def record_storage_usage(
        self, user_id: str, bytes_stored: int
    ) -> dict:
        """Record storage usage.

        Args:
            user_id: Unique user identifier.
            bytes_stored: Number of bytes stored.

        Returns:
            Dict with recording confirmation.
        """
        today = date.today()
        daily = await self._get_or_create_daily(user_id, today)

        daily.storage_bytes += bytes_stored

        return {
            "recorded": True,
            "user_id": user_id,
            "bytes_stored": bytes_stored,
            "total_storage_bytes": daily.storage_bytes,
        }

    async def get_daily_usage(
        self, user_id: str, query_date: date
    ) -> DailyUsage:
        """Get usage data for a specific day.

        Args:
            user_id: Unique user identifier.
            query_date: Date to query.

        Returns:
            DailyUsage for that date.
        """
        user_data = _daily_usage.get(user_id, {})
        date_key = query_date.isoformat()
        return user_data.get(
            date_key,
            DailyUsage(user_id=user_id, date=query_date),
        )

    async def get_monthly_usage(
        self, user_id: str, year: int, month: int
    ) -> MonthlyUsage:
        """Get aggregated usage for a month.

        Args:
            user_id: Unique user identifier.
            year: Year.
            month: Month (1-12).

        Returns:
            MonthlyUsage with aggregated data.
        """
        month_key = f"{year}-{month:02d}"
        user_monthly = _monthly_usage.get(user_id, {})
        monthly = user_monthly.get(month_key)

        if monthly:
            return monthly

        # Aggregate from daily data
        user_data = _daily_usage.get(user_id, {})
        total_events = 0
        total_ai_calls = 0
        total_ai_tokens = 0
        total_storage = 0
        total_bandwidth = 0
        total_cameras = 0
        peak_cameras = 0
        days_count = 0

        for date_key, daily in user_data.items():
            try:
                d = date.fromisoformat(date_key)
                if d.year == year and d.month == month:
                    total_events += daily.events_generated
                    total_ai_calls += daily.ai_calls
                    total_ai_tokens += daily.ai_tokens
                    total_storage += daily.storage_bytes
                    total_bandwidth += daily.bandwidth_bytes
                    total_cameras += daily.active_cameras
                    peak_cameras = max(peak_cameras, daily.active_cameras)
                    days_count += 1
            except ValueError:
                continue

        avg_storage = total_storage / max(days_count, 1)
        avg_cameras = total_cameras / max(days_count, 1)

        # Estimate cost based on tier
        tier = _user_tiers.get(user_id, "free")
        price_per_camera = {"free": 0, "household": 299, "business": 499}.get(tier, 0)
        estimated_cost = avg_cameras * price_per_camera

        monthly = MonthlyUsage(
            user_id=user_id,
            year=year,
            month=month,
            total_events=total_events,
            total_ai_calls=total_ai_calls,
            total_ai_tokens=total_ai_tokens,
            avg_daily_storage_bytes=avg_storage,
            total_bandwidth_bytes=total_bandwidth,
            avg_active_cameras=avg_cameras,
            peak_cameras=peak_cameras,
            estimated_cost=estimated_cost,
        )

        if user_id not in _monthly_usage:
            _monthly_usage[user_id] = {}
        _monthly_usage[user_id][month_key] = monthly

        return monthly

    async def get_current_usage(self, user_id: str) -> CurrentUsage:
        """Get real-time current usage for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            CurrentUsage with live data.
        """
        today = date.today()
        daily = await self.get_daily_usage(user_id, today)
        monthly = await self.get_monthly_usage(
            user_id, today.year, today.month
        )

        tier = _user_tiers.get(user_id, "free")
        price_per_camera = {"free": 0, "household": 299, "business": 499}.get(tier, 0)

        return CurrentUsage(
            user_id=user_id,
            tier=tier,
            camera_count=daily.active_cameras,
            events_today=daily.events_generated,
            events_this_month=monthly.total_events,
            ai_calls_today=daily.ai_calls,
            ai_calls_this_month=monthly.total_ai_calls,
            storage_used_mb=daily.storage_bytes / (1024 * 1024),
            bandwidth_used_mb=daily.bandwidth_bytes / (1024 * 1024),
            estimated_monthly_cost=monthly.estimated_cost,
        )

    async def check_usage_limits(self, user_id: str) -> UsageAlerts:
        """Check usage against tier limits and generate alerts.

        Args:
            user_id: Unique user identifier.

        Returns:
            UsageAlerts with any warnings or critical alerts.
        """
        today = date.today()
        daily = await self.get_daily_usage(user_id, today)
        tier = _user_tiers.get(user_id, "free")
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])

        alerts = []
        has_warnings = False
        has_critical = False

        # Check events
        events_pct = daily.events_generated / max(limits["max_events_per_day"], 1)
        if events_pct >= CRITICAL_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="events",
                    severity="critical",
                    message=f"Events near daily limit: {daily.events_generated}/{limits['max_events_per_day']}",
                    current_value=daily.events_generated,
                    limit_value=limits["max_events_per_day"],
                    usage_pct=events_pct * 100,
                )
            )
            has_critical = True
        elif events_pct >= WARNING_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="events",
                    severity="warning",
                    message=f"Events approaching limit: {daily.events_generated}/{limits['max_events_per_day']}",
                    current_value=daily.events_generated,
                    limit_value=limits["max_events_per_day"],
                    usage_pct=events_pct * 100,
                )
            )
            has_warnings = True

        # Check AI calls
        ai_pct = daily.ai_calls / max(limits["max_ai_calls_per_day"], 1)
        if ai_pct >= CRITICAL_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="ai_calls",
                    severity="critical",
                    message=f"AI calls near daily limit: {daily.ai_calls}/{limits['max_ai_calls_per_day']}",
                    current_value=daily.ai_calls,
                    limit_value=limits["max_ai_calls_per_day"],
                    usage_pct=ai_pct * 100,
                )
            )
            has_critical = True
        elif ai_pct >= WARNING_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="ai_calls",
                    severity="warning",
                    message=f"AI calls approaching limit: {daily.ai_calls}/{limits['max_ai_calls_per_day']}",
                    current_value=daily.ai_calls,
                    limit_value=limits["max_ai_calls_per_day"],
                    usage_pct=ai_pct * 100,
                )
            )
            has_warnings = True

        # Check storage
        storage_mb = daily.storage_bytes / (1024 * 1024)
        storage_pct = storage_mb / max(limits["max_storage_mb"], 1)
        if storage_pct >= CRITICAL_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="storage",
                    severity="critical",
                    message=f"Storage near limit: {storage_mb:.1f}MB/{limits['max_storage_mb']}MB",
                    current_value=storage_mb,
                    limit_value=limits["max_storage_mb"],
                    usage_pct=storage_pct * 100,
                )
            )
            has_critical = True
        elif storage_pct >= WARNING_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="storage",
                    severity="warning",
                    message=f"Storage approaching limit: {storage_mb:.1f}MB/{limits['max_storage_mb']}MB",
                    current_value=storage_mb,
                    limit_value=limits["max_storage_mb"],
                    usage_pct=storage_pct * 100,
                )
            )
            has_warnings = True

        # Check bandwidth
        bandwidth_mb = daily.bandwidth_bytes / (1024 * 1024)
        bw_pct = bandwidth_mb / max(limits["max_bandwidth_mb"], 1)
        if bw_pct >= CRITICAL_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="bandwidth",
                    severity="critical",
                    message=f"Bandwidth near limit: {bandwidth_mb:.1f}MB/{limits['max_bandwidth_mb']}MB",
                    current_value=bandwidth_mb,
                    limit_value=limits["max_bandwidth_mb"],
                    usage_pct=bw_pct * 100,
                )
            )
            has_critical = True
        elif bw_pct >= WARNING_THRESHOLD:
            alerts.append(
                UsageAlert(
                    type="bandwidth",
                    severity="warning",
                    message=f"Bandwidth approaching limit: {bandwidth_mb:.1f}MB/{limits['max_bandwidth_mb']}MB",
                    current_value=bandwidth_mb,
                    limit_value=limits["max_bandwidth_mb"],
                    usage_pct=bw_pct * 100,
                )
            )
            has_warnings = True

        return UsageAlerts(
            alerts=alerts,
            has_warnings=has_warnings,
            has_critical=has_critical,
        )

    async def get_all_users_usage(
        self, query_date: date
    ) -> list[UserUsageSummary]:
        """Get usage summary for all users (admin dashboard).

        Args:
            query_date: Date to query.

        Returns:
            List of UserUsageSummary.
        """
        summaries = []
        for user_id in _daily_usage:
            daily = await self.get_daily_usage(user_id, query_date)
            tier = _user_tiers.get(user_id, "free")
            price_per_camera = {"free": 0, "household": 299, "business": 499}.get(tier, 0)

            summaries.append(
                UserUsageSummary(
                    user_id=user_id,
                    email=f"{user_id}@visionos.app",
                    tier=tier,
                    camera_count=daily.active_cameras,
                    events_24h=daily.events_generated,
                    ai_calls_24h=daily.ai_calls,
                    storage_mb=daily.storage_bytes / (1024 * 1024),
                    estimated_daily_cost=daily.active_cameras * price_per_camera / 30,
                )
            )

        return summaries

    async def get_top_users(
        self, limit: int = 10, metric: str = "events"
    ) -> list[UserUsageSummary]:
        """Get top users by a specific metric.

        Args:
            limit: Maximum number of users.
            metric: Metric to sort by (events/ai_calls/storage).

        Returns:
            List of top UserUsageSummary.
        """
        today = date.today()
        all_users = await self.get_all_users_usage(today)

        if metric == "events":
            all_users.sort(key=lambda u: u.events_24h, reverse=True)
        elif metric == "ai_calls":
            all_users.sort(key=lambda u: u.ai_calls_24h, reverse=True)
        elif metric == "storage":
            all_users.sort(key=lambda u: u.storage_mb, reverse=True)

        return all_users[:limit]

    async def compute_daily_snapshot(self) -> int:
        """Compute daily usage snapshot for all users.

        Returns:
            Number of users processed.
        """
        today = date.today()
        count = 0

        for user_id in list(_daily_usage.keys()):
            # Ensure monthly aggregation is computed
            await self.get_monthly_usage(user_id, today.year, today.month)
            count += 1

        logger.info("Daily snapshot computed for %d users", count)
        return count

    async def set_user_tier(self, user_id: str, tier: str) -> None:
        """Set the tier for a user (used for limit checking).

        Args:
            user_id: Unique user identifier.
            tier: Tier name (free/household/business).
        """
        _user_tiers[user_id] = tier

    async def _get_or_create_daily(
        self, user_id: str, query_date: date
    ) -> DailyUsage:
        """Get or create a DailyUsage record.

        Args:
            user_id: Unique user identifier.
            query_date: Date.

        Returns:
            DailyUsage (existing or new).
        """
        if user_id not in _daily_usage:
            _daily_usage[user_id] = {}

        date_key = query_date.isoformat()
        if date_key not in _daily_usage[user_id]:
            _daily_usage[user_id][date_key] = DailyUsage(
                user_id=user_id, date=query_date
            )

        return _daily_usage[user_id][date_key]
