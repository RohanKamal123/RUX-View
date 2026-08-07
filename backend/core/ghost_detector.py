"""
ghost_detector.py — Detect persons who entered but haven't been seen leaving.

Tracks entries in-memory and schedules checks at 10min (MEDIUM) and 30min (HIGH).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GhostAlert:
    person_uid: str
    camera_id: str
    timestamp: datetime
    alert_level: str  # MEDIUM / HIGH
    message: str
    dismissed: bool = False


@dataclass
class _GhostEntry:
    person_uid: str
    camera_id: str
    location_id: str
    entry_time: datetime
    medium_alert_sent: bool = False
    high_alert_sent: bool = False
    resolved: bool = False


class GhostDetector:
    """Detect persons who entered but haven't been seen leaving."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize ghost detector with in-memory tracking.

        Args:
            config: Optional runtime config dict (e.g. from config_store).
                    ``ghost_check_interval_sec``, ``ghost_high_alert_sec``,
                    and ``ghost_medium_alert_sec`` are read from it.
        """
        self._entries: dict[str, _GhostEntry] = {}  # person_uid → entry
        self._check_interval = config.get("ghost_check_interval_sec", 60) if config else 60
        self._high_alert_sec = config.get("ghost_high_alert_sec", 1800) if config else 1800
        self._medium_alert_sec = config.get("ghost_medium_alert_sec", 600) if config else 600

    async def track_entry(self, person_uid: str, camera_id: str,
                           location_id: str, timestamp: datetime) -> None:
        """Record a person entry for ghost tracking.

        Schedules checks at 10min (MEDIUM) and 30min (HIGH).

        Args:
            person_uid: Person identifier.
            camera_id: Camera where entry was observed.
            location_id: Location UUID.
            timestamp: When the entry was observed.
        """
        self._entries[person_uid] = _GhostEntry(
            person_uid=person_uid,
            camera_id=camera_id,
            location_id=location_id,
            entry_time=timestamp,
        )
        logger.info(
            "Ghost tracking started for %s at %s (entry: %s)",
            person_uid, camera_id, timestamp.isoformat(),
        )

    def set_config(self, config: dict) -> None:
        """Update thresholds from runtime config (called per-pipeline-frame)."""
        self._check_interval = config.get("ghost_check_interval_sec", self._check_interval)
        self._high_alert_sec = config.get("ghost_high_alert_sec", self._high_alert_sec)
        self._medium_alert_sec = config.get("ghost_medium_alert_sec", self._medium_alert_sec)

    async def check_unaccounted(self) -> list[GhostAlert]:
        """Check all tracked entries that haven't been resolved.

        Returns:
            List of GhostAlerts that have crossed their threshold.
        """
        alerts: list[GhostAlert] = []
        now = datetime.now(timezone.utc)

        for entry in list(self._entries.values()):
            if entry.resolved:
                continue

            elapsed = (now - entry.entry_time).total_seconds()

            # HIGH alert at high_alert_sec (default 30 min)
            if elapsed >= self._high_alert_sec and not entry.high_alert_sent:
                entry.high_alert_sent = True
                alerts.append(GhostAlert(
                    person_uid=entry.person_uid,
                    camera_id=entry.camera_id,
                    timestamp=now,
                    alert_level="HIGH",
                    message=(
                        f"Person {entry.person_uid} entered at "
                        f"{entry.camera_id} but has not been seen "
                        f"leaving for 30+ minutes"
                    ),
                ))
                logger.info("HIGH ghost alert for %s", entry.person_uid)

            # MEDIUM alert at medium_alert_sec (default 10 min)
            elif elapsed >= self._medium_alert_sec and not entry.medium_alert_sent:
                entry.medium_alert_sent = True
                alerts.append(GhostAlert(
                    person_uid=entry.person_uid,
                    camera_id=entry.camera_id,
                    timestamp=now,
                    alert_level="MEDIUM",
                    message=(
                        f"Person {entry.person_uid} entered at "
                        f"{entry.camera_id} but has not been seen "
                        f"leaving for 10+ minutes"
                    ),
                ))
                logger.info("MEDIUM ghost alert for %s", entry.person_uid)

        return alerts

    async def cancel_ghost(self, person_uid: str) -> bool:
        """Cancel ghost tracking for a person (seen leaving or dismissed).

        Args:
            person_uid: Person identifier.

        Returns:
            True if person was being tracked.
        """
        entry = self._entries.get(person_uid)
        if entry:
            entry.resolved = True
            logger.info("Ghost tracking cancelled for %s", person_uid)
            # Remove from tracking
            del self._entries[person_uid]
            return True
        return False

    async def record_exit(self, person_uid: str, camera_id: str,
                           timestamp: datetime) -> None:
        """Record a person exit to cancel ghost tracking.

        Args:
            person_uid: Person identifier.
            camera_id: Camera where exit was observed.
            timestamp: When the exit was observed.
        """
        logger.info(
            "Exit recorded for %s at %s (%s)",
            person_uid, camera_id, timestamp.isoformat(),
        )
        await self.cancel_ghost(person_uid)

    async def start_periodic_check(self) -> None:
        """Start periodic ghost checks (runs indefinitely)."""
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                alerts = await self.check_unaccounted()
                if alerts:
                    for alert in alerts:
                        logger.warning(
                            "Ghost alert: [%s] %s", alert.alert_level, alert.message
                        )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Ghost periodic check failed: %s", exc, exc_info=True)

    @property
    def tracked_count(self) -> int:
        """Get number of currently tracked entries."""
        return len(self._entries)

    @property
    def active_entries(self) -> list[_GhostEntry]:
        """Get list of unresolved entries."""
        return [e for e in self._entries.values() if not e.resolved]
