"""Multi-Location Management Module for Vision OS.

Handles user locations, tier enforcement, camera topology validation,
and cross-location boundary enforcement for Re-ID.
"""

from dataclasses import dataclass, field
from datetime import date, time, datetime
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class LocationSummary:
    """Summary view of a location with aggregate stats."""
    id: str
    name: str
    address: Optional[str]
    timezone: str
    camera_count: int = 0
    online_cameras: int = 0
    events_today: int = 0
    high_threats_today: int = 0


@dataclass
class LocationDetail:
    """Full location details including cameras and topology."""
    id: str
    user_id: str
    name: str
    address: Optional[str]
    timezone: str
    created_at: datetime
    business_hours_open: Optional[time] = None
    business_hours_close: Optional[time] = None
    camera_topology: dict = field(default_factory=dict)
    cameras: list = field(default_factory=list)


# Tier limits: free=1, household=3, business=5
TIER_LOCATION_LIMITS = {
    "free": 1,
    "household": 3,
    "business": 5,
}


class LocationManager:
    """Manage user locations and enforce location boundaries.

    Key rules:
    - Cross-camera Re-ID NEVER crosses location boundary (HARD RULE)
    - Digest generated per location, aggregated for user
    - Tier limits enforced on create
    """

    def __init__(self, db_session_factory):
        """Initialize location manager.

        Args:
            db_session_factory: SQLAlchemy async session factory
        """
        self._session_factory = db_session_factory

    async def get_locations(self, user_id: str) -> list[LocationSummary]:
        """Get all locations for a user with summary stats.

        Args:
            user_id: The user's UUID

        Returns:
            List of LocationSummary with camera counts and event stats
        """
        async with self._session_factory() as session:
            # Query locations for user
            result = await session.execute(
                "SELECT id, name, address, timezone FROM locations "
                "WHERE user_id = :user_id ORDER BY created_at",
                {"user_id": user_id}
            )
            rows = result.fetchall()

            summaries = []
            for row in rows:
                # Get camera count for this location
                cam_result = await session.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online "
                    "FROM cameras WHERE location_id = :location_id",
                    {"location_id": row.id}
                )
                cam_stats = cam_result.fetchone()

                # Get events today for this location
                event_result = await session.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN threat_level IN ('HIGH', 'EMERGENCY') THEN 1 ELSE 0 END) as high "
                    "FROM events e "
                    "JOIN cameras c ON e.camera_id = c.id "
                    "WHERE c.location_id = :location_id "
                    "AND e.timestamp >= CURRENT_DATE",
                    {"location_id": row.id}
                )
                event_stats = event_result.fetchone()

                summaries.append(LocationSummary(
                    id=str(row.id),
                    name=row.name,
                    address=row.address,
                    timezone=row.timezone,
                    camera_count=cam_stats.total if cam_stats else 0,
                    online_cameras=cam_stats.online if cam_stats else 0,
                    events_today=event_stats.total if event_stats else 0,
                    high_threats_today=event_stats.high if event_stats else 0,
                ))

            return summaries

    async def get_location(self, location_id: str, user_id: str) -> LocationDetail:
        """Get full location details including cameras.

        Args:
            location_id: Location UUID
            user_id: The user's UUID (for ownership verification)

        Returns:
            LocationDetail with cameras list

        Raises:
            ValueError: If location not found or not owned by user
        """
        async with self._session_factory() as session:
            result = await session.execute(
                "SELECT * FROM locations WHERE id = :id AND user_id = :user_id",
                {"id": location_id, "user_id": user_id}
            )
            row = result.fetchone()

            if not row:
                raise ValueError(f"Location {location_id} not found or access denied")

            # Get cameras for this location
            cam_result = await session.execute(
                "SELECT id, name, status, mode FROM cameras "
                "WHERE location_id = :location_id",
                {"location_id": location_id}
            )
            cameras = [dict(c) for c in cam_result.fetchall()]

            return LocationDetail(
                id=str(row.id),
                user_id=str(row.user_id),
                name=row.name,
                address=row.address,
                timezone=row.timezone,
                business_hours_open=row.business_hours_open,
                business_hours_close=row.business_hours_close,
                camera_topology=row.camera_topology or {},
                cameras=cameras,
                created_at=row.created_at,
            )

    async def create_location(
        self,
        user_id: str,
        name: str,
        address: Optional[str] = None,
        timezone: str = "Asia/Dhaka",
    ) -> LocationDetail:
        """Create a new location.

        Checks tier limit before creating.

        Args:
            user_id: The user's UUID
            name: Location name
            address: Optional address
            timezone: Timezone string (default: Asia/Dhaka)

        Returns:
            Created LocationDetail

        Raises:
            ValueError: If tier limit exceeded
        """
        # Get user's tier
        async with self._session_factory() as session:
            user_result = await session.execute(
                "SELECT tier FROM users WHERE id = :user_id",
                {"user_id": user_id}
            )
            user = user_result.fetchone()
            tier = user.tier if user else "free"

            # Check current location count
            count_result = await session.execute(
                "SELECT COUNT(*) FROM locations WHERE user_id = :user_id",
                {"user_id": user_id}
            )
            current_count = count_result.fetchone()[0]

            limit = self._get_tier_location_limit(tier)
            if current_count >= limit:
                raise ValueError(
                    f"Tier '{tier}' limit of {limit} location(s) reached. "
                    f"Upgrade to add more locations."
                )

            # Create location
            result = await session.execute(
                "INSERT INTO locations (user_id, name, address, timezone) "
                "VALUES (:user_id, :name, :address, :timezone) "
                "RETURNING *",
                {
                    "user_id": user_id,
                    "name": name,
                    "address": address,
                    "timezone": timezone,
                }
            )
            await session.commit()
            row = result.fetchone()

            return LocationDetail(
                id=str(row.id),
                user_id=str(row.user_id),
                name=row.name,
                address=row.address,
                timezone=row.timezone,
                business_hours_open=row.business_hours_open,
                business_hours_close=row.business_hours_close,
                camera_topology=row.camera_topology or {},
                cameras=[],
                created_at=row.created_at,
            )

    async def update_location(
        self,
        location_id: str,
        user_id: str,
        updates: dict,
    ) -> LocationDetail:
        """Update location properties.

        Args:
            location_id: Location UUID
            user_id: The user's UUID (for ownership verification)
            updates: Dict with fields to update (name, address, timezone, etc.)

        Returns:
            Updated LocationDetail

        Raises:
            ValueError: If location not found or not owned by user
        """
        allowed_fields = {"name", "address", "timezone",
                          "business_hours_open", "business_hours_close"}

        # Filter to allowed fields only
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not safe_updates:
            raise ValueError("No valid fields to update")

        set_clause = ", ".join(f"{k} = :{k}" for k in safe_updates)
        safe_updates["id"] = location_id
        safe_updates["user_id"] = user_id

        async with self._session_factory() as session:
            result = await session.execute(
                f"UPDATE locations SET {set_clause} "
                "WHERE id = :id AND user_id = :user_id "
                "RETURNING *",
                safe_updates
            )
            await session.commit()
            row = result.fetchone()

            if not row:
                raise ValueError(f"Location {location_id} not found or access denied")

            # Get cameras
            cam_result = await session.execute(
                "SELECT id, name, status, mode FROM cameras "
                "WHERE location_id = :location_id",
                {"location_id": location_id}
            )
            cameras = [dict(c) for c in cam_result.fetchall()]

            return LocationDetail(
                id=str(row.id),
                user_id=str(row.user_id),
                name=row.name,
                address=row.address,
                timezone=row.timezone,
                business_hours_open=row.business_hours_open,
                business_hours_close=row.business_hours_close,
                camera_topology=row.camera_topology or {},
                cameras=cameras,
                created_at=row.created_at,
            )

    async def delete_location(self, location_id: str, user_id: str) -> bool:
        """Delete a location and all associated data.

        Cascades: cameras, events, persons, analytics

        Args:
            location_id: Location UUID
            user_id: The user's UUID (for ownership verification)

        Returns:
            True if deleted

        Raises:
            ValueError: If location not found or not owned by user
        """
        async with self._session_factory() as session:
            # Verify ownership
            check = await session.execute(
                "SELECT id FROM locations WHERE id = :id AND user_id = :user_id",
                {"id": location_id, "user_id": user_id}
            )
            if not check.fetchone():
                raise ValueError(f"Location {location_id} not found or access denied")

            # Delete in order: events → persons → cameras → location
            await session.execute(
                "DELETE FROM events WHERE camera_id IN "
                "(SELECT id FROM cameras WHERE location_id = :location_id)",
                {"location_id": location_id}
            )
            await session.execute(
                "DELETE FROM person_sightings WHERE camera_id IN "
                "(SELECT id FROM cameras WHERE location_id = :location_id)",
                {"location_id": location_id}
            )
            await session.execute(
                "DELETE FROM cameras WHERE location_id = :location_id",
                {"location_id": location_id}
            )
            await session.execute(
                "DELETE FROM analytics WHERE location_id = :location_id",
                {"location_id": location_id}
            )
            await session.execute(
                "DELETE FROM locations WHERE id = :id",
                {"id": location_id}
            )
            await session.commit()

            return True

    async def get_location_limit(self, tier: str) -> int:
        """Get max locations for a tier.

        Args:
            tier: User tier (free/household/business)

        Returns:
            Max number of locations allowed
        """
        return self._get_tier_location_limit(tier)

    async def get_camera_topology(self, location_id: str) -> dict:
        """Get camera neighbour topology for a location.

        Args:
            location_id: Location UUID

        Returns:
            {camera_id: {neighbours: [...], min_transit_time: int}}
        """
        async with self._session_factory() as session:
            result = await session.execute(
                "SELECT camera_topology FROM locations WHERE id = :id",
                {"id": location_id}
            )
            row = result.fetchone()
            return row.camera_topology if row else {}

    async def update_camera_topology(
        self,
        location_id: str,
        topology: dict,
    ) -> None:
        """Update camera neighbour topology.

        Validates no cycles before saving.

        Args:
            location_id: Location UUID
            topology: Camera topology dict

        Raises:
            ValueError: If topology contains cycles
        """
        if not self._validate_topology(topology):
            raise ValueError(
                "Camera topology contains cycles. "
                "Please ensure the camera graph is acyclic."
            )

        async with self._session_factory() as session:
            await session.execute(
                "UPDATE locations SET camera_topology = :topology WHERE id = :id",
                {"id": location_id, "topology": json.dumps(topology)}
            )
            await session.commit()

    async def get_unified_digest(self, user_id: str, digest_date: date) -> str:
        """Generate a unified digest across all user locations.

        Aggregates per-location digests into one summary.

        Args:
            user_id: The user's UUID
            digest_date: Date for the digest

        Returns:
            Plain text digest
        """
        locations = await self.get_locations(user_id)

        if not locations:
            return (
                f"Vision OS Daily Digest — {digest_date.isoformat()}\n"
                f"{'=' * 50}\n\n"
                f"No locations configured. "
                f"Connect your first camera to get started.\n"
            )

        parts = [
            f"Vision OS Daily Digest — {digest_date.isoformat()}",
            f"{'=' * 50}",
            f"Total Locations: {len(locations)}",
            f"Total Cameras: {sum(l.camera_count for l in locations)}",
            f"Total Events Today: {sum(l.events_today for l in locations)}",
            f"High Threats Today: {sum(l.high_threats_today for l in locations)}",
            "",
        ]

        for loc in locations:
            parts.extend([
                f"--- {loc.name} ---",
                f"  Cameras: {loc.online_cameras}/{loc.camera_count} online",
                f"  Events: {loc.events_today} (High: {loc.high_threats_today})",
                "",
            ])

        return "\n".join(parts)

    def _validate_topology(self, topology: dict) -> bool:
        """Validate camera topology has no cycles.

        Uses DFS cycle detection.

        Args:
            topology: Camera topology dict

        Returns:
            True if valid (no cycles)
        """
        if not topology:
            return True

        visited = set()
        rec_stack = set()

        def dfs(camera_id: str) -> bool:
            """DFS cycle detection. Returns True if cycle found."""
            visited.add(camera_id)
            rec_stack.add(camera_id)

            neighbours = topology.get(camera_id, {}).get("neighbours", [])
            for neighbour in neighbours:
                if neighbour not in visited:
                    if dfs(neighbour):
                        return True
                elif neighbour in rec_stack:
                    return True

            rec_stack.discard(camera_id)
            return False

        for camera_id in topology:
            if camera_id not in visited:
                if dfs(camera_id):
                    return False

        return True

    def _get_tier_location_limit(self, tier: str) -> int:
        """Get location limit by tier.

        Args:
            tier: User tier string

        Returns:
            Max locations for the tier (defaults to 1 for unknown tiers)
        """
        return TIER_LOCATION_LIMITS.get(tier, 1)

    async def get_location_stats(
        self,
        location_id: str,
        stats_date: date,
    ) -> dict:
        """Get aggregate stats for a location on a given date.

        Args:
            location_id: Location UUID
            stats_date: Date to get stats for

        Returns:
            {events: int, high_threats: int, persons_seen: int,
             audio_events: int, alerts_sent: int}
        """
        async with self._session_factory() as session:
            result = await session.execute(
                """
                SELECT
                    COUNT(*) as events,
                    SUM(CASE WHEN threat_level IN ('HIGH', 'EMERGENCY')
                        THEN 1 ELSE 0 END) as high_threats,
                    COUNT(DISTINCT person_id) as persons_seen,
                    SUM(CASE WHEN has_audio THEN 1 ELSE 0 END) as audio_events,
                    SUM(CASE WHEN alert_sent THEN 1 ELSE 0 END) as alerts_sent
                FROM events e
                JOIN cameras c ON e.camera_id = c.id
                WHERE c.location_id = :location_id
                AND DATE(e.timestamp) = :stats_date
                """,
                {"location_id": location_id, "stats_date": stats_date}
            )
            row = result.fetchone()

            return {
                "events": row.events or 0,
                "high_threats": row.high_threats or 0,
                "persons_seen": row.persons_seen or 0,
                "audio_events": row.audio_events or 0,
                "alerts_sent": row.alerts_sent or 0,
            }
