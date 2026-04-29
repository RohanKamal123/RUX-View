"""Tests for Sprint 8.2 — Camera Metrics & Analytics."""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.analytics.camera_metrics import (
    CameraMetricsCollector,
    DailyCameraMetrics,
    CostBreakdown,
    BandwidthSummary,
    METRICS_RETENTION_DAYS,
    GEMINI_FLASH_COST_PER_IMAGE,
)


@pytest.fixture
def metrics_collector():
    """Create a fresh CameraMetricsCollector for each test."""
    return CameraMetricsCollector()


class TestCameraMetricsCollector:
    """Tests for CameraMetricsCollector class."""

    @pytest.mark.asyncio
    async def test_record_trigger_increments_count(self, metrics_collector):
        """Test that recording a trigger increments the trigger count."""
        result = await metrics_collector.record_trigger("cam-001", 50000)
        assert result["camera_id"] == "cam-001"

        today = date.today()
        dm = await metrics_collector.get_daily_metrics("cam-001", today)
        assert dm is not None
        assert dm.total_triggers == 1
        assert dm.bandwidth_bytes == 50000

    @pytest.mark.asyncio
    async def test_record_ai_call_tracks_cost(self, metrics_collector):
        """Test that recording an AI call tracks the cost."""
        result = await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)
        assert result["camera_id"] == "cam-001"
        assert result["cost"] == 0.00010

        today = date.today()
        dm = await metrics_collector.get_daily_metrics("cam-001", today)
        assert dm is not None
        assert dm.ai_calls == 1
        assert dm.ai_cost_total == 0.00010

    @pytest.mark.asyncio
    async def test_get_daily_metrics_returns_data(self, metrics_collector):
        """Test that get_daily_metrics returns correct data."""
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)

        today = date.today()
        dm = await metrics_collector.get_daily_metrics("cam-001", today)
        assert dm is not None
        assert dm.camera_id == "cam-001"
        assert dm.date == today
        assert dm.total_triggers == 1
        assert dm.ai_calls == 1
        assert dm.ai_cost_total == 0.00010

    @pytest.mark.asyncio
    async def test_get_metrics_range_returns_list(self, metrics_collector):
        """Test that get_metrics_range returns list of metrics."""
        await metrics_collector.record_trigger("cam-001", 50000)

        today = date.today()
        start = today - timedelta(days=1)
        end = today + timedelta(days=1)

        metrics_list = await metrics_collector.get_metrics_range("cam-001", start, end)
        assert len(metrics_list) == 1
        assert metrics_list[0].date == today

    @pytest.mark.asyncio
    async def test_get_all_cameras_metrics(self, metrics_collector):
        """Test that get_all_cameras_metrics returns metrics for all cameras."""
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-002", 75000)

        today = date.today()
        all_metrics = await metrics_collector.get_all_cameras_metrics("user-001", today)
        assert len(all_metrics) == 2

    @pytest.mark.asyncio
    async def test_cost_breakdown_calculates_correctly(self, metrics_collector):
        """Test that cost breakdown calculates correctly."""
        # Record some triggers and AI calls
        for _ in range(10):
            await metrics_collector.record_trigger("cam-001", 50000)
            await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)

        breakdown = await metrics_collector.get_cost_breakdown("cam-001", days=30)
        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.camera_id == "cam-001"
        assert breakdown.period_days == 30
        assert breakdown.total_ai_cost == 0.0010  # 10 * 0.00010
        assert breakdown.total_cost > 0
        assert breakdown.cost_per_day > 0
        assert breakdown.cost_per_trigger > 0

    @pytest.mark.asyncio
    async def test_bandwidth_usage_summary(self, metrics_collector):
        """Test that bandwidth usage summary is correct."""
        # Record triggers with varying frame sizes
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-001", 75000)
        await metrics_collector.record_trigger("cam-001", 100000)

        bandwidth = await metrics_collector.get_bandwidth_usage("cam-001", days=30)
        assert isinstance(bandwidth, BandwidthSummary)
        assert bandwidth.camera_id == "cam-001"
        assert bandwidth.total_bytes == 225000  # 50000 + 75000 + 100000
        assert bandwidth.total_mb > 0
        assert bandwidth.avg_daily_mb > 0
        assert bandwidth.peak_daily_mb > 0

    @pytest.mark.asyncio
    async def test_trigger_trend_returns_daily_counts(self, metrics_collector):
        """Test that trigger trend returns daily counts."""
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-001", 60000)

        trend = await metrics_collector.get_trigger_trend("cam-001", days=30)
        assert len(trend) >= 1
        assert "date" in trend[0]
        assert "trigger_count" in trend[0]
        assert trend[0]["trigger_count"] == 2

    @pytest.mark.asyncio
    async def test_compute_daily_summary_aggregates(self, metrics_collector):
        """Test that compute_daily_summary aggregates raw data."""
        # Record raw data
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-001", 75000)
        await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)
        await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)

        today = date.today()
        summary = await metrics_collector.compute_daily_summary("cam-001", today)
        assert summary.total_triggers == 2
        assert summary.ai_calls == 2
        assert summary.ai_cost_total == 0.00020
        assert summary.bandwidth_bytes == 125000  # 50000 + 75000

    @pytest.mark.asyncio
    async def test_top_triggers_cameras_ordered(self, metrics_collector):
        """Test that top triggers cameras are ordered by trigger count."""
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-002", 50000)

        top = await metrics_collector.get_top_triggers_cameras("user-001", limit=5)
        assert len(top) == 2
        assert top[0]["camera_id"] == "cam-001"  # Most triggers
        assert top[0]["total_triggers"] == 2
        assert top[1]["total_triggers"] == 1

    @pytest.mark.asyncio
    async def test_metrics_retention_90_days(self, metrics_collector):
        """Test that metrics older than 90 days are removed."""
        # Add some recent metrics
        await metrics_collector.record_trigger("cam-001", 50000)

        # Manually add old metrics
        old_date = date.today() - timedelta(days=METRICS_RETENTION_DAYS + 1)
        metrics_collector._daily_metrics["cam-001"] = {
            old_date: DailyCameraMetrics(camera_id="cam-001", date=old_date),
            date.today(): DailyCameraMetrics(camera_id="cam-001", date=date.today()),
        }

        # Enforce retention
        await metrics_collector._enforce_retention()

        # Old date should be removed
        assert old_date not in metrics_collector._daily_metrics["cam-001"]
        assert date.today() in metrics_collector._daily_metrics["cam-001"]

    @pytest.mark.asyncio
    async def test_concurrent_metric_recording(self, metrics_collector):
        """Test that concurrent metric recording works correctly."""
        import asyncio

        async def record():
            await metrics_collector.record_trigger("cam-001", 50000)
            await metrics_collector.record_ai_call("cam-001", "gemini-2.0-flash", 0.00010)

        tasks = [record() for _ in range(5)]
        await asyncio.gather(*tasks)

        today = date.today()
        dm = await metrics_collector.get_daily_metrics("cam-001", today)
        assert dm.total_triggers == 5
        assert dm.ai_calls == 5

    @pytest.mark.asyncio
    async def test_get_daily_metrics_returns_none_for_unknown(self, metrics_collector):
        """Test that get_daily_metrics returns None for unknown camera."""
        today = date.today()
        dm = await metrics_collector.get_daily_metrics("unknown-cam", today)
        assert dm is None

    @pytest.mark.asyncio
    async def test_avg_frame_size_calculation(self, metrics_collector):
        """Test that average frame size is calculated correctly."""
        await metrics_collector.record_trigger("cam-001", 50000)
        await metrics_collector.record_trigger("cam-001", 100000)

        today = date.today()
        dm = await metrics_collector.get_daily_metrics("cam-001", today)
        assert dm.avg_frame_size_bytes == 75000.0  # (50000 + 100000) / 2
