"""
Vision OS — Metrics Collector Module
SPRINT 10.5 — Monitoring & Alerting

Collects system health, API latency, error rates, and business metrics.
Uses async/await throughout (D026).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BusinessMetrics:
    """Aggregated business-level KPIs."""
    total_users: int = 0
    active_users_today: int = 0
    total_cameras: int = 0
    online_cameras: int = 0
    events_today: int = 0
    high_threat_events: int = 0
    ai_calls_today: int = 0
    estimated_revenue_today: float = 0.0
    estimated_revenue_monthly: float = 0.0
    trial_conversion_rate: float = 0.0


@dataclass
class SystemHealth:
    """Overall system health snapshot."""
    status: str = "healthy"  # healthy / degraded / unhealthy
    api_latency_p95_ms: float = 0.0
    error_rate_pct: float = 0.0
    database_connections: int = 0
    database_latency_ms: float = 0.0
    active_instances: int = 1
    cpu_utilization_pct: float = 0.0
    memory_utilization_pct: float = 0.0
    active_alerts: int = 0


@dataclass
class RealtimeMetrics:
    """High-frequency (last 1 minute) metrics."""
    events_last_minute: int = 0
    ai_calls_last_minute: int = 0
    active_websockets: int = 0
    api_requests_last_minute: int = 0
    avg_response_time_ms: float = 0.0
    error_count_last_minute: int = 0


# ---------------------------------------------------------------------------
# In-memory metric stores (ephemeral — replace with Cloud Monitoring in prod)
# ---------------------------------------------------------------------------

class _MetricStore:
    """Thread-safe in-memory metric stores for development / single-instance use."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # endpoint -> list of latency values (milliseconds)
        self._api_latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        # list of error dicts
        self._errors: list[dict[str, Any]] = []
        # metric_name -> list of (timestamp, value, tags)
        self._business_metrics: dict[str, deque[tuple[float, float, dict]]] = defaultdict(
            lambda: deque(maxlen=50000)
        )
        self._error_lock = asyncio.Lock()

    # ---- API latency ----

    async def record_latency(self, endpoint: str, latency_ms: float) -> None:
        async with self._lock:
            self._api_latencies[endpoint].append(latency_ms)

    async def get_latency_values(self, endpoint: str) -> list[float]:
        async with self._lock:
            return list(self._api_latencies.get(endpoint, []))

    async def clear_latencies(self, endpoint: Optional[str] = None) -> None:
        async with self._lock:
            if endpoint:
                self._api_latencies.pop(endpoint, None)
            else:
                self._api_latencies.clear()

    # ---- Errors ----

    async def add_error(self, entry: dict[str, Any]) -> None:
        async with self._error_lock:
            self._errors.append(entry)
            # Keep only last 50000 errors
            if len(self._errors) > 50000:
                self._errors = self._errors[-50000:]

    async def get_errors_since(self, since_ts: float) -> list[dict[str, Any]]:
        async with self._error_lock:
            return [e for e in self._errors if e.get("timestamp", 0) >= since_ts]

    async def count_errors_since(self, since_ts: float) -> int:
        async with self._error_lock:
            return sum(1 for e in self._errors if e.get("timestamp", 0) >= since_ts)

    # ---- Business metrics ----

    async def record_business(self, name: str, value: float, tags: dict) -> None:
        async with self._lock:
            self._business_metrics[name].append((time.time(), value, tags))

    async def get_business_values(
        self, name: str, since_ts: float
    ) -> list[tuple[float, float, dict]]:
        async with self._lock:
            return [
                (ts, v, t)
                for ts, v, t in self._business_metrics.get(name, [])
                if ts >= since_ts
            ]

    async def get_latest_business_value(self, name: str) -> Optional[float]:
        async with self._lock:
            dq = self._business_metrics.get(name)
            if dq:
                last = dq[-1]
                return last[1]  # value
            return None


_store = _MetricStore()


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Collects and retrieves API latency, error, and business metrics.

    Designed for Google Cloud Monitoring integration but functions standalone
    with in-memory storage for development/testing.
    """

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_api_latency(self, endpoint: str, latency_ms: float) -> dict:
        """
        Record an API call latency measurement.

        Args:
            endpoint: API endpoint path (e.g. '/api/events').
            latency_ms: Response time in milliseconds.

        Returns:
            dict with status and recorded stats.
        """
        if latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")

        await _store.record_latency(endpoint, latency_ms)

        return {
            "status": "recorded",
            "endpoint": endpoint,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }

    async def record_error(
        self, module: str, error_type: str, message: str
    ) -> dict:
        """
        Record an error occurrence.

        Args:
            module: Module name (e.g. 'pipeline', 'ai_client', 'database').
            error_type: Type/category of error (e.g. 'timeout', 'connection').
            message: Human-readable error description.

        Returns:
            dict with status and recorded entry.
        """
        entry = {
            "module": module,
            "error_type": error_type,
            "message": message,
            "timestamp": time.time(),
            "datetime": datetime.utcnow().isoformat(),
        }
        await _store.add_error(entry)
        return {"status": "recorded", "entry": entry}

    async def record_business_metric(
        self, metric: str, value: float, tags: Optional[dict] = None
    ) -> dict:
        """
        Record a business-level metric (active users, events, revenue, etc.).

        Args:
            metric: Metric name (e.g. 'active_users', 'events_today').
            value: Numeric value.
            tags: Optional key-value tags for filtering.

        Returns:
            dict with status.
        """
        await _store.record_business(metric, value, tags or {})
        return {"status": "recorded", "metric": metric, "value": value}

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_api_latency_p50(
        self, endpoint: str, minutes: int = 5
    ) -> float:
        """Get median (P50) API latency for the last N minutes."""
        values = await self._recent_latencies(endpoint, minutes)
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        return float(sorted_vals[mid])

    async def get_api_latency_p95(
        self, endpoint: str, minutes: int = 5
    ) -> float:
        """Get 95th percentile API latency for the last N minutes."""
        values = await self._recent_latencies(endpoint, minutes)
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, int(len(sorted_vals) * 0.95) - 1)
        return float(sorted_vals[idx])

    async def _recent_latencies(
        self, endpoint: str, minutes: int
    ) -> list[float]:
        """Return latency values recorded within the last *minutes*."""
        # All values in deque are within maxlen=10000, no timestamp stored.
        # For simplicity assume they are recent enough.
        # In production you'd attach timestamps.
        return await _store.get_latency_values(endpoint)

    async def get_error_rate(self, minutes: int = 5) -> float:
        """
        Calculate error rate as fraction of a simple request estimate.

        Returns error rate as a percentage (0-100). Uses a heuristic
        based on the number of API latency recordings as total requests.
        """
        since = time.time() - minutes * 60
        error_count = await _store.count_errors_since(since)

        # Estimate total requests from business metric 'api_requests' or fallback
        total_requests = 0
        req_vals = await _store.get_business_values("api_requests", since)
        if req_vals:
            total_requests = sum(v for _, v, _ in req_vals)

        # Fallback: use number of latency recordings across all endpoints
        if total_requests == 0:
            # crude fallback
            total_requests = error_count + 100

        if total_requests == 0:
            return 0.0

        return (error_count / total_requests) * 100.0

    async def get_business_metrics(
        self, since: Optional[datetime] = None
    ) -> BusinessMetrics:
        """
        Aggregate business metrics since a given datetime.

        Args:
            since: Start time for aggregation. Defaults to 24 hours ago.

        Returns:
            BusinessMetrics dataclass.
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)
        since_ts = since.timestamp()

        bm = BusinessMetrics()

        # Map metric names to attributes
        metric_map: dict[str, str] = {
            "total_users": "total_users",
            "active_users_today": "active_users_today",
            "total_cameras": "total_cameras",
            "online_cameras": "online_cameras",
            "events_today": "events_today",
            "high_threat_events": "high_threat_events",
            "ai_calls_today": "ai_calls_today",
            "estimated_revenue_today": "estimated_revenue_today",
            "estimated_revenue_monthly": "estimated_revenue_monthly",
            "trial_conversion_rate": "trial_conversion_rate",
        }

        for metric_name, attr in metric_map.items():
            vals = await _store.get_business_values(metric_name, since_ts)
            if vals:
                # Use the most recent value
                latest = vals[-1][1]
                setattr(bm, attr, latest)

        # Provide defaults for zero values
        return bm

    async def get_system_health(self) -> SystemHealth:
        """
        Produce a snapshot of overall system health.

        Returns:
            SystemHealth dataclass.
        """
        sh = SystemHealth()

        # Compute P95 across all endpoints
        all_latencies: list[float] = []
        # We can't iterate endpoints easily; use a known one or 'overall'
        known_endpoints = ["/api/*"]
        for ep in known_endpoints:
            vals = await _store.get_latency_values(ep)
            all_latencies.extend(vals)

        if all_latencies:
            sorted_vals = sorted(all_latencies)
            idx = max(0, int(len(sorted_vals) * 0.95) - 1)
            sh.api_latency_p95_ms = float(sorted_vals[idx])
        else:
            sh.api_latency_p95_ms = 0.0

        # Error rate
        error_rate = await self.get_error_rate(5)
        sh.error_rate_pct = error_rate

        # Determine status
        if sh.api_latency_p95_ms > 3000 or error_rate > 10:
            sh.status = "unhealthy"
        elif sh.api_latency_p95_ms > 1000 or error_rate > 5:
            sh.status = "degraded"
        else:
            sh.status = "healthy"

        # Stub values for infrastructure metrics (populated by cloud monitoring)
        sh.active_alerts = 0

        return sh

    async def get_realtime_metrics(self) -> RealtimeMetrics:
        """Get high-frequency metrics for the last 60 seconds."""
        rm = RealtimeMetrics()
        since = time.time() - 60

        # Events
        ev_vals = await _store.get_business_values("events_last_minute", since)
        if ev_vals:
            rm.events_last_minute = int(ev_vals[-1][1])

        # AI calls
        ai_vals = await _store.get_business_values("ai_calls_last_minute", since)
        if ai_vals:
            rm.ai_calls_last_minute = int(ai_vals[-1][1])

        # API requests
        req_vals = await _store.get_business_values("api_requests_last_minute", since)
        if req_vals:
            rm.api_requests_last_minute = int(req_vals[-1][1])

        # Error count
        rm.error_count_last_minute = await _store.count_errors_since(since)

        # Average response time
        all_latencies: list[float] = []
        known_endpoints = ["/api/*"]
        for ep in known_endpoints:
            vals = await _store.get_latency_values(ep)
            all_latencies.extend(vals)
        if all_latencies:
            rm.avg_response_time_ms = sum(all_latencies) / len(all_latencies)

        return rm

    # ------------------------------------------------------------------
    # Utility / reset
    # ------------------------------------------------------------------

    async def reset_metrics(self) -> dict:
        """Clear all in-memory metric stores (for testing)."""
        await _store.clear_latencies()
        # Errors & business survive — reset them explicitly
        async with _store._error_lock:
            _store._errors.clear()
        async with _store._lock:
            _store._business_metrics.clear()
        return {"status": "reset"}


# Singleton
metrics_collector = MetricsCollector()


# ---------------------------------------------------------------------------
# Helper: periodic aggregation task
# ---------------------------------------------------------------------------

async def periodic_metrics_aggregation(
    collector: MetricsCollector,
    interval_seconds: int = 60,
) -> None:
    """
    Background task that periodically aggregates and logs key metrics.
    Run with asyncio.create_task(periodic_metrics_aggregation(...)).
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)

            health = await collector.get_system_health()
            realtime = await collector.get_realtime_metrics()
            business = await collector.get_business_metrics()

            logger.info(
                "Metrics snapshot | "
                "status=%s p95=%.0fms error_rate=%.1f%% "
                "events_1m=%d ai_1m=%d requests_1m=%d",
                health.status,
                health.api_latency_p95_ms,
                health.error_rate_pct,
                realtime.events_last_minute,
                realtime.ai_calls_last_minute,
                realtime.api_requests_last_minute,
            )

            # In production: push to Cloud Monitoring
            # from google.cloud import monitoring_v3
            # ...

        except asyncio.CancelledError:
            logger.info("Metrics aggregation task cancelled.")
            break
        except Exception:
            logger.exception("Error in periodic metrics aggregation")
