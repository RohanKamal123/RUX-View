"""
Tests for Sprint 4.2 — Shop Analytics Mode.

Tests customer entry recording, hourly aggregation, demographic breakdowns,
peak hours, dwell time, repeat customer detection, and weekly reports.
"""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.analytics.shop_analytics import (
    ShopAnalytics,
    CustomerEntry,
    HourlyAnalytics,
    DailySummary,
    MIN_DWELL_SECONDS,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_db_session
    factory.return_value.__aexit__.return_value = None
    return factory


@pytest.fixture
def shop_analytics(mock_session_factory):
    """Create a ShopAnalytics instance with mocked dependencies."""
    return ShopAnalytics(db_session_factory=mock_session_factory)


@pytest.fixture
def sample_gemma_result():
    """Sample Gemma analysis result for a customer."""
    return {
        "gender": "male",
        "age_group": "30s",
        "carried_items": ["bag"],
        "group_size": 1,
        "confidence": 0.92,
    }


@pytest.fixture
def sample_gemma_female():
    """Sample Gemma result for a female customer."""
    return {
        "gender": "female",
        "age_group": "20s",
        "carried_items": [],
        "group_size": 1,
        "confidence": 0.88,
    }


# ── Tests ──────────────────────────────────────────────────────


class TestShopAnalytics:
    @pytest.mark.asyncio
    async def test_record_entry_upserts_hourly_bucket(
        self, shop_analytics, mock_db_session, sample_gemma_result
    ):
        """Recording an entry should upsert the hourly analytics bucket."""
        # Mock no existing bucket
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        timestamp = datetime.now(timezone.utc).replace(hour=10, minute=30)
        result = await shop_analytics.record_entry(
            camera_id="cam_01",
            user_id="user_001",
            timestamp=timestamp,
            gemma_result=sample_gemma_result,
            person_uid="P_001",
        )

        assert isinstance(result, CustomerEntry)
        assert result.person_uid == "P_001"
        assert result.gender == "male"
        assert result.age_group == "30s"
        assert result.is_staff is False

        # Should have added a new ShopAnalytic
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_staff_not_counted_as_customer(
        self, shop_analytics, mock_db_session, sample_gemma_result
    ):
        """Staff entries should be filtered out and not counted."""
        timestamp = datetime.now(timezone.utc)
        result = await shop_analytics.record_entry(
            camera_id="cam_01",
            user_id="user_001",
            timestamp=timestamp,
            gemma_result=sample_gemma_result,
            person_uid="STAFF_001",
            is_staff=True,
        )

        assert result.is_staff is True
        # Should NOT have added to analytics
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_demographic_breakdown_totals(
        self, shop_analytics, mock_db_session
    ):
        """Demographic breakdown should return correct totals."""
        # Mock hourly buckets
        mock_bucket_1 = MagicMock()
        mock_bucket_1.hour = 10
        mock_bucket_1.customer_count = 5
        mock_bucket_1.male_count = 3
        mock_bucket_1.female_count = 2
        mock_bucket_1.unknown_gender = 0
        mock_bucket_1.age_teens = 1
        mock_bucket_1.age_20s = 2
        mock_bucket_1.age_30s = 1
        mock_bucket_1.age_40s = 1
        mock_bucket_1.age_50plus = 0
        mock_bucket_1.avg_dwell_seconds = 120.0

        mock_bucket_2 = MagicMock()
        mock_bucket_2.hour = 11
        mock_bucket_2.customer_count = 3
        mock_bucket_2.male_count = 1
        mock_bucket_2.female_count = 1
        mock_bucket_2.unknown_gender = 1
        mock_bucket_2.age_teens = 0
        mock_bucket_2.age_20s = 1
        mock_bucket_2.age_30s = 1
        mock_bucket_2.age_40s = 0
        mock_bucket_2.age_50plus = 1
        mock_bucket_2.avg_dwell_seconds = 90.0

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_bucket_1,
            mock_bucket_2,
        ]

        analytics_date = date(2024, 6, 15)
        breakdown = await shop_analytics.get_demographic_breakdown(
            "cam_01", analytics_date
        )

        assert breakdown["gender"]["male"] == 4
        assert breakdown["gender"]["female"] == 3
        assert breakdown["gender"]["unknown"] == 1
        assert breakdown["age"]["teens"] == 1
        assert breakdown["age"]["20s"] == 3
        assert breakdown["age"]["30s"] == 2
        assert breakdown["age"]["40s"] == 1
        assert breakdown["age"]["50plus"] == 1

    @pytest.mark.asyncio
    async def test_peak_hours_sorted_descending(
        self, shop_analytics, mock_db_session
    ):
        """Peak hours should be sorted by count descending."""
        mock_bucket_10 = MagicMock()
        mock_bucket_10.hour = 10
        mock_bucket_10.customer_count = 5
        mock_bucket_10.male_count = 3
        mock_bucket_10.female_count = 2
        mock_bucket_10.unknown_gender = 0
        mock_bucket_10.age_teens = 0
        mock_bucket_10.age_20s = 0
        mock_bucket_10.age_30s = 0
        mock_bucket_10.age_40s = 0
        mock_bucket_10.age_50plus = 0
        mock_bucket_10.avg_dwell_seconds = 0.0

        mock_bucket_14 = MagicMock()
        mock_bucket_14.hour = 14
        mock_bucket_14.customer_count = 12
        mock_bucket_14.male_count = 0
        mock_bucket_14.female_count = 0
        mock_bucket_14.unknown_gender = 0
        mock_bucket_14.age_teens = 0
        mock_bucket_14.age_20s = 0
        mock_bucket_14.age_30s = 0
        mock_bucket_14.age_40s = 0
        mock_bucket_14.age_50plus = 0
        mock_bucket_14.avg_dwell_seconds = 0.0

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_bucket_10,
            mock_bucket_14,
        ]

        analytics_date = date(2024, 6, 15)
        peaks = await shop_analytics.get_peak_hours("cam_01", analytics_date)

        assert len(peaks) == 2
        assert peaks[0]["hour"] == 14  # Highest first
        assert peaks[0]["count"] == 12
        assert peaks[1]["hour"] == 10
        assert peaks[1]["count"] == 5

    @pytest.mark.asyncio
    async def test_daily_summary_aggregation(
        self, shop_analytics, mock_db_session
    ):
        """Daily summary should aggregate all hourly data correctly."""
        mock_bucket = MagicMock()
        mock_bucket.hour = 10
        mock_bucket.customer_count = 8
        mock_bucket.male_count = 5
        mock_bucket.female_count = 3
        mock_bucket.unknown_gender = 0
        mock_bucket.age_teens = 1
        mock_bucket.age_20s = 3
        mock_bucket.age_30s = 2
        mock_bucket.age_40s = 1
        mock_bucket.age_50plus = 1
        mock_bucket.avg_dwell_seconds = 150.0

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_bucket,
        ]

        # Mock unique and repeat counts
        mock_db_session.execute.return_value.scalar.return_value = 5

        analytics_date = date(2024, 6, 15)
        summary = await shop_analytics.get_daily_summary("cam_01", analytics_date)

        assert summary.total_customers == 8
        assert summary.gender_breakdown["male"] == 5
        assert summary.gender_breakdown["female"] == 3
        assert summary.peak_hour == 10
        assert summary.avg_dwell_seconds > 0

    @pytest.mark.asyncio
    async def test_repeat_customer_detection(
        self, shop_analytics, mock_db_session
    ):
        """Repeat customer detection should find customers with multiple visits."""
        mock_sighting_1 = MagicMock()
        mock_sighting_1.person_uid = "P_001"
        mock_sighting_1.timestamp = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_sighting_1.clothing_colors = "red shirt"

        mock_sighting_2 = MagicMock()
        mock_sighting_2.person_uid = "P_001"
        mock_sighting_2.timestamp = datetime(2024, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        mock_sighting_2.clothing_colors = "red shirt"

        mock_sighting_3 = MagicMock()
        mock_sighting_3.person_uid = "P_002"
        mock_sighting_3.timestamp = datetime(2024, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        mock_sighting_3.clothing_colors = "blue shirt"

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_sighting_1,
            mock_sighting_2,
            mock_sighting_3,
        ]

        analytics_date = date(2024, 6, 15)
        repeat = await shop_analytics.get_repeat_customers(
            "cam_01", analytics_date, min_visits=2
        )

        assert len(repeat) == 1
        assert repeat[0]["person_uid"] == "P_001"
        assert repeat[0]["visit_count"] == 2

    @pytest.mark.asyncio
    async def test_weekly_report_generation(
        self, shop_analytics, mock_db_session
    ):
        """Weekly report should aggregate 7 days of data."""
        # Mock hourly buckets for each day
        mock_bucket = MagicMock()
        mock_bucket.hour = 10
        mock_bucket.customer_count = 5
        mock_bucket.male_count = 3
        mock_bucket.female_count = 2
        mock_bucket.unknown_gender = 0
        mock_bucket.age_teens = 1
        mock_bucket.age_20s = 2
        mock_bucket.age_30s = 1
        mock_bucket.age_40s = 1
        mock_bucket.age_50plus = 0
        mock_bucket.avg_dwell_seconds = 120.0

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_bucket,
        ]
        mock_db_session.execute.return_value.scalar.return_value = 3

        week_start = date(2024, 6, 10)  # Monday
        report = await shop_analytics.get_weekly_report("cam_01", week_start)

        assert report["total_customers"] > 0
        assert report["avg_daily"] > 0
        assert report["peak_hour"] is not None
        assert "repeat_rate" in report

    def test_dwell_time_calculation(self, shop_analytics):
        """Dwell time should be calculated correctly with minimum threshold."""
        entry = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        exit_short = datetime(2024, 6, 15, 10, 0, 20, tzinfo=timezone.utc)  # 20s
        exit_long = datetime(2024, 6, 15, 10, 5, 0, tzinfo=timezone.utc)  # 300s

        # Below minimum
        assert shop_analytics._calculate_dwell(entry, exit_short) is None

        # Above minimum
        dwell = shop_analytics._calculate_dwell(entry, exit_long)
        assert dwell == 300.0

    @pytest.mark.asyncio
    async def test_get_hourly_breakdown_returns_24_entries(
        self, shop_analytics, mock_db_session
    ):
        """Hourly breakdown should always return 24 entries (0-23)."""
        # Only one bucket in DB
        mock_bucket = MagicMock()
        mock_bucket.hour = 10
        mock_bucket.customer_count = 5
        mock_bucket.male_count = 3
        mock_bucket.female_count = 2
        mock_bucket.unknown_gender = 0
        mock_bucket.age_teens = 1
        mock_bucket.age_20s = 2
        mock_bucket.age_30s = 1
        mock_bucket.age_40s = 1
        mock_bucket.age_50plus = 0
        mock_bucket.avg_dwell_seconds = 120.0
        mock_bucket.camera_id = "cam_01"
        mock_bucket.date = date(2024, 6, 15)

        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_bucket,
        ]

        analytics_date = date(2024, 6, 15)
        hourly = await shop_analytics.get_hourly_breakdown("cam_01", analytics_date)

        assert len(hourly) == 24
        assert hourly[10].customer_count == 5  # The one with data
        assert hourly[0].customer_count == 0  # Empty bucket

    @pytest.mark.asyncio
    async def test_crm_tracking_visit_count(
        self, shop_analytics, mock_db_session
    ):
        """CRM tracking should return visit count for a person."""
        mock_db_session.execute.return_value.scalar.return_value = 3

        timestamp = datetime.now(timezone.utc)
        result = await shop_analytics.record_entry(
            camera_id="cam_01",
            user_id="user_001",
            timestamp=timestamp,
            gemma_result={"gender": "male", "age_group": "30s"},
            person_uid="P_001",
        )

        assert result.visit_count_today >= 1

    def test_is_staff_check(self, shop_analytics):
        """Staff check should identify staff by ID or entrance zone."""
        staff_ids = ["STAFF_001", "STAFF_002"]
        staff_zones = ["staff_entrance", "back_door"]

        assert shop_analytics._is_staff("STAFF_001", "main_entrance", staff_ids, staff_zones) is True
        assert shop_analytics._is_staff("CUST_001", "staff_entrance", staff_ids, staff_zones) is True
        assert shop_analytics._is_staff("CUST_001", "main_entrance", staff_ids, staff_zones) is False

    def test_customer_entry_dataclass(self):
        """CustomerEntry dataclass should work correctly."""
        entry = CustomerEntry(
            person_uid="P_001",
            camera_id="cam_01",
            timestamp=datetime.now(timezone.utc),
            gender="male",
            age_group="30s",
        )
        assert entry.person_uid == "P_001"
        assert entry.is_staff is False
        assert entry.dwell_seconds is None

    def test_hourly_analytics_dataclass(self):
        """HourlyAnalytics dataclass should work correctly."""
        ha = HourlyAnalytics(
            camera_id="cam_01",
            date=date(2024, 6, 15),
            hour=10,
            customer_count=5,
        )
        assert ha.hour == 10
        assert ha.customer_count == 5

    def test_daily_summary_dataclass(self):
        """DailySummary dataclass should work correctly."""
        summary = DailySummary(
            camera_id="cam_01",
            date=date(2024, 6, 15),
            total_customers=50,
            peak_hour=14,
        )
        assert summary.total_customers == 50
        assert summary.peak_hour == 14
        assert summary.gender_breakdown == {"male": 0, "female": 0, "unknown": 0}
