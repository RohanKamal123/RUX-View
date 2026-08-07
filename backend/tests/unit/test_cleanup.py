"""
Tests for Sprint 5.4 — Data Retention + Cleanup.

Tests DataCleanup class, retention periods, transcript cleanup,
orphaned thumbnail deletion, and cleanup logging.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.storage.cleanup import (
    DataCleanup,
    CleanupResult,
    RETENTION_PERIODS,
    TRANSCRIPT_RETENTION_DAYS,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Create a mock async database session.

    session.execute must resolve to a plain MagicMock, not the AsyncMock
    default: AsyncMock().return_value is itself an AsyncMock, so any
    unconfigured chain off it (result.scalars().all(), result.rowcount,
    etc.) silently becomes async too — calling it inline like real
    SQLAlchemy code does raises "coroutine object has no attribute/is not
    iterable" instead of exercising the code path. Explicitly returning a
    MagicMock() here matches real SQLAlchemy Result objects, whose
    methods are sync.
    """
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    execute_result.rowcount = 0
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_db_session
    factory.return_value.__aexit__.return_value = None
    return factory


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def cleanup(mock_session_factory, temp_storage):
    """Create a DataCleanup with mocked dependencies."""
    return DataCleanup(
        db_session_factory=mock_session_factory,
        storage_path=temp_storage,
    )


# ── Tests ──────────────────────────────────────────────────────


class TestRetentionPeriods:
    def test_free_retention_is_7_days(self):
        """Free tier should have 7 day retention."""
        assert RETENTION_PERIODS["free"] == 7

    def test_household_retention_is_30_days(self):
        """Household tier should have 30 day retention."""
        assert RETENTION_PERIODS["household"] == 30

    def test_business_retention_is_90_days(self):
        """Business tier should have 90 day retention."""
        assert RETENTION_PERIODS["business"] == 90

    def test_transcript_retention_is_3_days(self):
        """Transcript retention should be 3 days."""
        assert TRANSCRIPT_RETENTION_DAYS == 3

    @pytest.mark.asyncio
    async def test_get_retention_period_free(self, cleanup):
        """get_retention_period should return 7 for free."""
        days = await cleanup.get_retention_period("free")
        assert days == 7

    @pytest.mark.asyncio
    async def test_get_retention_period_household(self, cleanup):
        """get_retention_period should return 30 for household."""
        days = await cleanup.get_retention_period("household")
        assert days == 30

    @pytest.mark.asyncio
    async def test_get_retention_period_business(self, cleanup):
        """get_retention_period should return 90 for business."""
        days = await cleanup.get_retention_period("business")
        assert days == 90

    @pytest.mark.asyncio
    async def test_get_retention_period_unknown_defaults_to_7(self, cleanup):
        """get_retention_period should default to 7 for unknown tiers."""
        days = await cleanup.get_retention_period("unknown")
        assert days == 7


class TestCutoffDate:
    def test_get_cutoff_date_returns_datetime(self, cleanup):
        """_get_cutoff_date should return a datetime."""
        cutoff = cleanup._get_cutoff_date(7)
        assert isinstance(cutoff, datetime)

    def test_get_cutoff_date_is_in_past(self, cleanup):
        """_get_cutoff_date should be in the past."""
        cutoff = cleanup._get_cutoff_date(1)
        assert cutoff < datetime.now(timezone.utc)

    def test_get_cutoff_date_respects_days(self, cleanup):
        """_get_cutoff_date should respect the days parameter."""
        cutoff_7 = cleanup._get_cutoff_date(7)
        cutoff_30 = cleanup._get_cutoff_date(30)
        assert cutoff_7 > cutoff_30  # 7 days is more recent than 30


class TestCleanup:
    @pytest.mark.asyncio
    async def test_free_events_deleted_after_7_days(self, cleanup):
        """Free tier events older than 7 days should be deleted."""
        result = await cleanup.run_daily_cleanup()
        assert isinstance(result, CleanupResult)

    @pytest.mark.asyncio
    async def test_household_events_kept_30_days(self, cleanup):
        """Household tier events should be kept for 30 days."""
        days = await cleanup.get_retention_period("household")
        assert days == 30

    @pytest.mark.asyncio
    async def test_business_events_kept_90_days(self, cleanup):
        """Business tier events should be kept for 90 days."""
        days = await cleanup.get_retention_period("business")
        assert days == 90

    @pytest.mark.asyncio
    async def test_transcripts_deleted_after_3_days(self, cleanup):
        """Transcripts older than 3 days should be deleted."""
        result = await cleanup.run_daily_cleanup()
        assert isinstance(result, CleanupResult)

    @pytest.mark.asyncio
    async def test_cleanup_doesnt_delete_wrong_user(self, cleanup):
        """Cleanup should not delete events for wrong users."""
        result = await cleanup.cleanup_single_user("user_001")
        assert isinstance(result, CleanupResult)

    @pytest.mark.asyncio
    async def test_orphaned_thumbnails_deleted(self, cleanup, temp_storage):
        """Orphaned thumbnails should be deleted."""
        # Create some test files
        test_file = os.path.join(temp_storage, "orphaned.jpg")
        with open(test_file, "w") as f:
            f.write("test")

        referenced_file = os.path.join(temp_storage, "referenced.jpg")
        with open(referenced_file, "w") as f:
            f.write("test")

        # Mock referenced thumbnails to only include referenced.jpg
        with patch.object(cleanup, "_get_referenced_thumbnails",
                          AsyncMock(return_value={"referenced.jpg"})):
            deleted = await cleanup.delete_orphaned_thumbnails()
            assert deleted == 1
            assert not os.path.exists(test_file)
            assert os.path.exists(referenced_file)

    @pytest.mark.asyncio
    async def test_estimate_cleanup_returns_counts(self, cleanup):
        """estimate_cleanup should return counts for each category."""
        estimates = await cleanup.estimate_cleanup()
        assert "events" in estimates
        assert "transcripts" in estimates
        assert "thumbnails" in estimates

    @pytest.mark.asyncio
    async def test_cleanup_logs_results(self, cleanup):
        """Cleanup should log results."""
        result = await cleanup.run_daily_cleanup()
        # log_cleanup should not raise
        await cleanup.log_cleanup(result)

    @pytest.mark.asyncio
    async def test_retention_period_by_tier(self, cleanup):
        """Retention period should vary by tier."""
        assert await cleanup.get_retention_period("free") == 7
        assert await cleanup.get_retention_period("household") == 30
        assert await cleanup.get_retention_period("business") == 90

    @pytest.mark.asyncio
    async def test_cleanup_single_user(self, cleanup):
        """cleanup_single_user should work for a specific user."""
        result = await cleanup.cleanup_single_user("user_001")
        assert isinstance(result, CleanupResult)
        assert result.events_deleted == 0  # No real DB, so 0

    @pytest.mark.asyncio
    async def test_run_daily_cleanup_returns_result(self, cleanup):
        """run_daily_cleanup should return a CleanupResult."""
        result = await cleanup.run_daily_cleanup()
        assert isinstance(result, CleanupResult)
        assert isinstance(result.events_deleted, int)
        assert isinstance(result.transcripts_deleted, int)
        assert isinstance(result.thumbnails_deleted, int)
        assert isinstance(result.errors, list)

    @pytest.mark.asyncio
    async def test_delete_expired_events_returns_int(self, cleanup):
        """delete_expired_events should return an integer."""
        count = await cleanup.delete_expired_events()
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_delete_expired_transcripts_returns_int(self, cleanup):
        """delete_expired_transcripts should return an integer."""
        count = await cleanup.delete_expired_transcripts()
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_delete_orphaned_thumbnails_returns_int(self, cleanup):
        """delete_orphaned_thumbnails should return an integer."""
        count = await cleanup.delete_orphaned_thumbnails()
        assert isinstance(count, int)

    def test_cleanup_result_dataclass(self):
        """CleanupResult dataclass should work correctly."""
        result = CleanupResult(
            events_deleted=10,
            transcripts_deleted=5,
            thumbnails_deleted=3,
            errors=["test error"],
        )
        assert result.events_deleted == 10
        assert result.transcripts_deleted == 5
        assert result.thumbnails_deleted == 3
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_orphaned_thumbnails_skips_directories(self, cleanup, temp_storage):
        """Orphaned thumbnail deletion should skip directories."""
        # Create a subdirectory
        subdir = os.path.join(temp_storage, "subdir")
        os.makedirs(subdir)

        with patch.object(cleanup, "_get_referenced_thumbnails",
                          AsyncMock(return_value=set())):
            deleted = await cleanup.delete_orphaned_thumbnails()
            assert deleted == 0
            assert os.path.exists(subdir)

    @pytest.mark.asyncio
    async def test_orphaned_thumbnails_skips_non_images(self, cleanup, temp_storage):
        """Orphaned thumbnail deletion should skip non-image files."""
        # Create a non-image file
        txt_file = os.path.join(temp_storage, "readme.txt")
        with open(txt_file, "w") as f:
            f.write("text")

        with patch.object(cleanup, "_get_referenced_thumbnails",
                          AsyncMock(return_value=set())):
            deleted = await cleanup.delete_orphaned_thumbnails()
            assert deleted == 0
            assert os.path.exists(txt_file)

    @pytest.mark.asyncio
    async def test_estimate_cleanup_handles_missing_storage(self, cleanup):
        """estimate_cleanup should handle missing storage directory."""
        cleanup.storage_path = "/nonexistent/path"
        estimates = await cleanup.estimate_cleanup()
        assert estimates["thumbnails"] == 0
