"""
cleanup.py — Data Retention and Cleanup for Vision OS.

Retention periods by tier:
- Free = 7 days
- Household = 30 days
- Business = 90 days

Audio transcripts deleted after 1-3 days (privacy — D020).
Thumbnails deleted with events.
Runs daily at 03:00 via APScheduler cron job.
Logs all deletions for audit.

Key decisions:
- D020: Whisper transcript stored only 1-3 days
- D024: APScheduler (NOT `schedule` library)
- D026: All calls async
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    events_deleted: int = 0
    transcripts_deleted: int = 0
    thumbnails_deleted: int = 0
    persons_merged: int = 0
    errors: list[str] = field(default_factory=list)


# ── Retention Periods ──────────────────────────────────────────

RETENTION_PERIODS = {
    "free": 7,
    "household": 30,
    "business": 90,
}

TRANSCRIPT_RETENTION_DAYS = 3


class DataCleanup:
    """Data retention and cleanup jobs."""

    def __init__(self, db_session_factory,
                 storage_path: str = "./storage"):
        """Initialize data cleanup.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            storage_path: Path to thumbnail storage directory.
        """
        self.db_session_factory = db_session_factory
        self.storage_path = storage_path

    async def run_daily_cleanup(self) -> CleanupResult:
        """Run all cleanup jobs.

        Called by APScheduler cron job at 03:00 daily.

        Steps:
        1. Delete expired events by tier
        2. Delete expired transcripts (1-3 days)
        3. Delete orphaned thumbnails
        4. Log all deletions

        Returns:
            CleanupResult with counts.
        """
        result = CleanupResult()

        try:
            # Step 1: Delete expired events
            events_deleted = await self.delete_expired_events()
            result.events_deleted = events_deleted
            logger.info("Deleted %d expired events", events_deleted)
        except Exception as exc:
            error_msg = f"Failed to delete expired events: {exc}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

        try:
            # Step 2: Delete expired transcripts
            transcripts_deleted = await self.delete_expired_transcripts()
            result.transcripts_deleted = transcripts_deleted
            logger.info("Deleted %d expired transcripts", transcripts_deleted)
        except Exception as exc:
            error_msg = f"Failed to delete expired transcripts: {exc}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

        try:
            # Step 3: Delete orphaned thumbnails
            thumbnails_deleted = await self.delete_orphaned_thumbnails()
            result.thumbnails_deleted = thumbnails_deleted
            logger.info("Deleted %d orphaned thumbnails", thumbnails_deleted)
        except Exception as exc:
            error_msg = f"Failed to delete orphaned thumbnails: {exc}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

        # Log cleanup results
        try:
            await self.log_cleanup(result)
        except Exception as exc:
            logger.error("Failed to log cleanup: %s", exc, exc_info=True)

        return result

    async def delete_expired_events(self) -> int:
        """Delete events older than retention period for each tier.

        Free: 7 days
        Household: 30 days
        Business: 90 days

        Returns:
            Number of events deleted.
        """
        total_deleted = 0

        for tier, days in RETENTION_PERIODS.items():
            cutoff = self._get_cutoff_date(days)
            try:
                # In production, execute SQL:
                # DELETE FROM events
                # WHERE user_id IN (SELECT id FROM users WHERE tier = '{tier}')
                #   AND timestamp_start < '{cutoff}'
                deleted = await self._delete_events_for_tier(tier, cutoff)
                total_deleted += deleted
                logger.info(
                    "Deleted %d events for tier '%s' (cutoff: %s)",
                    deleted, tier, cutoff,
                )
            except Exception as exc:
                logger.error(
                    "Failed to delete events for tier '%s': %s",
                    tier, exc, exc_info=True,
                )

        return total_deleted

    async def delete_expired_transcripts(
        self, retention_days: int = TRANSCRIPT_RETENTION_DAYS
    ) -> int:
        """Delete audio transcripts older than retention period.

        Args:
            retention_days: Days to keep transcripts (default 3).

        Returns:
            Number of transcripts deleted.
        """
        cutoff = self._get_cutoff_date(retention_days)

        try:
            # In production, execute SQL:
            # DELETE FROM audio_events
            # WHERE transcript IS NOT NULL
            #   AND timestamp < '{cutoff}'
            deleted = await self._delete_transcripts_before(cutoff)
            logger.info(
                "Deleted %d transcripts (cutoff: %s, retention: %d days)",
                deleted, cutoff, retention_days,
            )
            return deleted
        except Exception as exc:
            logger.error(
                "Failed to delete transcripts: %s", exc, exc_info=True,
            )
            raise

    async def delete_orphaned_thumbnails(self) -> int:
        """Delete thumbnail files not referenced by any event.

        Returns:
            Number of files deleted.
        """
        deleted_count = 0

        if not os.path.exists(self.storage_path):
            logger.warning("Storage path does not exist: %s", self.storage_path)
            return 0

        try:
            # Get all thumbnail filenames referenced in database
            referenced = await self._get_referenced_thumbnails()

            # Scan storage directory for orphaned files
            for filename in os.listdir(self.storage_path):
                filepath = os.path.join(self.storage_path, filename)

                # Skip directories
                if os.path.isdir(filepath):
                    continue

                # Skip non-image files
                if not filename.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp")
                ):
                    continue

                # Delete if not referenced
                if filename not in referenced:
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug("Deleted orphaned thumbnail: %s", filepath)
                    except OSError as exc:
                        logger.error(
                            "Failed to delete thumbnail %s: %s",
                            filepath, exc,
                        )

            logger.info("Deleted %d orphaned thumbnails", deleted_count)
        except Exception as exc:
            logger.error(
                "Failed to delete orphaned thumbnails: %s",
                exc, exc_info=True,
            )
            raise

        return deleted_count

    async def get_retention_period(self, tier: str) -> int:
        """Get retention period in days for a tier.

        Args:
            tier: User tier (free/household/business).

        Returns:
            Number of days for retention period.
        """
        return RETENTION_PERIODS.get(tier.lower(), 7)

    def _get_cutoff_date(self, days: int) -> datetime:
        """Get cutoff datetime for retention period.

        Args:
            days: Number of days to keep.

        Returns:
            Datetime in UTC for the cutoff.
        """
        return datetime.now(timezone.utc) - timedelta(days=days)

    async def log_cleanup(self, result: CleanupResult) -> None:
        """Log cleanup results to audit table.

        Creates cleanup_log entry with timestamp and counts.

        Args:
            result: CleanupResult with deletion counts.
        """
        # In production, insert into cleanup_log table:
        # INSERT INTO cleanup_log
        #   (timestamp, events_deleted, transcripts_deleted,
        #    thumbnails_deleted, persons_merged, errors)
        # VALUES
        #   (NOW(), {result.events_deleted}, {result.transcripts_deleted},
        #    {result.thumbnails_deleted}, {result.persons_merged},
        #    {json.dumps(result.errors)})
        logger.info(
            "Cleanup completed: events=%d, transcripts=%d, "
            "thumbnails=%d, errors=%d",
            result.events_deleted,
            result.transcripts_deleted,
            result.thumbnails_deleted,
            len(result.errors),
        )

    async def estimate_cleanup(self) -> dict:
        """Estimate how many records would be deleted without actually deleting.

        Returns:
            Dict with events, transcripts, thumbnails counts.
            Useful for dashboard display: "Next cleanup will remove X old events"
        """
        estimates = {
            "events": 0,
            "transcripts": 0,
            "thumbnails": 0,
        }

        # Estimate expired events
        for tier, days in RETENTION_PERIODS.items():
            cutoff = self._get_cutoff_date(days)
            try:
                count = await self._count_events_for_tier(tier, cutoff)
                estimates["events"] += count
            except Exception as exc:
                logger.error(
                    "Failed to estimate events for tier '%s': %s",
                    tier, exc,
                )

        # Estimate expired transcripts
        cutoff = self._get_cutoff_date(TRANSCRIPT_RETENTION_DAYS)
        try:
            estimates["transcripts"] = await self._count_transcripts_before(cutoff)
        except Exception as exc:
            logger.error("Failed to estimate transcripts: %s", exc)

        # Estimate orphaned thumbnails
        try:
            estimates["thumbnails"] = await self._count_orphaned_thumbnails()
        except Exception as exc:
            logger.error("Failed to estimate thumbnails: %s", exc)

        return estimates

    async def cleanup_single_user(self, user_id: str) -> CleanupResult:
        """Run cleanup for a single user (useful for manual trigger).

        Args:
            user_id: User UUID to clean up.

        Returns:
            CleanupResult for that user.
        """
        result = CleanupResult()

        try:
            # Get user's tier
            tier = await self._get_user_tier(user_id)
            days = await self.get_retention_period(tier)
            cutoff = self._get_cutoff_date(days)

            # Delete user's expired events
            deleted = await self._delete_events_for_user(user_id, cutoff)
            result.events_deleted = deleted
            logger.info(
                "Deleted %d events for user %s (tier: %s, cutoff: %s)",
                deleted, user_id, tier, cutoff,
            )
        except Exception as exc:
            error_msg = f"Failed cleanup for user {user_id}: {exc}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)

        return result

    # ── Database Helper Methods (to be implemented with real SQL) ──

    async def _delete_events_for_tier(self, tier: str,
                                      cutoff: datetime) -> int:
        """Delete events for a specific tier older than cutoff.

        Args:
            tier: User tier.
            cutoff: Cutoff datetime.

        Returns:
            Number of deleted events.
        """
        # TODO: Implement with real SQLAlchemy query
        # async with self.db_session_factory() as session:
        #     result = await session.execute(
        #         delete(Event).where(
        #             Event.user_id.in_(
        #                 select(User.id).where(User.tier == tier)
        #             ),
        #             Event.timestamp_start < cutoff
        #         )
        #     )
        #     await session.commit()
        #     return result.rowcount
        logger.debug(
            "Would delete events for tier '%s' before %s", tier, cutoff
        )
        return 0

    async def _delete_transcripts_before(self, cutoff: datetime) -> int:
        """Delete transcripts older than cutoff.

        Args:
            cutoff: Cutoff datetime.

        Returns:
            Number of deleted transcripts.
        """
        # TODO: Implement with real SQLAlchemy query
        logger.debug("Would delete transcripts before %s", cutoff)
        return 0

    async def _get_referenced_thumbnails(self) -> set[str]:
        """Get set of thumbnail filenames referenced in database.

        Returns:
            Set of referenced thumbnail filenames.
        """
        # TODO: Implement with real SQLAlchemy query
        logger.debug("Would fetch referenced thumbnails from database")
        return set()

    async def _count_events_for_tier(self, tier: str,
                                     cutoff: datetime) -> int:
        """Count events for a specific tier older than cutoff.

        Args:
            tier: User tier.
            cutoff: Cutoff datetime.

        Returns:
            Count of events.
        """
        # TODO: Implement with real SQLAlchemy query
        return 0

    async def _count_transcripts_before(self, cutoff: datetime) -> int:
        """Count transcripts older than cutoff.

        Args:
            cutoff: Cutoff datetime.

        Returns:
            Count of transcripts.
        """
        # TODO: Implement with real SQLAlchemy query
        return 0

    async def _count_orphaned_thumbnails(self) -> int:
        """Count orphaned thumbnail files.

        Returns:
            Count of orphaned files.
        """
        if not os.path.exists(self.storage_path):
            return 0

        referenced = await self._get_referenced_thumbnails()
        orphaned = 0

        for filename in os.listdir(self.storage_path):
            filepath = os.path.join(self.storage_path, filename)
            if os.path.isfile(filepath) and filename not in referenced:
                orphaned += 1

        return orphaned

    async def _get_user_tier(self, user_id: str) -> str:
        """Get user's tier from database.

        Args:
            user_id: User UUID.

        Returns:
            User tier string.
        """
        # TODO: Implement with real SQLAlchemy query
        return "free"

    async def _delete_events_for_user(self, user_id: str,
                                      cutoff: datetime) -> int:
        """Delete events for a specific user older than cutoff.

        Args:
            user_id: User UUID.
            cutoff: Cutoff datetime.

        Returns:
            Number of deleted events.
        """
        # TODO: Implement with real SQLAlchemy query
        logger.debug(
            "Would delete events for user %s before %s", user_id, cutoff
        )
        return 0
