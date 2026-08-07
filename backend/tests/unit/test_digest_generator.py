"""
Tests for Sprint 4.3 — Digest Generator.

Tests digest generation for all three tiers, formatting templates,
word limits, weekly aggregation, and Telegram sending.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.analytics.digest_generator import (
    DigestGenerator,
    DigestData,
    TIER_WORD_LIMITS,
)
from backend.analytics.report_builder import (
    ReportBuilder,
    BusinessReport,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Create a mock async database session.

    session.execute must resolve to a plain MagicMock, not the AsyncMock
    default: AsyncMock().return_value is itself an AsyncMock, so an
    unconfigured chain off it (result.scalars().all(), etc.) silently
    becomes async too — calling it inline like real SQLAlchemy code does
    raises "coroutine object has no attribute 'all'" instead of exercising
    the code path, and any .return_value/.side_effect configured on the
    chain (see test bodies below) never actually takes effect since the
    intermediate .scalars is itself an unawaited AsyncMock call.
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
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
def mock_ai_client():
    """Create a mock AI client."""
    client = AsyncMock()
    client.generate_content_async = AsyncMock()
    response = MagicMock()
    response.text = "Security recommendation: review camera placement."
    client.generate_content_async.return_value = response
    return client


@pytest.fixture
def mock_telegram():
    """Create a mock Telegram client."""
    tg = AsyncMock()
    tg.send_text = AsyncMock()
    return tg


@pytest.fixture
def digest_generator(mock_session_factory, mock_ai_client, mock_telegram):
    """Create a DigestGenerator with mocked dependencies."""
    return DigestGenerator(
        db_session_factory=mock_session_factory,
        ai_client=mock_ai_client,
        telegram_client=mock_telegram,
    )


@pytest.fixture
def report_builder(mock_session_factory, mock_ai_client):
    """Create a ReportBuilder with mocked dependencies."""
    return ReportBuilder(
        db_session_factory=mock_session_factory,
        ai_client=mock_ai_client,
    )


# ── DigestGenerator Tests ──────────────────────────────────────


class TestDigestGenerator:
    def test_free_digest_under_200_words(self, digest_generator):
        """Free tier digest should be under 200 words."""
        events = {"total": 3, "high": 1, "medium": 1, "low": 1, "audio_count": 2}
        persons = {"total": 5, "familiar": 3, "unknown": 2, "flagged": []}

        text = digest_generator._format_free_digest(events, persons)
        word_count = len(text.split())

        assert word_count <= 200
        assert "VisionOS Daily" in text
        assert "Events:" in text
        assert "Visitors:" in text

    def test_household_digest_includes_person_stats(self, digest_generator):
        """Household digest should include detailed person stats."""
        events = {"total": 5, "high": 2, "medium": 2, "low": 1, "audio_count": 3}
        persons = {
            "total": 8,
            "familiar": 5,
            "unknown": 3,
            "flagged": [{"person_uid": "P_001", "count": 4}],
        }
        audio = {"total": 3, "top_class": "Speech", "top_time": "14:30"}

        text = digest_generator._format_household_digest(events, persons, audio)

        assert "Security:" in text
        assert "HIGH:" in text
        assert "MEDIUM:" in text
        assert "LOW:" in text
        assert "Visitors:" in text
        assert "flagged" in text.lower() or "P_001" in text
        assert "Audio:" in text

    def test_business_digest_includes_analytics(self, digest_generator):
        """Business digest should include shop analytics section."""
        events = {"total": 10, "high": 3, "medium": 4, "low": 3, "audio_count": 5}
        persons = {"total": 15, "familiar": 10, "unknown": 5, "flagged": []}
        audio = {"total": 5, "top_class": "Gunshot, gunfire", "top_time": "02:15"}
        shop = {"total_customers": 45, "peak_hour": 14, "avg_dwell": 180.0}

        text = digest_generator._format_business_digest(events, persons, audio, shop)

        assert "Shop Analytics:" in text
        assert "Customers:" in text
        assert "Peak hour:" in text
        assert "Avg dwell:" in text

    @pytest.mark.asyncio
    async def test_digest_sends_to_telegram(
        self, digest_generator, mock_db_session
    ):
        """Digest should be sent via Telegram."""
        # Mock user and location queries
        mock_user = MagicMock()
        mock_user.id = "user_001"
        mock_user.tier = "free"
        mock_user.telegram_chat_id = "chat_001"

        mock_location = MagicMock()
        mock_location.id = "loc_001"

        # First call returns user, second returns locations
        mock_db_session.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_user],  # Users
            [mock_location],  # Locations
        ]

        # Mock event queries to return empty
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        sent = await digest_generator.send_daily_digests()

        assert sent == 1
        digest_generator.telegram.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_weekly_digest_aggregates_7_days(
        self, digest_generator, mock_db_session
    ):
        """Weekly digest should aggregate 7 days of data."""
        # Mock user tier
        mock_user = MagicMock()
        mock_user.tier = "free"
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user

        # Mock event queries to return empty
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        week_start = date(2024, 6, 10)
        text = await digest_generator.generate_weekly_digest(
            user_id="user_001",
            location_id="loc_001",
            week_start=week_start,
        )

        assert isinstance(text, str)
        assert len(text) > 0

    def test_format_free_digest_template(self, digest_generator):
        """Free digest should follow the specified template."""
        events = {"total": 0, "high": 0, "medium": 0, "low": 0, "audio_count": 0}
        persons = {"total": 0, "familiar": 0, "unknown": 0, "flagged": []}

        text = digest_generator._format_free_digest(events, persons)

        assert "VisionOS Daily" in text
        assert "All clear today." in text

    def test_format_household_digest_template(self, digest_generator):
        """Household digest should follow the specified template."""
        events = {"total": 2, "high": 1, "medium": 1, "low": 0, "audio_count": 1}
        persons = {"total": 3, "familiar": 2, "unknown": 1, "flagged": []}
        audio = {"total": 1, "top_class": "Speech", "top_time": "10:00"}

        text = digest_generator._format_household_digest(events, persons, audio)

        assert "VisionOS Daily Summary" in text
        assert "Security:" in text
        assert "HIGH: 1" in text
        assert "MEDIUM: 1" in text

    def test_format_business_digest_template(self, digest_generator):
        """Business digest should follow the specified template."""
        events = {"total": 5, "high": 2, "medium": 2, "low": 1, "audio_count": 3}
        persons = {"total": 10, "familiar": 7, "unknown": 3, "flagged": []}
        audio = {"total": 3, "top_class": "Alarm", "top_time": "08:00"}
        shop = {"total_customers": 100, "peak_hour": 12, "avg_dwell": 240.0}

        text = digest_generator._format_business_digest(events, persons, audio, shop)

        assert "VisionOS Daily Summary" in text
        assert "Shop Analytics:" in text
        assert "Customers: 100" in text

    def test_tier_word_limits(self, digest_generator):
        """Tier word limits should be correct."""
        assert digest_generator._get_tier_limit("free") == 200
        assert digest_generator._get_tier_limit("household") == 500
        assert digest_generator._get_tier_limit("business") == 1000
        assert digest_generator._get_tier_limit("unknown") == 200  # Default

    @pytest.mark.asyncio
    async def test_report_builder_weekly_report(self, report_builder, mock_db_session):
        """ReportBuilder should generate a weekly report."""
        # Mock location name
        mock_location = MagicMock()
        mock_location.name = "Test Shop"
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        # Mock events
        mock_event = MagicMock()
        mock_event.threat_level = "HIGH"
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_event,
        ]

        # Mock unique persons count
        mock_db_session.execute.return_value.scalar.return_value = 5

        week_start = date(2024, 6, 10)
        report = await report_builder.build_weekly_report(
            user_id="user_001",
            location_id="loc_001",
            week_start=week_start,
        )

        assert isinstance(report, BusinessReport)
        assert report.location_name == "Test Shop"
        assert report.total_events == 1
        assert report.high_threat_events == 1
        assert report.unique_persons == 5

    def test_report_builder_format_text(self, report_builder):
        """Report text should be plain text without markdown."""
        report = BusinessReport(
            location_name="Test Shop",
            week_start=date(2024, 6, 10),
            week_end=date(2024, 6, 16),
            total_events=10,
            high_threat_events=3,
            unique_persons=20,
            audio_events=5,
            recommendations=["Test recommendation"],
        )

        text = report_builder.format_report_text(report)

        assert "VisionOS Weekly Report" in text
        assert "Test Shop" in text
        assert "Test recommendation" in text
        # No markdown
        assert "**" not in text
        assert "##" not in text

    def test_digest_data_dataclass(self):
        """DigestData dataclass should work correctly."""
        data = DigestData(
            user_id="user_001",
            location_id="loc_001",
            date=date(2024, 6, 15),
            tier="business",
        )
        assert data.user_id == "user_001"
        assert data.tier == "business"
        assert data.events_summary == {}

    def test_business_report_dataclass(self):
        """BusinessReport dataclass should work correctly."""
        report = BusinessReport(
            location_name="Test",
            week_start=date(2024, 6, 10),
            week_end=date(2024, 6, 16),
            total_events=50,
            high_threat_events=5,
        )
        assert report.total_events == 50
        assert report.repeat_offenders == []
        assert report.recommendations == []

    @pytest.mark.asyncio
    async def test_digest_generates_for_all_tiers(
        self, digest_generator, mock_db_session
    ):
        """Digest should generate for all three tiers."""
        # Mock user with different tiers
        for tier in ["free", "household", "business"]:
            mock_user = MagicMock()
            mock_user.tier = tier
            mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user
            mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

            text = await digest_generator.generate_daily_digest(
                user_id="user_001",
                location_id="loc_001",
                digest_date=date(2024, 6, 15),
            )

            assert isinstance(text, str)
            assert len(text) > 0
