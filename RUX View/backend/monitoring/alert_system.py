"""
Vision OS — Alert System Module
SPRINT 10.5 — Monitoring & Alerting

Threshold checking, alert lifecycle management, and notification dispatch.
Uses async/await throughout (D026).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """Represents a single alert instance."""
    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    severity: str = "info"  # info / warning / critical / emergency
    metric: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    message: str = ""
    module: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"  # active / acknowledged / resolved / silenced
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None


@dataclass
class AlertRule:
    """Configuration for a single alert rule."""
    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    metric: str = ""
    condition: str = "gt"  # gt / lt / gte / lte / eq
    threshold: float = 0.0
    severity: str = "warning"
    duration_minutes: int = 5  # sustained for X minutes before alert
    enabled: bool = True
    channels: list[str] = field(default_factory=lambda: ["telegram", "email"])


# ---------------------------------------------------------------------------
# In-memory alert store
# ---------------------------------------------------------------------------

class _AlertStore:
    """Thread-safe in-memory alert storage."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._alerts: list[Alert] = []
        self._rules: list[AlertRule] = []

    # ---- Alerts ----

    async def add_alert(self, alert: Alert) -> None:
        async with self._lock:
            self._alerts.append(alert)

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        async with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    return a
            return None

    async def update_alert(self, alert_id: str, **updates) -> Optional[Alert]:
        async with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    for k, v in updates.items():
                        setattr(a, k, v)
                    return a
            return None

    async def get_active_alerts(self) -> list[Alert]:
        async with self._lock:
            return [a for a in self._alerts if a.status == "active"]

    async def get_alerts_since(self, since_ts: float) -> list[Alert]:
        async with self._lock:
            return [
                a for a in self._alerts
                if a.timestamp.timestamp() >= since_ts
            ]

    # ---- Rules ----

    async def add_rule(self, rule: AlertRule) -> None:
        async with self._lock:
            self._rules.append(rule)

    async def get_rules(self) -> list[AlertRule]:
        async with self._lock:
            return list(self._rules)

    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        async with self._lock:
            for r in self._rules:
                if r.rule_id == rule_id:
                    return r
            return None


_alert_store = _AlertStore()


# ---------------------------------------------------------------------------
# AlertSystem
# ---------------------------------------------------------------------------

class AlertSystem:
    """
    Manages alert rules, evaluates thresholds, and handles alert lifecycle.

    Notification delivery (Telegram, Email) is delegated to existing
    modules (telegram_client, sms_client).
    """

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def configure_alert_rule(self, rule: AlertRule) -> dict:
        """
        Add or update an alert rule.

        Args:
            rule: AlertRule dataclass with threshold configuration.

        Returns:
            dict with status and rule_id.
        """
        # If rule_id is provided and exists, update it
        existing = await _alert_store.get_rule(rule.rule_id)
        if existing:
            # Replace
            await _alert_store.add_rule(rule)
        else:
            await _alert_store.add_rule(rule)

        logger.info("Alert rule configured: %s (%s %s %.2f)",
                     rule.rule_id, rule.metric, rule.condition, rule.threshold)
        return {"status": "configured", "rule_id": rule.rule_id}

    # ------------------------------------------------------------------
    # Threshold checking
    # ------------------------------------------------------------------

    async def check_thresholds(self) -> list[Alert]:
        """
        Evaluate all enabled alert rules. For simplicity this checks
        instant values; production should evaluate sustained conditions.

        Returns:
            List of newly created Alert objects.
        """
        rules = await _alert_store.get_rules()
        new_alerts: list[Alert] = []

        for rule in rules:
            if not rule.enabled:
                continue

            current_value = await self._get_current_metric_value(rule.metric)
            if current_value is None:
                continue

            triggered = self._evaluate_condition(
                current_value, rule.condition, rule.threshold
            )
            if not triggered:
                continue

            # Check if already active for this metric/severity to avoid duplicates
            existing_active = await _alert_store.get_active_alerts()
            already_active = any(
                a.metric == rule.metric and a.severity == rule.severity
                for a in existing_active
            )
            if already_active:
                continue

            alert = Alert(
                severity=rule.severity,
                metric=rule.metric,
                current_value=current_value,
                threshold_value=rule.threshold,
                message=(
                    f"Alert: {rule.metric} = {current_value:.1f} "
                    f"({rule.condition} {rule.threshold:.1f}) "
                    f"on rule {rule.rule_id}"
                ),
                module="alert_system",
                timestamp=datetime.utcnow(),
                status="active",
            )
            await _alert_store.add_alert(alert)
            new_alerts.append(alert)

            logger.warning("Alert triggered: [%s] %s = %.2f (threshold %.2f)",
                           rule.severity, rule.metric, current_value, rule.threshold)

        return new_alerts

    async def _get_current_metric_value(self, metric: str) -> Optional[float]:
        """
        Retrieve the current value for a given metric name.
        Integrates with MetricsCollector.
        """
        from backend.monitoring.metrics_collector import metrics_collector

        # Map metric names to collector methods
        metric_map: dict[str, str] = {
            "api_latency_p95": "api_latency_p95",
            "error_rate": "error_rate",
            "database_connections": "database_connections",
            "online_cameras": "online_cameras",
            "events_today": "events_today",
            "offline_cameras": "offline_cameras",
            "ai_cost_per_user": "ai_cost_per_user",
        }

        if metric in ("api_latency_p95", "api_latency", "latency_p95"):
            return await metrics_collector.get_api_latency_p95("/api/*", 5)

        if metric in ("error_rate", "error_rate_pct"):
            return await metrics_collector.get_error_rate(5)

        if metric == "database_connections":
            # Stub — in production query Cloud SQL metrics
            return 3.0

        if metric == "online_cameras":
            bm = await metrics_collector.get_business_metrics()
            return float(bm.online_cameras)

        if metric == "events_today":
            bm = await metrics_collector.get_business_metrics()
            return float(bm.events_today)

        if metric == "offline_cameras":
            bm = await metrics_collector.get_business_metrics()
            return float(max(0, bm.total_cameras - bm.online_cameras))

        if metric == "ai_cost_per_user":
            bm = await metrics_collector.get_business_metrics()
            if bm.active_users_today > 0:
                return bm.estimated_revenue_today / bm.active_users_today
            return 0.0

        # Unknown metric
        return None

    def _evaluate_condition(
        self, current: float, condition: str, threshold: float
    ) -> bool:
        """Evaluate a single threshold condition."""
        if condition == "gt":
            return current > threshold
        elif condition == "lt":
            return current < threshold
        elif condition == "gte":
            return current >= threshold
        elif condition == "lte":
            return current <= threshold
        elif condition == "eq":
            return abs(current - threshold) < 1e-9
        return False

    # ------------------------------------------------------------------
    # Alert lifecycle
    # ------------------------------------------------------------------

    async def send_alert(self, alert: Alert) -> bool:
        """
        Deliver an alert to configured channels (Telegram, Email).

        Args:
            alert: The alert to send.

        Returns:
            True if at least one channel delivered successfully.
        """
        delivered = False

        # Determine channels from matching rule
        rules = await _alert_store.get_rules()
        channels: list[str] = ["telegram", "email"]  # default
        for rule in rules:
            if rule.metric == alert.metric:
                channels = rule.channels
                break

        for channel in channels:
            try:
                if channel == "telegram":
                    from backend.alerts.telegram_client import telegram_client
                    await telegram_client.send_message(
                        f"[{alert.severity.upper()}] {alert.message}"
                    )
                    delivered = True
                elif channel == "email":
                    from backend.alerts.sms_client import sms_client
                    await sms_client.send_email(
                        subject=f"[Vision OS] {alert.severity.upper()} Alert",
                        body=alert.message,
                    )
                    delivered = True
            except Exception:
                logger.exception("Failed to send alert via %s", channel)

        return delivered

    async def acknowledge_alert(
        self, alert_id: str, admin_id: str
    ) -> dict:
        """
        Acknowledge an active alert.

        Args:
            alert_id: ID of the alert.
            admin_id: Admin/user identifier.

        Returns:
            dict with status.
        """
        updated = await _alert_store.update_alert(
            alert_id,
            status="acknowledged",
            acknowledged_by=admin_id,
        )
        if updated is None:
            return {"status": "not_found", "alert_id": alert_id}
        logger.info("Alert %s acknowledged by %s", alert_id, admin_id)
        return {"status": "acknowledged", "alert_id": alert_id}

    async def resolve_alert(self, alert_id: str, admin_id: str) -> dict:
        """
        Resolve an acknowledged/active alert.

        Args:
            alert_id: ID of the alert.
            admin_id: Admin/user identifier.

        Returns:
            dict with status.
        """
        updated = await _alert_store.update_alert(
            alert_id,
            status="resolved",
            resolved_by=admin_id,
        )
        if updated is None:
            return {"status": "not_found", "alert_id": alert_id}
        logger.info("Alert %s resolved by %s", alert_id, admin_id)
        return {"status": "resolved", "alert_id": alert_id}

    async def get_active_alerts(self) -> list[Alert]:
        """Get all unresolved alerts (active + acknowledged)."""
        alerts = await _alert_store.get_active_alerts()
        # Also include acknowledged
        async with _alert_store._lock:
            acknowledged = [a for a in _alert_store._alerts if a.status == "acknowledged"]
        return alerts + acknowledged

    async def get_alert_history(
        self, hours: int = 24
    ) -> list[Alert]:
        """Get alerts from the last N hours."""
        since_ts = time.time() - hours * 3600
        return await _alert_store.get_alerts_since(since_ts)

    async def silence_alert(
        self, alert_id: str, duration_minutes: int
    ) -> dict:
        """
        Silence an alert for a given duration (no notifications).

        Args:
            alert_id: ID of the alert.
            duration_minutes: Minutes to silence.

        Returns:
            dict with status and silenced_until.
        """
        silenced_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        updated = await _alert_store.update_alert(
            alert_id,
            status="silenced",
        )
        if updated is None:
            return {"status": "not_found", "alert_id": alert_id}

        # Schedule auto-reactivate
        async def _unsilence():
            await asyncio.sleep(duration_minutes * 60)
            await _alert_store.update_alert(alert_id, status="active")

        asyncio.create_task(_unsilence())

        logger.info("Alert %s silenced for %d minutes", alert_id, duration_minutes)
        return {
            "status": "silenced",
            "alert_id": alert_id,
            "silenced_until": silenced_until.isoformat(),
        }

    # ------------------------------------------------------------------
    # Default rules setup
    # ------------------------------------------------------------------

    async def setup_default_rules(self) -> list[AlertRule]:
        """
        Create the default alert thresholds from the spec.

        Returns:
            List of created AlertRule objects.
        """
        default_rules = [
            AlertRule(
                metric="api_latency_p95",
                condition="gt",
                threshold=1000.0,
                severity="warning",
                duration_minutes=5,
                channels=["telegram"],
            ),
            AlertRule(
                metric="api_latency_p95",
                condition="gt",
                threshold=3000.0,
                severity="critical",
                duration_minutes=2,
                channels=["telegram", "email"],
            ),
            AlertRule(
                metric="error_rate",
                condition="gt",
                threshold=5.0,
                severity="warning",
                duration_minutes=5,
                channels=["telegram"],
            ),
            AlertRule(
                metric="error_rate",
                condition="gt",
                threshold=10.0,
                severity="critical",
                duration_minutes=2,
                channels=["telegram", "email"],
            ),
            AlertRule(
                metric="database_connections",
                condition="gt",
                threshold=80.0,
                severity="warning",
                duration_minutes=5,
                channels=["telegram"],
            ),
            AlertRule(
                metric="database_connections",
                condition="gt",
                threshold=95.0,
                severity="critical",
                duration_minutes=2,
                channels=["telegram", "email"],
            ),
            AlertRule(
                metric="offline_cameras",
                condition="gt",
                threshold=3.0,
                severity="warning",
                duration_minutes=10,
                channels=["telegram"],
            ),
            AlertRule(
                metric="offline_cameras",
                condition="gt",
                threshold=5.0,
                severity="critical",
                duration_minutes=5,
                channels=["telegram", "email"],
            ),
            AlertRule(
                metric="ai_cost_per_user",
                condition="gt",
                threshold=10.0,
                severity="warning",
                duration_minutes=60,
                channels=["telegram"],
            ),
            AlertRule(
                metric="ai_cost_per_user",
                condition="gt",
                threshold=25.0,
                severity="critical",
                duration_minutes=30,
                channels=["telegram", "email"],
            ),
        ]

        for rule in default_rules:
            await _alert_store.add_rule(rule)

        logger.info("Default alert rules setup complete (%d rules)", len(default_rules))
        return default_rules


# Singleton
alert_system = AlertSystem()
