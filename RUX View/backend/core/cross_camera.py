"""
cross_camera.py — Cross-camera correlation, ghost detection, and repeat sightings.

Cross-camera: correlates person sightings across cameras within same location.
NEVER crosses location boundary (HARD RULE enforced in SQL).
Ghost detection: alerts if person entered but not seen leaving (10min/30min).
Repeat sighting: frequency escalation (1st=LOG, 2nd=LOW, 3rd=MEDIUM, 4th+=HIGH).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default topology: min transit time between cameras in seconds
DEFAULT_MIN_TRANSIT = 10  # 10 seconds minimum between cameras


@dataclass
class CrossCameraResult:
    matched: bool
    matched_person_uid: Optional[str] = None
    source_camera_id: Optional[str] = None
    time_gap_seconds: Optional[float] = None
    confidence: float = 0.0
    impossible_timing: bool = False


@dataclass
class GhostCheckResult:
    is_ghost: bool
    alert_level: Optional[str] = None  # MEDIUM / HIGH
    message: Optional[str] = None


class CrossCameraCorrelator:
    """Correlate person sightings across cameras within a location."""

    def __init__(self, db_session_factory=None):
        """Initialize with DB session factory.

        Args:
            db_session_factory: Factory callable that returns an async DB session.
        """
        self._db_factory = db_session_factory

    async def correlate_across_cameras(self, person_uid: str,
                                        source_camera_id: str,
                                        location_id: str,
                                        event_timestamp: datetime,
                                        direction: str = "unknown") -> CrossCameraResult:
        """Check if this person was seen on another camera recently.

        Args:
            person_uid: Person identifier.
            source_camera_id: Camera that just saw this person.
            location_id: Location UUID (HARD boundary).
            event_timestamp: When the sighting occurred.
            direction: Direction person was moving.

        Returns:
            CrossCameraResult with match info.
        """
        try:
            if self._db_factory is None:
                # No DB available — cannot correlate
                return CrossCameraResult(matched=False)

            from backend.storage.crud import get_recent_sightings
            async with self._db_factory() as db:
                # Get recent sightings of this person within the SAME location
                recent = await get_recent_sightings(
                    db=db,
                    person_uid=person_uid,
                    location_id=location_id,
                    since=event_timestamp - timedelta(minutes=30),
                    exclude_camera=source_camera_id,
                )

            if not recent:
                return CrossCameraResult(matched=False)

            # Find the closest matching sighting
            best_match = None
            smallest_gap = float("inf")

            for sighting in recent:
                gap = abs(
                    (sighting["timestamp"] - event_timestamp).total_seconds()
                )
                if gap < smallest_gap:
                    smallest_gap = gap
                    best_match = sighting

            if best_match is None:
                return CrossCameraResult(matched=False)

            # Check for impossible timing (too fast between cameras)
            topology = {}  # Would be loaded from user config
            impossible = self._detect_impossible_timing(
                smallest_gap, source_camera_id, best_match["camera_id"], topology
            )

            return CrossCameraResult(
                matched=True,
                matched_person_uid=person_uid,
                source_camera_id=best_match["camera_id"],
                time_gap_seconds=smallest_gap,
                confidence=1.0 if smallest_gap < 300 else 0.5,
                impossible_timing=impossible,
            )

        except Exception as exc:
            logger.error("Cross-camera correlation failed: %s", exc, exc_info=True)
            return CrossCameraResult(matched=False)

    async def check_ghost_condition(self, person_uid: str,
                                      location_id: str,
                                      entry_camera_id: str,
                                      entry_timestamp: datetime) -> GhostCheckResult:
        """Check if a person who entered has not been seen leaving.

        Args:
            person_uid: Person identifier.
            location_id: Location UUID.
            entry_camera_id: Camera where person was first seen.
            entry_timestamp: When person was first seen.

        Returns:
            GhostCheckResult with alert info.
        """
        try:
            if self._db_factory is None:
                return GhostCheckResult(is_ghost=False)

            from backend.storage.crud import get_recent_sightings

            async with self._db_factory() as db:
                # Check if person was seen on an exit-point camera since entry
                exit_sightings = await get_recent_sightings(
                    db=db,
                    person_uid=person_uid,
                    location_id=location_id,
                    since=entry_timestamp,
                    # Exit-point cameras would be defined in topology
                )

            # If no sightings on other cameras within 30 minutes → possible ghost
            if not exit_sightings:
                elapsed = (datetime.now(timezone.utc) - entry_timestamp).total_seconds()

                if elapsed >= 1800:  # 30 minutes
                    return GhostCheckResult(
                        is_ghost=True,
                        alert_level="HIGH",
                        message=f"Person {person_uid} entered at {entry_camera_id} "
                                f"but has not been seen leaving for 30+ minutes",
                    )
                if elapsed >= 600:  # 10 minutes
                    return GhostCheckResult(
                        is_ghost=True,
                        alert_level="MEDIUM",
                        message=f"Person {person_uid} entered at {entry_camera_id} "
                                f"but has not been seen leaving for 10+ minutes",
                    )

            return GhostCheckResult(is_ghost=False)

        except Exception as exc:
            logger.error("Ghost condition check failed: %s", exc, exc_info=True)
            return GhostCheckResult(is_ghost=False)

    def _get_neighbour_cameras(self, camera_id: str,
                                topology: dict) -> list[str]:
        """Get neighbouring cameras from topology config.

        Args:
            camera_id: Camera ID to find neighbours for.
            topology: Dict mapping camera_id to list of neighbour camera IDs.

        Returns:
            List of neighbouring camera IDs.
        """
        return topology.get("neighbours", {}).get(camera_id, [])

    def _detect_impossible_timing(self, time_gap: float,
                                    cam_a: str, cam_b: str,
                                    topology: dict) -> bool:
        """Detect if a person appearing at cam_b too quickly after cam_a is impossible.

        Uses min_transit_time from topology config.

        Args:
            time_gap: Time gap in seconds between sightings.
            cam_a: First camera ID.
            cam_b: Second camera ID.
            topology: Dict with transit_time config.

        Returns:
            True if the timing is physically impossible.
        """
        # Get minimum transit time for this camera pair
        transit_times = topology.get("transit_times", {})
        pair_key = f"{cam_a}→{cam_b}"
        min_transit = transit_times.get(pair_key, DEFAULT_MIN_TRANSIT)

        # If time gap is less than minimum transit time, it's impossible
        # (unless the cameras cover the same area)
        if time_gap < min_transit and time_gap > 0:
            logger.info(
                "Impossible timing: %s→%s gap=%.1fs < min_transit=%.1fs",
                cam_a, cam_b, time_gap, min_transit,
            )
            return True

        return False
