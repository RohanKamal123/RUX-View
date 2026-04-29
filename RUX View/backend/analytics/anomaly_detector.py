"""Statistical anomaly detection for security events.

Detects anomalous events compared to historical baselines using
z-score analysis with mean + 2*std deviation thresholds.
"""

from datetime import date, datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Statistical anomaly detection for security events.

    Detects anomalous event patterns by comparing current data against
    historical baselines. Uses z-score analysis with configurable thresholds.
    """

    def __init__(self, db_session_factory):
        """Initialize anomaly detector.

        Args:
            db_session_factory: SQLAlchemy async session factory
        """
        self.db_session_factory = db_session_factory

    async def detect_event_anomalies(self, camera_id: str,
                                      date: date) -> list[dict]:
        """Detect anomalous events compared to historical baseline.

        Uses: mean + 2*std deviation threshold

        Args:
            camera_id: Camera/location ID
            date: Date to check for anomalies

        Returns:
            List of dicts with hour, event_count, expected_range, anomaly_score
        """
        # Build baseline from historical data
        baseline = await self.build_baseline(camera_id, days=14)

        # Placeholder hourly counts for the target date
        hourly_counts = {
            0: 2, 1: 1, 2: 0, 3: 0, 4: 0, 5: 1,
            6: 3, 7: 5, 8: 12, 9: 15, 10: 18, 11: 20,
            12: 16, 13: 14, 14: 17, 15: 19, 16: 22, 17: 25,
            18: 20, 19: 15, 20: 10, 21: 8, 22: 5, 23: 3,
        }

        anomalies = []
        hourly_baseline = baseline.get("hourly", {})

        for hour in range(24):
            count = hourly_counts.get(hour, 0)
            hour_data = hourly_baseline.get(str(hour), {})

            if not hour_data or "mean" not in hour_data:
                continue

            mean = hour_data["mean"]
            std = hour_data["std"]

            is_anomaly = self._is_anomalous(count, mean, std)
            if is_anomaly:
                expected_min = max(0, mean - 2 * std)
                expected_max = mean + 2 * std
                z_score = self._calculate_z_score(count, mean, std)

                anomalies.append({
                    "hour": hour,
                    "event_count": count,
                    "expected_range": (round(expected_min, 1), round(expected_max, 1)),
                    "anomaly_score": round(z_score, 2),
                    "severity": "HIGH" if z_score > 3 else "MEDIUM",
                })

        return anomalies

    async def detect_hourly_anomaly(self, camera_id: str,
                                     hour: int,
                                     current_count: int,
                                     baseline_days: int = 14) -> dict:
        """Check if current hour's count is anomalous.

        Args:
            camera_id: Camera/location ID
            hour: Hour of day (0-23)
            current_count: Current event count for this hour
            baseline_days: Number of days for baseline calculation

        Returns:
            Dict with is_anomaly, expected_range, current_count, z_score, severity
        """
        baseline = await self.build_baseline(camera_id, days=baseline_days)
        hourly_baseline = baseline.get("hourly", {})
        hour_data = hourly_baseline.get(str(hour), {})

        if not hour_data or "mean" not in hour_data:
            return {
                "is_anomaly": False,
                "expected_range": (0, 0),
                "current_count": current_count,
                "z_score": 0.0,
                "severity": "UNKNOWN",
                "reason": "Insufficient baseline data",
            }

        mean = hour_data["mean"]
        std = hour_data["std"]
        is_anomaly = self._is_anomalous(current_count, mean, std)
        z_score = self._calculate_z_score(current_count, mean, std)

        expected_min = max(0, mean - 2 * std)
        expected_max = mean + 2 * std

        severity = "LOW"
        if is_anomaly:
            if z_score > 3:
                severity = "HIGH"
            elif z_score > 2.5:
                severity = "MEDIUM"

        return {
            "is_anomaly": is_anomaly,
            "expected_range": (round(expected_min, 1), round(expected_max, 1)),
            "current_count": current_count,
            "z_score": round(z_score, 2),
            "severity": severity,
            "mean": round(mean, 1),
            "std": round(std, 1),
        }

    async def build_baseline(self, camera_id: str,
                              days: int = 14) -> dict:
        """Build historical baseline for anomaly detection.

        Args:
            camera_id: Camera/location ID
            days: Number of days of historical data

        Returns:
            Dict with hourly, daily, weekly_pattern
        """
        # Placeholder baseline data - would query DB in production
        hourly_baseline = {}
        for hour in range(24):
            # Simulate typical daily pattern
            if 0 <= hour < 6:
                mean, std = 1.0, 0.5  # Night time - low activity
            elif 6 <= hour < 9:
                mean, std = 4.0, 1.5  # Morning ramp-up
            elif 9 <= hour < 12:
                mean, std = 15.0, 3.0  # Peak morning
            elif 12 <= hour < 14:
                mean, std = 12.0, 2.5  # Lunch dip
            elif 14 <= hour < 17:
                mean, std = 16.0, 3.5  # Afternoon peak
            elif 17 <= hour < 20:
                mean, std = 20.0, 4.0  # Evening peak
            elif 20 <= hour < 22:
                mean, std = 10.0, 2.0  # Evening wind-down
            else:
                mean, std = 4.0, 1.5  # Late evening

            hourly_baseline[str(hour)] = {
                "mean": mean,
                "std": std,
                "min": max(0, mean - 3 * std),
                "max": mean + 3 * std,
            }

        # Daily baseline
        daily_mean = sum(h["mean"] for h in hourly_baseline.values())
        daily_std = (sum(h["std"] ** 2 for h in hourly_baseline.values())) ** 0.5

        # Weekly pattern
        weekly_pattern = {
            "monday": {"mean": daily_mean * 0.9, "std": daily_std * 0.9},
            "tuesday": {"mean": daily_mean * 0.85, "std": daily_std * 0.85},
            "wednesday": {"mean": daily_mean * 0.85, "std": daily_std * 0.85},
            "thursday": {"mean": daily_mean * 0.9, "std": daily_std * 0.9},
            "friday": {"mean": daily_mean * 1.0, "std": daily_std * 1.0},
            "saturday": {"mean": daily_mean * 1.2, "std": daily_std * 1.2},
            "sunday": {"mean": daily_mean * 1.1, "std": daily_std * 1.1},
        }

        return {
            "hourly": hourly_baseline,
            "daily": {
                "mean": round(daily_mean, 1),
                "std": round(daily_std, 1),
                "min": round(max(0, daily_mean - 3 * daily_std), 1),
                "max": round(daily_mean + 3 * daily_std, 1),
            },
            "weekly_pattern": weekly_pattern,
            "baseline_days": days,
            "camera_id": camera_id,
        }

    def _calculate_z_score(self, value: float, mean: float,
                            std: float) -> float:
        """Calculate z-score for anomaly detection.

        Args:
            value: Observed value
            mean: Mean of the population
            std: Standard deviation of the population

        Returns:
            Z-score value
        """
        if std == 0:
            return 0.0
        return (value - mean) / std

    def _is_anomalous(self, value: float, mean: float,
                       std: float, threshold: float = 2.0) -> bool:
        """Check if value is anomalous (beyond threshold std deviations).

        Args:
            value: Observed value
            mean: Mean of the population
            std: Standard deviation of the population
            threshold: Number of std deviations for anomaly threshold

        Returns:
            True if value is anomalous
        """
        z_score = self._calculate_z_score(value, mean, std)
        return abs(z_score) > threshold
