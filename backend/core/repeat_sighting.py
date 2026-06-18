"""
repeat_sighting.py — Track repeat sightings and escalate threat level.

Escalation:
- 1st: LOG only (\"none\")
- 2nd: LOW alert
- 3rd: MEDIUM + \"seen X times today\"
- 4th: HIGH + emergency voice note
- 5th+: HIGH every time

Night hours (10pm-6am) escalate faster.
Reset after 6 hours no sighting (except night/after-hours).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Reset timeout: 6 hours of no sighting
RESET_TIMEOUT_HOURS = 6

# Night hours definition
NIGHT_START_HOUR = 22  # 10 PM
NIGHT_END_HOUR = 6     # 6 AM


@dataclass
class SightingRecord:
    person_uid: str
    user_id: str
    count_today: int = 0
    first_seen_today: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    escalation_level: str = "none"  # none/low/medium/high


class RepeatSightingTracker:
    """Track repeat sightings and escalate threat level."""

    def __init__(self):
        """Initialize tracker with in-memory state."""
        self._records: dict[str, SightingRecord] = {}  # key: f"{person_uid}:{user_id}"

    def _key(self, person_uid: str, user_id: str) -> str:
        return f"{person_uid}:{user_id}"

    async def record_sighting(self, person_uid: str, user_id: str,
                               timestamp: datetime, is_night: bool = False) -> str:
        """Record a sighting and return escalation level.

        Args:
            person_uid: Person identifier.
            user_id: User identifier.
            timestamp: When the sighting occurred.
            is_night: Whether it's currently night hours.

        Returns:
            Escalation level string (none/low/medium/high).
        """
        key = self._key(person_uid, user_id)
        record = self._records.get(key)

        if record is None:
            # First sighting ever
            record = SightingRecord(
                person_uid=person_uid,
                user_id=user_id,
                count_today=1,
                first_seen_today=timestamp,
                last_seen=timestamp,
            )
            self._records[key] = record
            logger.info("First sighting for %s (user=%s)", person_uid, user_id)
            return "none"

        # Check if we should reset
        should_reset = await self.should_reset(person_uid, user_id, record.last_seen, is_night)
        if should_reset:
            record.count_today = 1
            record.first_seen_today = timestamp
            record.last_seen = timestamp
            record.escalation_level = "none"
            logger.info("Sighting reset for %s", person_uid)
            return "none"

        # Update record
        record.count_today += 1
        record.last_seen = timestamp

        # Determine escalation level
        level = await self.get_escalation_level(record.count_today, is_night)
        record.escalation_level = level

        logger.info(
            "Repeat sighting for %s: count=%d, level=%s",
            person_uid, record.count_today, level,
        )
        return level

    async def get_today_count(self, person_uid: str, user_id: str) -> int:
        """Get number of sightings today for a person.

        Args:
            person_uid: Person identifier.
            user_id: User identifier.

        Returns:
            Sighting count for today.
        """
        record = self._records.get(self._key(person_uid, user_id))
        if record is None:
            return 0
        return record.count_today

    async def get_escalation_level(self, count: int, is_night: bool) -> str:
        """Get escalation level based on sighting count.

        Night hours (10pm-6am) escalate faster:
        - 1st: LOG (none)
        - 2nd: MEDIUM (instead of LOW)
        - 3rd: HIGH (instead of MEDIUM)
        - 4th+: HIGH

        Daytime escalation:
        - 1st: LOG (none)
        - 2nd: LOW
        - 3rd: MEDIUM
        - 4th: HIGH
        - 5th+: HIGH

        Args:
            count: Sighting count.
            is_night: Whether it's night hours.

        Returns:
            Escalation level string.
        """
        if is_night:
            if count <= 1:
                return "none"
            if count == 2:
                return "medium"  # Faster escalation at night
            if count >= 3:
                return "high"
        else:
            if count <= 1:
                return "none"
            if count == 2:
                return "low"
            if count == 3:
                return "medium"
            if count >= 4:
                return "high"

        return "none"

    async def should_reset(self, person_uid: str, user_id: str,
                            last_seen: Optional[datetime],
                            is_night: bool) -> bool:
        """Check if sighting count should reset.

        Reset conditions:
        - 6 hours no sighting → reset
        - Night hours NEVER reset
        - After hours at business NEVER reset

        Args:
            person_uid: Person identifier.
            user_id: User identifier.
            last_seen: Last sighting timestamp.
            is_night: Whether it's currently night hours.

        Returns:
            True if the count should reset.
        """
        # Night hours never reset
        if is_night:
            return False

        if last_seen is None:
            return False

        # Check if 6 hours have passed since last sighting
        now = datetime.now(timezone.utc)
        elapsed = (now - last_seen).total_seconds()
        return elapsed >= RESET_TIMEOUT_HOURS * 3600

    def is_night_hours(self, timestamp: Optional[datetime] = None) -> bool:
        """Check if the given time falls within night hours (10pm-6am).

        Args:
            timestamp: Time to check (defaults to now).

        Returns:
            True if within night hours.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        hour = timestamp.hour
        return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR

    @property
    def total_tracked(self) -> int:
        """Get number of unique person-user pairs tracked."""
        return len(self._records)
