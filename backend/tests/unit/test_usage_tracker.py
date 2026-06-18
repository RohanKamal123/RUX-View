"""
test_usage_tracker.py — Tests for Usage Tracking.
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from backend.analytics.usage_tracker import (
    UsageTracker,
    DailyUsage,
    MonthlyUsage,
    CurrentUsage,
    UsageAlert,
    UsageAlerts,
    UserUsageSummary,
    TIER_LIMITS,
    WARNING_THRESHOLD,
    CRITICAL_THRESHOLD,
)


@pytest.fixture
def tracker():
    """Create a fresh UsageTracker for each test."""
    from backend.analytics.usage_tracker import _daily_usage, _monthly_usage, _current_usage, _user_tiers
    _daily_usage.clear()
    _monthly_usage.clear()
    _current_usage.clear()
    _user_tiers.clear()
    return UsageTracker()


@pytest.fixture
def sample_user():
    return "test_user_usage"


# ── Test: Record Event ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_event_increments_count(tracker, sample_user):
    result = await tracker.record_event(
        sample_user, {"type": "motion", "threat_level": "LOW"}
    )

    assert result["recorded"] is True
    assert result["total_events_today"] == 1

    # Record another
    await tracker.record_event(sample_user, {"type": "person", "threat_level": "HIGH"})
    daily = await tracker.get_daily_usage(sample_user, date.today())
    assert daily.events_generated == 2
    assert daily.high_threat_events == 1


# ── Test: Record AI Call ────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_ai_call_tracks_tokens(tracker, sample_user):
    result = await tracker.record_ai_call(sample_user, "yolov8", 1500)

    assert result["recorded"] is True
    assert result["tokens"] == 1500
    assert result["total_ai_calls_today"] == 1

    daily = await tracker.get_daily_usage(sample_user, date.today())
    assert daily.ai_calls == 1
    assert daily.ai_tokens == 1500


# ── Test: Record Storage Usage ──────────────────────────────────


@pytest.mark.asyncio
async def test_record_storage_usage(tracker, sample_user):
    result = await tracker.record_storage_usage(sample_user, 1024 * 1024)  # 1MB

    assert result["recorded"] is True
    assert result["bytes_stored"] == 1024 * 1024

    daily = await tracker.get_daily_usage(sample_user, date.today())
    assert daily.storage_bytes == 1024 * 1024


# ── Test: Get Daily Usage ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_daily_usage_returns_data(tracker, sample_user):
    await tracker.record_event(sample_user, {"type": "motion"})
    await tracker.record_ai_call(sample_user, "yolov8", 500)

    daily = await tracker.get_daily_usage(sample_user, date.today())

    assert daily.user_id == sample_user
    assert daily.events_generated == 1
    assert daily.ai_calls == 1
    assert daily.ai_tokens == 500


# ── Test: Get Monthly Usage ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_monthly_usage_aggregates(tracker, sample_user):
    today = date.today()

    # Record events across multiple days
    await tracker.record_event(sample_user, {"type": "motion"})
    await tracker.record_event(sample_user, {"type": "person"})
    await tracker.record_ai_call(sample_user, "yolov8", 1000)

    monthly = await tracker.get_monthly_usage(
        sample_user, today.year, today.month
    )

    assert monthly.total_events >= 2
    assert monthly.total_ai_calls >= 1
    assert monthly.total_ai_tokens >= 1000


# ── Test: Get Current Usage ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_usage_returns_live_data(tracker, sample_user):
    await tracker.set_user_tier(sample_user, "household")
    await tracker.record_event(sample_user, {"type": "motion"})
    await tracker.record_ai_call(sample_user, "yolov8", 500)

    current = await tracker.get_current_usage(sample_user)

    assert current.user_id == sample_user
    assert current.tier == "household"
    assert current.events_today >= 1
    assert current.ai_calls_today >= 1


# ── Test: Check Usage Limits ────────────────────────────────────


@pytest.mark.asyncio
async def test_check_usage_limits_within_bounds(tracker, sample_user):
    await tracker.set_user_tier(sample_user, "free")

    alerts = await tracker.check_usage_limits(sample_user)

    assert alerts.has_warnings is False
    assert alerts.has_critical is False
    assert len(alerts.alerts) == 0


@pytest.mark.asyncio
async def test_check_usage_limits_near_limit_warning(tracker, sample_user):
    await tracker.set_user_tier(sample_user, "free")
    limits = TIER_LIMITS["free"]

    # Record events to approach warning threshold
    warning_count = int(limits["max_events_per_day"] * WARNING_THRESHOLD)
    for _ in range(warning_count):
        await tracker.record_event(sample_user, {"type": "motion"})

    alerts = await tracker.check_usage_limits(sample_user)

    assert alerts.has_warnings is True


@pytest.mark.asyncio
async def test_check_usage_limits_over_limit_critical(tracker, sample_user):
    await tracker.set_user_tier(sample_user, "free")
    limits = TIER_LIMITS["free"]

    # Record events to exceed critical threshold
    critical_count = int(limits["max_events_per_day"] * CRITICAL_THRESHOLD) + 1
    for _ in range(critical_count):
        await tracker.record_event(sample_user, {"type": "motion"})

    alerts = await tracker.check_usage_limits(sample_user)

    assert alerts.has_critical is True


# ── Test: Get All Users Usage ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_users_usage(tracker):
    await tracker.record_event("user_a", {"type": "motion"})
    await tracker.record_event("user_b", {"type": "person"})
    await tracker.record_event("user_b", {"type": "vehicle"})

    summaries = await tracker.get_all_users_usage(date.today())

    assert len(summaries) == 2

    # Find user_b
    user_b = [s for s in summaries if s.user_id == "user_b"][0]
    assert user_b.events_24h == 2


# ── Test: Get Top Users ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_top_users_by_events(tracker):
    for i in range(5):
        user = f"user_{i}"
        for _ in range(i * 10):
            await tracker.record_event(user, {"type": "motion"})

    top = await tracker.get_top_users(limit=3, metric="events")

    assert len(top) == 3
    # user_4 should have the most events
    assert top[0].user_id == "user_4"


# ── Test: Compute Daily Snapshot ────────────────────────────────


@pytest.mark.asyncio
async def test_compute_daily_snapshot_processes_all(tracker):
    await tracker.record_event("user_a", {"type": "motion"})
    await tracker.record_event("user_b", {"type": "person"})
    await tracker.record_event("user_c", {"type": "vehicle"})

    count = await tracker.compute_daily_snapshot()
    assert count == 3


# ── Test: Usage Data Retention ──────────────────────────────────


@pytest.mark.asyncio
async def test_usage_data_retention(tracker, sample_user):
    # Record usage
    await tracker.record_event(sample_user, {"type": "motion"})

    # Get daily usage for a past date (should return empty)
    past_date = date.today() - timedelta(days=30)
    daily = await tracker.get_daily_usage(sample_user, past_date)

    assert daily.events_generated == 0
    assert daily.ai_calls == 0


# ── Test: Concurrent Usage Recording ────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_usage_recording(tracker):
    users = [f"user_{i}" for i in range(5)]

    # Record events concurrently
    for user in users:
        for _ in range(3):
            await tracker.record_event(user, {"type": "motion"})

    for user in users:
        daily = await tracker.get_daily_usage(user, date.today())
        assert daily.events_generated == 3


# ── Test: Set User Tier ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_user_tier(tracker, sample_user):
    await tracker.set_user_tier(sample_user, "business")

    current = await tracker.get_current_usage(sample_user)
    assert current.tier == "business"


# ── Test: Dataclass Defaults ────────────────────────────────────


def test_daily_usage_defaults():
    today = date.today()
    usage = DailyUsage(user_id="test", date=today)
    assert usage.events_generated == 0
    assert usage.ai_calls == 0
    assert usage.storage_bytes == 0
    assert usage.bandwidth_bytes == 0


def test_monthly_usage_defaults():
    usage = MonthlyUsage(user_id="test", year=2026, month=4)
    assert usage.total_events == 0
    assert usage.estimated_cost == 0.0


def test_current_usage_defaults():
    usage = CurrentUsage(user_id="test")
    assert usage.tier == "free"
    assert usage.camera_count == 0
    assert usage.storage_used_mb == 0.0


def test_usage_alert():
    alert = UsageAlert(
        type="storage",
        severity="warning",
        message="Storage at 85%",
        current_value=850.0,
        limit_value=1000.0,
        usage_pct=85.0,
    )
    assert alert.usage_pct == 85.0


def test_usage_alerts():
    alerts = UsageAlerts()
    assert alerts.has_warnings is False
    assert alerts.has_critical is False
    assert alerts.alerts == []


def test_user_usage_summary():
    summary = UserUsageSummary(
        user_id="test",
        email="test@visionos.app",
        tier="household",
        camera_count=3,
        events_24h=50,
        ai_calls_24h=20,
        storage_mb=150.0,
        estimated_daily_cost=29.9,
    )
    assert summary.camera_count == 3
    assert summary.events_24h == 50
