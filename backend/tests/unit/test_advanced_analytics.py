"""Tests for advanced analytics modules: advanced_analytics, trend_analyzer, anomaly_detector."""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from backend.analytics.advanced_analytics import (
    AdvancedAnalytics,
    TrendAnalysis,
    TrendDirection,
    WeeklyReport,
    MonthlyReport,
)
from backend.analytics.trend_analyzer import TrendAnalyzer
from backend.analytics.anomaly_detector import AnomalyDetector


@pytest.fixture
def advanced_analytics():
    mock_session_factory = MagicMock()
    return AdvancedAnalytics(db_session_factory=mock_session_factory)


@pytest.fixture
def trend_analyzer():
    return TrendAnalyzer()


@pytest.fixture
def anomaly_detector():
    mock_session_factory = MagicMock()
    return AnomalyDetector(db_session_factory=mock_session_factory)


class TestAdvancedAnalytics:
    """Tests for AdvancedAnalytics class."""

    @pytest.mark.asyncio
    async def test_weekly_report_generates_all_sections(self, advanced_analytics):
        """Test that weekly report contains all required sections."""
        report = await advanced_analytics.get_weekly_report(
            camera_id="cam_123",
            week_start=date(2024, 1, 1),
        )
        assert isinstance(report, WeeklyReport)
        assert report.location_id == "cam_123"
        assert report.total_customers > 0
        assert report.avg_daily_customers > 0
        assert report.busiest_day is not None
        assert report.peak_hour is not None
        assert report.trends is not None
        assert len(report.predictions) > 0
        assert len(report.recommendations) > 0

    @pytest.mark.asyncio
    async def test_monthly_report_includes_trends(self, advanced_analytics):
        """Test that monthly report includes trend analysis."""
        report = await advanced_analytics.get_monthly_report(
            camera_id="cam_123",
            month=1,
            year=2024,
        )
        assert isinstance(report, MonthlyReport)
        assert report.month == 1
        assert report.year == 2024
        assert report.week_over_week_change != 0
        assert report.customer_retention_rate > 0
        assert len(report.trends) > 0

    @pytest.mark.asyncio
    async def test_customer_trend_detection_rising(self, advanced_analytics):
        """Test that rising trend is detected correctly."""
        current = [100, 110, 120, 130, 140]
        previous = [80, 85, 90, 95, 100]
        trend = advanced_analytics._calculate_trend(current, previous, "customer_count")
        assert trend.direction == TrendDirection.RISING
        assert trend.percentage_change > 0

    @pytest.mark.asyncio
    async def test_customer_trend_detection_falling(self, advanced_analytics):
        """Test that falling trend is detected correctly."""
        current = [100, 95, 90, 85, 80]
        previous = [120, 115, 110, 105, 100]
        trend = advanced_analytics._calculate_trend(current, previous, "customer_count")
        assert trend.direction == TrendDirection.FALLING
        assert trend.percentage_change < 0

    @pytest.mark.asyncio
    async def test_peak_hour_prediction_returns_reasonable_hour(self, advanced_analytics):
        """Test that peak hour prediction returns a valid hour."""
        prediction = await advanced_analytics.get_peak_hour_prediction(
            camera_id="cam_123",
            forecast_date=date(2024, 1, 15),
        )
        assert 0 <= prediction["predicted_peak_hour"] <= 23
        assert 0 <= prediction["confidence"] <= 1.0
        assert "reasoning" in prediction

    @pytest.mark.asyncio
    async def test_customer_retention_calculation(self, advanced_analytics):
        """Test that customer retention is calculated correctly."""
        retention = await advanced_analytics.get_customer_retention(
            camera_id="cam_123",
            days=30,
        )
        assert "retention_rate" in retention
        assert "repeat_customers" in retention
        assert "total_customers" in retention
        assert "avg_visits_per_customer" in retention
        assert 0 <= retention["retention_rate"] <= 1.0

    def test_trend_analysis_dataclass(self):
        """Test TrendAnalysis dataclass creation."""
        trend = TrendAnalysis(
            metric="customer_count",
            direction=TrendDirection.RISING,
            percentage_change=15.5,
            current_value=115.0,
            previous_value=100.0,
            confidence=0.85,
            insight="Customer count rising by 15.5%",
        )
        assert trend.metric == "customer_count"
        assert trend.direction == TrendDirection.RISING
        assert trend.percentage_change == 15.5

    def test_weekly_report_dataclass(self):
        """Test WeeklyReport dataclass creation."""
        report = WeeklyReport(
            location_id="loc_1",
            week_start=date(2024, 1, 1),
            week_end=date(2024, 1, 7),
        )
        assert report.location_id == "loc_1"
        assert report.total_customers == 0  # Default value


class TestTrendAnalyzer:
    """Tests for TrendAnalyzer class."""

    @pytest.mark.asyncio
    async def test_event_trend_analysis(self, trend_analyzer):
        """Test event trend analysis returns expected structure."""
        result = await trend_analyzer.analyze_event_trends(
            camera_id="cam_123",
            days=14,
        )
        assert "avg_events_per_day" in result
        assert "trend_direction" in result
        assert "peak_event_hour" in result
        assert "high_threat_percentage" in result
        assert "anomaly_days" in result

    @pytest.mark.asyncio
    async def test_person_trend_analysis(self, trend_analyzer):
        """Test person trend analysis returns expected structure."""
        result = await trend_analyzer.analyze_person_trends(
            location_id="loc_123",
            days=14,
        )
        assert "unique_persons_per_day" in result
        assert "repeat_rate" in result
        assert "new_vs_familiar_ratio" in result
        assert "top_frequent_persons" in result

    @pytest.mark.asyncio
    async def test_audio_trend_analysis(self, trend_analyzer):
        """Test audio trend analysis returns expected structure."""
        result = await trend_analyzer.analyze_audio_trends(
            camera_id="cam_123",
            days=14,
        )
        assert "avg_audio_events_per_day" in result
        assert "top_sound_classes" in result
        assert "after_hours_audio_ratio" in result
        assert "speech_vs_noise_ratio" in result

    def test_moving_average(self, trend_analyzer):
        """Test moving average calculation."""
        data = [1, 2, 3, 4, 5]
        result = trend_analyzer._moving_average(data, window=3)
        assert len(result) == 3  # 5 - 3 + 1 = 3
        assert result[0] == 2.0  # (1+2+3)/3
        assert result[1] == 3.0  # (2+3+4)/3
        assert result[2] == 4.0  # (3+4+5)/3

    def test_trend_detection_rising(self, trend_analyzer):
        """Test rising trend detection."""
        data = [10, 20, 30, 40, 50]
        direction = trend_analyzer._detect_trend(data)
        assert direction == TrendDirection.RISING

    def test_trend_detection_falling(self, trend_analyzer):
        """Test falling trend detection."""
        data = [50, 40, 30, 20, 10]
        direction = trend_analyzer._detect_trend(data)
        assert direction == TrendDirection.FALLING

    def test_trend_detection_stable(self, trend_analyzer):
        """Test stable trend detection."""
        data = [30, 31, 29, 30, 31]
        direction = trend_analyzer._detect_trend(data)
        assert direction == TrendDirection.STABLE


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""

    @pytest.mark.asyncio
    async def test_event_anomaly_detection_above_threshold(self, anomaly_detector):
        """Test that anomalies above threshold are detected."""
        anomalies = await anomaly_detector.detect_event_anomalies(
            camera_id="cam_123",
            date=date(2024, 1, 15),
        )
        assert isinstance(anomalies, list)
        # Some hours should be anomalous
        if anomalies:
            assert "hour" in anomalies[0]
            assert "event_count" in anomalies[0]
            assert "anomaly_score" in anomalies[0]

    @pytest.mark.asyncio
    async def test_event_anomaly_no_detection_within_normal(self, anomaly_detector):
        """Test that normal values are not flagged as anomalous."""
        result = await anomaly_detector.detect_hourly_anomaly(
            camera_id="cam_123",
            hour=10,
            current_count=15,  # Within expected range for 10am
            baseline_days=14,
        )
        # 15 events at 10am should be within normal range (mean=15, std=3)
        assert result["is_anomaly"] is False

    @pytest.mark.asyncio
    async def test_baseline_builds_hourly_pattern(self, anomaly_detector):
        """Test that baseline builds hourly patterns."""
        baseline = await anomaly_detector.build_baseline(
            camera_id="cam_123",
            days=14,
        )
        assert "hourly" in baseline
        assert "daily" in baseline
        assert "weekly_pattern" in baseline
        assert len(baseline["hourly"]) == 24  # 24 hours

    def test_z_score_calculation(self, anomaly_detector):
        """Test z-score calculation."""
        z_score = anomaly_detector._calculate_z_score(value=15, mean=10, std=2)
        assert z_score == 2.5  # (15-10)/2

    def test_is_anomalous_above_threshold(self, anomaly_detector):
        """Test that values above threshold are anomalous."""
        assert anomaly_detector._is_anomalous(value=20, mean=10, std=2, threshold=2.0) is True

    def test_is_anomalous_within_threshold(self, anomaly_detector):
        """Test that values within threshold are not anomalous."""
        assert anomaly_detector._is_anomalous(value=12, mean=10, std=2, threshold=2.0) is False

    @pytest.mark.asyncio
    async def test_hourly_anomaly_detection_high_severity(self, anomaly_detector):
        """Test that extreme values get HIGH severity."""
        result = await anomaly_detector.detect_hourly_anomaly(
            camera_id="cam_123",
            hour=3,  # Night time - normally very low
            current_count=50,  # Extremely high for 3am
            baseline_days=14,
        )
        assert result["is_anomaly"] is True
        assert result["severity"] in ["HIGH", "MEDIUM"]
