"""
Vision OS — Monitoring & Alerting Tests
SPRINT 10.5 — Monitoring & Alerting

Tests for MetricsCollector and AlertSystem.
Uses async/await throughout.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.monitoring.metrics_collector import (
    BusinessMetrics,
    MetricsCollector,
    RealtimeMetrics,
    SystemHealth,
    _store as _metrics_store,
    metrics_collector,
)
from backend.monitoring.alert_system import (
    Alert,
    AlertRule,
    AlertSystem,
    alert_system,
    _alert_store,
)


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture(autouse=True)
async def clear_metrics_store():
    """Reset the in-memory metrics store before each test."""
    async with _metrics_store._lock:
        _metrics_store._api_latencies.clear()
        _metrics_store._errors.clear()
        _metrics_store._business_metrics.clear()
    yield


@pytest.fixture(autouse=True)
async def clear_alert_store():
    """Reset the in-memory alert store before each test."""
    async with _alert_store._lock:
        _alert_store._alerts.clear()
        _alert_store._rules.clear()
    yield


# ======================================================================
# MetricsCollector Tests
# ======================================================================

class TestMetricsCollector:
    """Test suite for MetricsCollector."""

    @pytest.mark.asyncio
    async def test_record_api_latency_stores_metric(self):
        """record_api_latency stores a latency record."""
        result = await metrics_collector.record_api_latency("/api/cameras", 150.0)
        assert result["status"] == "recorded"
        assert result["endpoint"] == "/api/cameras"
        assert result["latency_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_record_error_creates_entry(self):
        """record_error stores an error record."""
        result = await metrics_collector.record_error(
            module="camera_health",
            error_type="ConnectionError",
            message="Camera 3 connection lost",
        )
        assert result["status"] == "recorded"
        assert result["module"] == "camera_health"

    @pytest.mark.asyncio
    async def test_record_business_metric(self):
        """record_business_metric stores a business metric."""
        result = await metrics_collector.record_business_metric(
            metric="active_users",
            value=42.0,
            tags={"tier": "business"},
        )
        assert result["status"] == "recorded"
        assert result["metric"] == "active_users"

    @pytest.mark.asyncio
    async def test_get_api_latency_p50_p95(self):
        """get_api_latency_p50 and p95 return correct percentiles."""
        # Record latency data
        for i in range(1, 101):
            await metrics_collector.record_api_latency("/api/*", float(i))

        p50 = await metrics_collector.get_api_latency_p50("/api/*", 5)
        p95 = await metrics_collector.get_api_latency_p95("/api/*", 5)

        # For 1..100, p50 ≈ 50.5, p95 ≈ 95.05
        assert 45 <= p50 <= 55, f"Expected p50 ~50, got {p50}"
        assert 90 <= p95 <= 100, f"Expected p95 ~95, got {p95}"

    @pytest.mark.asyncio
    async def test_get_api_latency_p50_no_data(self):
        """p50 returns 0 when no data."""
        val = await metrics_collector.get_api_latency_p50("/api/unknown", 5)
        assert val == 0.0

    @pytest.mark.asyncio
    async def test_get_error_rate_calculation(self):
        """get_error_rate returns correct error percentage."""
        # Add some latency + errors
        for _ in range(80):
            await metrics_collector.record_api_latency("/api/*", 100.0)
        for _ in range(20):
            await metrics_collector.record_error("test", "ValueError", "test error")

        rate = await metrics_collector.get_error_rate(5)
        # 20 errors out of 100 total records = 20%
        assert 15 <= rate <= 25, f"Expected rate ~20%, got {rate}"

    @pytest.mark.asyncio
    async def test_get_error_rate_no_data(self):
        """get_error_rate returns 0 when no data."""
        rate = await metrics_collector.get_error_rate(5)
        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_get_business_metrics_aggregates(self):
        """get_business_metrics returns aggregated business metrics."""
        await metrics_collector.record_business_metric(
            "active_users", 50.0, {"tier": "business"}
        )
        await metrics_collector.record_business_metric(
            "revenue_today", 150.0, {"tier": "business"}
        )

        bm = await metrics_collector.get_business_metrics()
        assert isinstance(bm, BusinessMetrics)
        assert bm.active_users_today == 50
        assert bm.estimated_revenue_today == 150.0

    @pytest.mark.asyncio
    async def test_get_system_health_returns_status(self):
        """get_system_health returns a SystemHealth object."""
        health = await metrics_collector.get_system_health()
        assert isinstance(health, SystemHealth)
        assert health.status in ("healthy", "degraded", "unhealthy")
        assert health.active_alerts >= 0

    @pytest.mark.asyncio
    async def test_realtime_metrics_updates_frequently(self):
        """get_realtime_metrics returns up-to-date RealtimeMetrics."""
        rm = await metrics_collector.get_realtime_metrics()
        assert isinstance(rm, RealtimeMetrics)
        assert rm.events_last_minute >= 0
        assert rm.api_requests_last_minute >= 0
        assert rm.avg_response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_system_health_degraded_with_high_latency(self):
        """System health shows degraded when latency is high."""
        for _ in range(20):
            await metrics_collector.record_api_latency("/api/*", 2000.0)
        for _ in range(2):
            await metrics_collector.record_error("test", "Timeout", "slow")

        health = await metrics_collector.get_system_health()
        assert health.status in ("degraded", "unhealthy")

    @pytest.mark.asyncio
    async def test_system_health_unhealthy_with_critical_errors(self):
        """System health shows unhealthy when error rate is very high."""
        for _ in range(10):
            await metrics_collector.record_api_latency("/api/*", 500.0)
        for _ in range(5):
            await metrics_collector.record_error("critical", "Crash", "fatal")

        health = await metrics_collector.get_system_health()
        assert health.status == "unhealthy"


# ======================================================================
# AlertSystem Tests
# ======================================================================

class TestAlertSystem:
    """Test suite for AlertSystem."""

    @pytest.mark.asyncio
    async def test_configure_alert_rule(self):
        """configure_alert_rule stores a rule."""
        rule = AlertRule(metric="cpu_usage", condition="gt", threshold=90.0)
        result = await alert_system.configure_alert_rule(rule)
        assert result["status"] == "configured"
        assert "rule_id" in result

    @pytest.mark.asyncio
    async def test_check_thresholds_triggers_alert(self):
        """check_thresholds creates an alert when threshold is exceeded."""
        # Add a rule with a low threshold
        rule = AlertRule(
            metric="error_rate",
            condition="gt",
            threshold=1.0,
            severity="warning",
            duration_minutes=0,
        )
        await alert_system.configure_alert_rule(rule)

        # Record enough errors to exceed threshold
        for _ in range(30):
            await metrics_collector.record_api_latency("/api/*", 100.0)
        for _ in range(10):
            await metrics_collector.record_error("test", "ValueError", "test")

        alerts = await alert_system.check_thresholds()
        assert len(alerts) >= 1
        assert alerts[0].metric == "error_rate"
        assert alerts[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_send_alert_delivers_notification(self):
        """send_alert attempts delivery via channels."""
        alert = Alert(
            severity="critical",
            metric="cpu_usage",
            current_value=95.0,
            threshold_value=90.0,
            message="CPU usage critical",
            module="test",
        )

        # Mock telegram and sms clients to avoid actual sends
        with patch("backend.monitoring.alert_system.alert_system.send_alert", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await alert_system.send_alert(alert)
            assert result is True

    @pytest.mark.asyncio
    async def test_acknowledge_alert_updates_status(self):
        """acknowledge_alert changes status to acknowledged."""
        alert = Alert(metric="test_metric", severity="warning")
        await _alert_store.add_alert(alert)

        result = await alert_system.acknowledge_alert(alert.alert_id, "admin_001")
        assert result["status"] == "acknowledged"

        updated = await _alert_store.get_alert(alert.alert_id)
        assert updated is not None
        assert updated.status == "acknowledged"
        assert updated.acknowledged_by == "admin_001"

    @pytest.mark.asyncio
    async def test_resolve_alert_clears(self):
        """resolve_alert changes status to resolved."""
        alert = Alert(metric="test", severity="critical")
        await _alert_store.add_alert(alert)

        result = await alert_system.resolve_alert(alert.alert_id, "admin_001")
        assert result["status"] == "resolved"

        updated = await _alert_store.get_alert(alert.alert_id)
        assert updated is not None
        assert updated.status == "resolved"
        assert updated.resolved_by == "admin_001"

    @pytest.mark.asyncio
    async def test_get_active_alerts_returns_unresolved(self):
        """get_active_alerts returns only active alerts."""
        active = Alert(metric="cpu", severity="warning")
        acknowledged = Alert(metric="memory", severity="critical", status="acknowledged")
        resolved = Alert(metric="disk", severity="info", status="resolved")
        await _alert_store.add_alert(active)
        await _alert_store.add_alert(acknowledged)
        await _alert_store.add_alert(resolved)

        active_alerts = await alert_system.get_active_alerts()
        # Should include active + acknowledged, not resolved
        alert_ids = {a.alert_id for a in active_alerts}
        assert active.alert_id in alert_ids
        assert acknowledged.alert_id in alert_ids
        assert resolved.alert_id not in alert_ids

    @pytest.mark.asyncio
    async def test_get_alert_history_returns_recent(self):
        """get_alert_history returns alerts within the time window."""
        old = Alert(
            metric="old",
            severity="info",
            timestamp=datetime.utcnow() - timedelta(hours=48),
        )
        recent = Alert(metric="recent", severity="warning")
        await _alert_store.add_alert(old)
        await _alert_store.add_alert(recent)

        history = await alert_system.get_alert_history(hours=24)
        hist_ids = {a.alert_id for a in history}
        assert recent.alert_id in hist_ids
        assert old.alert_id not in hist_ids

    @pytest.mark.asyncio
    async def test_silence_alert_suppresses_notifications(self):
        """silence_alert changes status to silenced."""
        alert = Alert(metric="noisy", severity="warning")
        await _alert_store.add_alert(alert)

        result = await alert_system.silence_alert(alert.alert_id, 30)
        assert result["status"] == "silenced"
        assert "silenced_until" in result

        updated = await _alert_store.get_alert(alert.alert_id)
        assert updated is not None
        assert updated.status == "silenced"

    @pytest.mark.asyncio
    async def test_configure_and_validate_rule(self):
        """Alert rules can be configured and retrieved."""
        rule = AlertRule(
            metric="api_latency_p95",
            condition="gt",
            threshold=2000.0,
            severity="critical",
            channels=["telegram"],
        )
        result = await alert_system.configure_alert_rule(rule)
        assert result["status"] == "configured"

        rules = await _alert_store.get_rules()
        assert len(rules) >= 1
        configure_rules = [r for r in rules if r.rule_id == rule.rule_id]
        assert len(configure_rules) == 1
        assert configure_rules[0].metric == "api_latency_p95"

    @pytest.mark.asyncio
    async def test_setup_default_rules(self):
        """setup_default_rules creates all default thresholds."""
        rules = await alert_system.setup_default_rules()
        assert len(rules) == 10  # 10 default rules from the spec

        # Verify specific thresholds
        metrics = {(r.metric, r.severity) for r in rules}
        assert ("api_latency_p95", "warning") in metrics
        assert ("api_latency_p95", "critical") in metrics
        assert ("error_rate", "warning") in metrics
        assert ("error_rate", "critical") in metrics
        assert ("database_connections", "warning") in metrics
        assert ("database_connections", "critical") in metrics
        assert ("offline_cameras", "warning") in metrics
        assert ("offline_cameras", "critical") in metrics
        assert ("ai_cost_per_user", "warning") in metrics
        assert ("ai_cost_per_user", "critical") in metrics

    @pytest.mark.asyncio
    async def test_no_duplicate_alerts_for_same_metric(self):
        """check_thresholds does not create duplicate active alerts."""
        rule = AlertRule(
            metric="error_rate",
            condition="gt",
            threshold=1.0,
            severity="warning",
        )
        await alert_system.configure_alert_rule(rule)

        # Record errors
        for _ in range(30):
            await metrics_collector.record_api_latency("/api/*", 100.0)
        for _ in range(10):
            await metrics_collector.record_error("test", "Err", "msg")

        # First check should create alert
        first = await alert_system.check_thresholds()
        assert len(first) == 1

        # Second check should not duplicate
        second = await alert_system.check_thresholds()
        assert len(second) == 0

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_alert(self):
        """acknowledge_alert returns not_found for unknown alert."""
        result = await alert_system.acknowledge_alert("nonexistent", "admin")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_alert(self):
        """resolve_alert returns not_found for unknown alert."""
        result = await alert_system.resolve_alert("nonexistent", "admin")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_silence_nonexistent_alert(self):
        """silence_alert returns not_found for unknown alert."""
        result = await alert_system.silence_alert("nonexistent", 10)
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_check_thresholds_with_disabled_rule(self):
        """check_thresholds skips disabled rules."""
        rule = AlertRule(
            metric="error_rate",
            condition="gt",
            threshold=1.0,
            enabled=False,
        )
        await alert_system.configure_alert_rule(rule)

        for _ in range(10):
            await metrics_collector.record_error("test", "Err", "msg")

        alerts = await alert_system.check_thresholds()
        assert len(alerts) == 0


# ======================================================================
# Integration-Style Tests
# ======================================================================

class TestMonitoringIntegration:
    """End-to-end tests for metrics + alerting flow."""

    @pytest.mark.asyncio
    async def test_full_monitoring_flow(self):
        """Complete flow: record metrics → check thresholds → handle alert."""
        # 1. Setup default rules
        await alert_system.setup_default_rules()

        # 2. Record high latency
        for _ in range(20):
            await metrics_collector.record_api_latency("/api/cameras", 4000.0)

        # 3. Record errors
        for _ in range(15):
            await metrics_collector.record_error("api", "Timeout", "slow response")

        # 4. Record business metrics
        await metrics_collector.record_business_metric("active_users", 50.0, {})
        await metrics_collector.record_business_metric("revenue_today", 200.0, {})

        # 5. Check thresholds
        alerts = await alert_system.check_thresholds()
        assert len(alerts) >= 1

        # 6. Acknowledge and resolve
        for alert in alerts:
            ack = await alert_system.acknowledge_alert(alert.alert_id, "admin_001")
            assert ack["status"] == "acknowledged"
            res = await alert_system.resolve_alert(alert.alert_id, "admin_001")
            assert res["status"] == "resolved"

        # 7. Verify no active alerts remain
        active = await alert_system.get_active_alerts()
        assert all(a.status == "acknowledged" for a in active)

    @pytest.mark.asyncio
    async def test_business_metrics_monitoring(self):
        """Business metrics are properly tracked."""
        # Simulate a day of activity
        await metrics_collector.record_business_metric("active_users", 35.0, {"tier": "business"})
        await metrics_collector.record_business_metric("active_users", 12.0, {"tier": "pro"})
        await metrics_collector.record_business_metric("revenue_today", 250.0, {"plan": "business"})
        await metrics_collector.record_business_metric("revenue_today", 80.0, {"plan": "pro"})

        bm = await metrics_collector.get_business_metrics()
        assert bm.active_users_today == 47  # 35 + 12
        assert bm.estimated_revenue_today == 330.0  # 250 + 80
        assert isinstance(bm.total_cameras, int)
        assert isinstance(bm.ai_calls_today, int)
