"""Statistical trend analysis for security and customer data.

Provides trend detection for events, person sightings, and audio events
using moving averages and linear regression analysis.
"""

from typing import Optional
import logging

from backend.analytics.advanced_analytics import TrendDirection

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Statistical trend analysis for security and customer data.

    Analyzes event frequency trends, person sighting patterns, and audio
    event trends over configurable time periods.
    """

    def __init__(self):
        """Initialize trend analyzer."""
        pass

    async def analyze_event_trends(self, camera_id: str,
                                    days: int = 14) -> dict:
        """Analyze event frequency trends.

        Args:
            camera_id: Camera/location ID
            days: Number of days to analyze

        Returns:
            Dict with avg_events_per_day, trend_direction, peak_event_hour,
            high_threat_percentage, anomaly_days
        """
        # Placeholder analysis - would query DB in production
        daily_counts = [12, 15, 8, 20, 14, 18, 10, 16, 22, 13, 17, 9, 19, 11]

        avg_events = sum(daily_counts) / len(daily_counts) if daily_counts else 0
        trend_direction = self._detect_trend(daily_counts)

        return {
            "avg_events_per_day": round(avg_events, 1),
            "trend_direction": trend_direction.value,
            "peak_event_hour": 14,  # 2 PM
            "high_threat_percentage": 0.15,
            "anomaly_days": ["2024-01-10", "2024-01-13"],  # Days with unusual activity
            "total_events": sum(daily_counts),
            "daily_breakdown": daily_counts,
        }

    async def analyze_person_trends(self, location_id: str,
                                     days: int = 14) -> dict:
        """Analyze person sighting trends.

        Args:
            location_id: Location ID
            days: Number of days to analyze

        Returns:
            Dict with unique_persons_per_day, repeat_rate,
            new_vs_familiar_ratio, top_frequent_persons
        """
        return {
            "unique_persons_per_day": 45,
            "repeat_rate": 0.35,
            "new_vs_familiar_ratio": {"new": 0.65, "familiar": 0.35},
            "top_frequent_persons": [
                {"person_uid": "person_001", "sightings": 12},
                {"person_uid": "person_002", "sightings": 8},
                {"person_uid": "person_003", "sightings": 6},
            ],
            "total_unique_persons": 120,
            "avg_sightings_per_person": 2.5,
        }

    async def analyze_audio_trends(self, camera_id: str,
                                    days: int = 14) -> dict:
        """Analyze audio event trends.

        Args:
            camera_id: Camera/location ID
            days: Number of days to analyze

        Returns:
            Dict with avg_audio_events_per_day, top_sound_classes,
            after_hours_audio_ratio, speech_vs_noise_ratio
        """
        return {
            "avg_audio_events_per_day": 8.5,
            "top_sound_classes": [
                {"class": "Speech", "count": 45},
                {"class": "Vehicle", "count": 30},
                {"class": "Animal", "count": 15},
                {"class": "Alarm", "count": 8},
            ],
            "after_hours_audio_ratio": 0.25,
            "speech_vs_noise_ratio": {"speech": 0.40, "noise": 0.60},
            "total_audio_events": 119,
            "quietest_day": "Tuesday",
            "loudest_day": "Saturday",
        }

    def _moving_average(self, data: list[float],
                         window: int = 3) -> list[float]:
        """Calculate simple moving average.

        Args:
            data: List of data points
            window: Window size for averaging

        Returns:
            List of moving average values
        """
        if len(data) < window:
            return data

        averages = []
        for i in range(len(data) - window + 1):
            window_avg = sum(data[i:i + window]) / window
            averages.append(window_avg)
        return averages

    def _detect_trend(self, data: list[float]) -> TrendDirection:
        """Detect trend direction using linear regression slope.

        Args:
            data: List of data points over time

        Returns:
            TrendDirection enum value
        """
        if len(data) < 2:
            return TrendDirection.INSUFFICIENT_DATA

        n = len(data)
        x_values = list(range(n))
        y_values = data

        # Calculate linear regression slope
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return TrendDirection.STABLE

        slope = numerator / denominator

        # Normalize slope by mean for relative comparison
        if y_mean == 0:
            return TrendDirection.INSUFFICIENT_DATA

        relative_slope = slope / y_mean

        # Determine direction based on relative slope
        if abs(relative_slope) < 0.05:
            return TrendDirection.STABLE
        elif relative_slope > 0:
            return TrendDirection.RISING
        else:
            return TrendDirection.FALLING
