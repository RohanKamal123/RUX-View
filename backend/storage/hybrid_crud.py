"""
hybrid_crud.py — Unified CRUD Layer for Vision OS (PostgreSQL Only).

Provides a consistent interface wrapping PostgreSQL (Layer 2).
MEGA.nz (Layer 1) has been removed entirely.

Architecture:
  Layer 1 (MEGA.nz): REMOVED
  Layer 2 (Neon PG): Structured data, events, cameras, users

Usage:
    from backend.storage.hybrid_crud import HybridCRUD

    crud = HybridCRUD(pg_crud=pg_crud)
    event = await crud.create_event(user_id="...", camera_id="...", ...)
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from backend.storage.database import Event as EventModel
from backend.storage.engine import create_session

logger = logging.getLogger(__name__)


# ===========================================================================
# Unified Data Models
# ===========================================================================

@dataclass
class User:
    """User profile data model."""
    user_id: str
    email: str
    name: str = ""
    tier: str = "free"
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True
    telegram_chat_id: Optional[str] = None


@dataclass
class Camera:
    """Camera device data model."""
    camera_id: str
    user_id: str
    name: str = ""
    rtsp_url: str = ""
    mode: str = "indoor"
    is_active: bool = True
    created_at: str = ""
    last_seen_at: str = ""
    connection_type: str = "rtsp"
    p2p_serial: str = ""
    p2p_username: str = ""
    rtmp_stream_key: str = ""


@dataclass
class Event:
    """Security event data model."""
    event_id: str
    user_id: str
    camera_id: str
    event_type: str = "motion"
    confidence: float = 0.0
    details: dict = field(default_factory=dict)
    thumbnail_url: str = ""
    threat_level: str = "LOW"
    timestamp_start: str = ""
    timestamp_end: Optional[str] = None
    camera_name: str = ""
    alert_message: str = ""
    duration_sec: int = 0
    person_ids: list = field(default_factory=list)
    created_at: str = ""


@dataclass
class QuotaInfo:
    """Camera quota information."""
    total_cameras: int = 0
    max_cameras: int = 20
    remaining: int = 20
    usage_percentage: float = 0.0
    tier: str = "free"


# ===========================================================================
# HybridCRUD — PostgreSQL only (MEGA.nz removed)
# ===========================================================================

class HybridCRUD:
    """Unified CRUD using PostgreSQL only.

    MEGA.nz has been removed entirely.
    Provides a consistent interface for all API routes.
    """

    def __init__(self, pg_crud=None):
        """Initialize the hybrid CRUD.

        Args:
            pg_crud: Optional PostgresCRUD instance (Layer 2).
        """
        self._pg = pg_crud
        self._pg_available = pg_crud is not None

    # ── Users ──────────────────────────────────────────────────────────────

    async def get_or_create_user(self, user_id: str, email: str = "",
                                  name: str = "") -> User:
        """Get a user, creating if not found.

        Args:
            user_id: Unique user identifier.
            email: User's email address.
            name: Display name.

        Returns:
            User dataclass.
        """
        if self._pg_available:
            try:
                pg_user = await self._pg.get_user(user_id)
                if pg_user:
                    return User(
                        user_id=pg_user.id,
                        email=pg_user.email or email,
                        name=name,
                        tier=pg_user.tier or "free",
                        created_at=str(pg_user.created_at) if pg_user.created_at else "",
                        updated_at=str(pg_user.created_at) if pg_user.created_at else "",
                        is_active=True,
                        telegram_chat_id=pg_user.telegram_chat_id,
                    )
                # Auto-create
                pg_user = await self._pg.upsert_user(
                    user_id=user_id,
                    email=email or f"{user_id}@visionos.local",
                    tier="free",
                    subscription_active=False,
                )
                return User(
                    user_id=pg_user.id,
                    email=pg_user.email or email,
                    name=name,
                    tier=pg_user.tier or "free",
                    created_at=str(pg_user.created_at) if pg_user.created_at else "",
                    updated_at=str(pg_user.created_at) if pg_user.created_at else "",
                    is_active=True,
                    telegram_chat_id=pg_user.telegram_chat_id,
                )
            except Exception as e:
                logger.error("PG user lookup failed: %s", e)

        # Last resort: return a minimal user
        return User(
            user_id=user_id,
            email=email,
            name=name,
            tier="free",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            is_active=True,
        )

    async def update_user(self, user_id: str, updates: dict) -> User:
        """Update a user's profile."""
        if self._pg_available:
            try:
                pg_user = await self._pg.upsert_user(
                    user_id=user_id,
                    email=updates.get("email"),
                    tier=updates.get("tier", "free"),
                    telegram_chat_id=updates.get("telegram_chat_id"),
                )
                return User(
                    user_id=pg_user.id,
                    email=pg_user.email or "",
                    name=updates.get("name", ""),
                    tier=pg_user.tier or "free",
                    created_at=str(pg_user.created_at) if pg_user.created_at else "",
                    updated_at=str(pg_user.created_at) if pg_user.created_at else "",
                    is_active=True,
                    telegram_chat_id=pg_user.telegram_chat_id,
                )
            except Exception as e:
                logger.error("PG user update failed: %s", e)

        return User(user_id=user_id, email="", name="", tier="free")

    # ── Cameras ────────────────────────────────────────────────────────────

    async def create_camera(self, user_id: str, name: str,
                             rtsp_url: str = "", mode: str = "indoor",
                             connection_type: str = "rtsp",
                             p2p_serial: str = "", p2p_username: str = "",
                             p2p_password: str = "") -> Camera:
        """Create a new camera.

        connection_type is "rtsp" (rtsp_url used directly) or "dahua_p2p"
        (p2p_serial/p2p_username/p2p_password used instead -- same auth
        model as the DMSS app, see backend/core/p2p/dahua_client.py).
        p2p_password is encrypted here before it ever reaches storage --
        callers (the API layer) must pass plaintext, this is the one
        place it gets encrypted.
        """
        if self._pg_available:
            try:
                import uuid
                from backend.core.crypto import encrypt_secret

                camera_id = f"CAM_{uuid.uuid4().hex[:12].upper()}"
                now = datetime.utcnow().isoformat()
                p2p_password_encrypted = encrypt_secret(p2p_password) if p2p_password else None
                # RTMP push cameras get a server-generated stream key --
                # never user-supplied, since it doubles as the ingest
                # server's auth (backend/core/ingest/rtmp_ingest.py): a
                # push is only accepted if the key matches a known camera.
                rtmp_stream_key = (
                    f"{camera_id}_{uuid.uuid4().hex[:16]}"
                    if connection_type == "rtmp_push" else None
                )
                pg_cam = await self._pg.upsert_camera(
                    camera_id=camera_id,
                    user_id=user_id,
                    location_id="default",
                    name=name,
                    mode=mode,
                    enabled=True,
                    connection_type=connection_type,
                    rtsp_url=rtsp_url or None,
                    p2p_serial=p2p_serial or None,
                    p2p_username=p2p_username or None,
                    p2p_password_encrypted=p2p_password_encrypted,
                    rtmp_stream_key=rtmp_stream_key,
                )
                return Camera(
                    camera_id=pg_cam.id,
                    user_id=pg_cam.user_id,
                    name=pg_cam.name or name,
                    rtsp_url=pg_cam.rtsp_url or "",
                    mode=pg_cam.mode or mode,
                    is_active=pg_cam.enabled,
                    created_at=str(pg_cam.created_at) if pg_cam.created_at else now,
                    last_seen_at=str(pg_cam.created_at) if pg_cam.created_at else now,
                    connection_type=pg_cam.connection_type or "rtsp",
                    p2p_serial=pg_cam.p2p_serial or "",
                    p2p_username=pg_cam.p2p_username or "",
                    rtmp_stream_key=pg_cam.rtmp_stream_key or "",
                )
            except Exception as e:
                logger.error("PG camera create failed: %s", e)
                raise RuntimeError(f"No storage backend available: {e}") from e

        raise RuntimeError("No storage backend available")

    @staticmethod
    def _map_pg_camera(c) -> Camera:
        return Camera(
            camera_id=c.id,
            user_id=c.user_id,
            name=c.name or "",
            rtsp_url=c.rtsp_url or "",
            mode=c.mode or "indoor",
            is_active=c.enabled,
            created_at=str(c.created_at) if c.created_at else "",
            last_seen_at=str(c.created_at) if c.created_at else "",
            connection_type=c.connection_type or "rtsp",
            p2p_serial=c.p2p_serial or "",
            p2p_username=c.p2p_username or "",
            rtmp_stream_key=c.rtmp_stream_key or "",
        )

    async def get_user_cameras(self, user_id: str) -> list[Camera]:
        """Get all cameras for a user."""
        if self._pg_available:
            try:
                pg_cameras = await self._pg.get_user_cameras(user_id)
                return [self._map_pg_camera(c) for c in pg_cameras]
            except Exception as e:
                logger.error("PG camera list failed: %s", e)

        return []

    async def update_camera(self, camera_id: str, user_id: str, updates: dict) -> Camera:
        """Update a camera's name/mode/enabled fields.

        Ownership is enforced by the caller (backend/api/cameras.py checks
        the camera is in the user's own list before calling this) -- this
        just delegates to upsert_camera's existing-row update path.
        """
        if self._pg_available:
            try:
                if "enabled" not in updates:
                    # upsert_camera's update path always overwrites `enabled`
                    # (unlike name/mode, it has no "or existing value"
                    # fallback) -- look the current value up first so a
                    # name-only update doesn't silently re-enable a
                    # disabled camera.
                    current = await self.get_user_cameras(user_id)
                    existing = next((c for c in current if c.camera_id == camera_id), None)
                    updates = {**updates, "enabled": existing.is_active if existing else True}
                pg_cam = await self._pg.upsert_camera(
                    camera_id=camera_id,
                    user_id=user_id,
                    location_id="default",
                    name=updates.get("name"),
                    mode=updates.get("mode"),
                    enabled=updates.get("enabled", True),
                    connection_type=updates.get("connection_type"),
                    rtsp_url=updates.get("rtsp_url"),
                )
                return self._map_pg_camera(pg_cam)
            except Exception as e:
                logger.error("PG camera update failed: %s", e)
                raise RuntimeError(f"No storage backend available: {e}") from e

        raise RuntimeError("No storage backend available")

    async def delete_camera(self, camera_id: str, user_id: str) -> bool:
        """Delete a camera owned by user_id. Returns False if not found/not owned."""
        if self._pg_available:
            try:
                return await self._pg.delete_camera(camera_id, user_id)
            except Exception as e:
                logger.error("PG camera delete failed: %s", e)
                raise RuntimeError(f"No storage backend available: {e}") from e

        raise RuntimeError("No storage backend available")

    async def get_cameras_by_connection_type(self, connection_type: str) -> list[Camera]:
        """Get all enabled cameras across all users with a given
        connection_type -- used by backend/core/ingest/rtmp_poller.py's
        periodic rtmp_push sampler, which has no request-scoped user_id."""
        if self._pg_available:
            try:
                pg_cameras = await self._pg.get_cameras_by_connection_type(connection_type)
                return [self._map_pg_camera(c) for c in pg_cameras]
            except Exception as e:
                logger.error("PG camera-by-connection-type list failed: %s", e)

        return []

    async def get_camera_quota(self, user_id: str) -> QuotaInfo:
        """Get camera quota — pass cameras list to avoid extra DB call."""
        from backend.core.config_store import get_max_cameras

        cameras = await self.get_user_cameras(user_id)
        total = len(cameras)
        max_cam = await get_max_cameras()
        remaining = max(0, max_cam - total)
        usage_pct = round((total / max_cam) * 100, 1) if max_cam > 0 else 0.0
        return QuotaInfo(
            total_cameras=total,
            max_cameras=max_cam,
            remaining=remaining,
            usage_percentage=usage_pct,
            tier="free",
        )

    # ── Events ─────────────────────────────────────────────────────────────

    async def create_event(self, user_id: str, camera_id: str,
                            event_type: str = "motion",
                            details: dict = None) -> Event:
        """Create a new event."""
        if self._pg_available:
            try:
                import uuid
                event_id = f"EVT_{uuid.uuid4().hex[:12].upper()}"
                now = datetime.utcnow()
                # Store image_base64 from details into gemini_decision for persistence
                gemini_decision = None
                if details and "image_base64" in details:
                    gemini_decision = {"image_base64": details["image_base64"]}
                pg_evt = await self._pg.create_event(
                    user_id=user_id,
                    location_id="default",
                    camera_id=camera_id,
                    incident_id=event_id,
                    timestamp_start=now,
                    threat_level=details.get("threat_level", "LOW") if details else "LOW",
                    gemini_decision=gemini_decision,
                )
                return Event(
                    event_id=event_id,
                    user_id=user_id,
                    camera_id=camera_id,
                    event_type=event_type,
                    confidence=details.get("confidence", 0.0) if details else 0.0,
                    details=details or {},
                    threat_level=details.get("threat_level", "LOW") if details else "LOW",
                    created_at=now.isoformat(),
                )
            except Exception as e:
                logger.error("PG event create failed: %s", e)
                raise RuntimeError(f"No storage backend available: {e}") from e

        raise RuntimeError("No storage backend available")

    async def get_user_events(self, user_id: str, limit: int = 50) -> list[Event]:
        """Get events for a user."""
        if self._pg_available:
            try:
                pg_events = await self._pg.get_user_events(user_id, limit=limit)
                return [
                    Event(
                        event_id=str(e.id),
                        user_id=e.user_id,
                        camera_id=e.camera_id,
                        event_type=e.incident_id or "motion",
                        confidence=0.0,
                        threat_level=e.threat_level or "LOW",
                        thumbnail_url=e.thumbnail_url or f"/api/triggers/image/{e.incident_id}",
                        alert_message=(e.gemini_decision or {}).get("alert_message", ""),
                        camera_name=e.camera_id,
                        timestamp_start=str(e.timestamp_start) if e.timestamp_start else "",
                        timestamp_end=str(e.timestamp_end) if getattr(e, "timestamp_end", None) else None,
                        duration_sec=int(e.duration_sec or 0),
                        person_ids=(e.gemini_decision or {}).get("person_ids", []),
                        details={
                            "image_base64": (e.gemini_decision or {}).get("image_base64", ""),
                            "frame_count": (e.gemini_decision or {}).get("frame_count", 0),
                        },
                        created_at=str(e.timestamp_start) if e.timestamp_start else "",
                    ) for e in pg_events
                ]
            except Exception as e:
                logger.error("PG events list failed: %s", e)

        return []

    async def get_event_by_id(self, event_id: str, user_id: str) -> Optional[Event]:
        """Get a single event by its event_id (incident_id) and user_id.

        Supports both EVT_ format (e.g. "EVT_ABC123") and legacy numeric IDs
        (e.g. "954", "955") by falling back to a primary-key lookup if the
        incident_id lookup returns nothing.
        """
        if self._pg_available:
            try:
                # First try: lookup by incident_id (EVT_ format)
                pg_event = await self._pg.get_event_by_incident_id(event_id, user_id)
                if pg_event is None:
                    # Second try: if event_id looks numeric, try lookup by primary key
                    if event_id.isdigit():
                        try:
                            pg_event = await self._pg.get_event(int(event_id))
                        except Exception:
                            pass
                if pg_event is None:
                    return None
                return Event(
                    event_id=str(pg_event.id),
                    user_id=pg_event.user_id,
                    camera_id=pg_event.camera_id,
                    event_type=pg_event.incident_id or "motion",
                    confidence=0.0,
                    threat_level=pg_event.threat_level or "LOW",
                    thumbnail_url=pg_event.thumbnail_url or f"/api/triggers/image/{pg_event.incident_id}",
                    alert_message=(pg_event.gemini_decision or {}).get("alert_message", ""),
                    camera_name=pg_event.camera_id,
                    timestamp_start=str(pg_event.timestamp_start) if pg_event.timestamp_start else "",
                    timestamp_end=str(pg_event.timestamp_end) if getattr(pg_event, "timestamp_end", None) else None,
                    duration_sec=int(pg_event.duration_sec or 0),
                    person_ids=(pg_event.gemini_decision or {}).get("person_ids", []),
                    details={
                        "image_base64": pg_event.gemini_decision.get("image_base64", "") if pg_event.gemini_decision else "",
                        "frame_count": pg_event.gemini_decision.get("frame_count", 0) if pg_event.gemini_decision else 0,
                    },
                    created_at=str(pg_event.timestamp_start) if pg_event.timestamp_start else "",
                )
            except Exception as e:
                logger.error("PG get_event_by_id failed: %s", e)
        return None

    async def update_event(
        self,
        event_id: str,
        threat_level: Optional[str] = None,
        alert_message: Optional[str] = None,
        person_ids: Optional[list] = None,
        timestamp_end: Optional["datetime"] = None,
        duration_sec: Optional[float] = None,
        frame_count: Optional[int] = None,
    ) -> bool:
        """Update an event's pipeline results.

        Stores alert_message and person_ids inside the gemini_decision JSON column
        so they can be read back by get_user_events() and the dashboard.

        `timestamp_end` and `duration_sec` are written directly to the Event row
        and are used by the session-cleanup loop in triggers.py to close out
        expired camera sessions.

        Uses a single DB session for both the incident_id lookup and the UPDATE,
        eliminating the previous pattern of two nested `create_session()` calls
        (one in hybrid_crud + one in pg_crud) which opened two separate connections.
        """
        if self._pg_available:
            try:
                async with create_session() as session:
                    # Look up the event by incident_id
                    result = await session.execute(
                        select(EventModel).where(EventModel.incident_id == event_id)
                    )
                    pg_event = result.scalar_one_or_none()
                    if pg_event is None:
                        logger.warning("Event %s not found for update", event_id)
                        return False

                    # Build gemini_decision dict with alert_message, person_ids, and frame_count
                    gemini_decision = dict(pg_event.gemini_decision or {})
                    if alert_message is not None:
                        gemini_decision["alert_message"] = alert_message
                    if person_ids is not None:
                        gemini_decision["person_ids"] = person_ids
                    if frame_count is not None:
                        gemini_decision["frame_count"] = frame_count

                    # Pass our session down so pg_crud.update_event() reuses it
                    # instead of opening its own separate connection.
                    await self._pg.update_event(
                        event_id=pg_event.id,
                        threat_level=threat_level,
                        alert_sent=bool(alert_message) if alert_message else None,
                        gemini_decision=gemini_decision,
                        timestamp_end=timestamp_end,
                        duration_sec=duration_sec,
                        session=session,
                    )
                logger.info(
                    "Updated event %s: threat=%s, alert=%s, persons=%s, frames=%s, end=%s, dur=%s",
                    event_id, threat_level, alert_message, person_ids, frame_count, timestamp_end, duration_sec,
                )
                return True
            except Exception as e:
                logger.error("PG update_event failed: %s", e)
        return False

    async def search_events(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        camera_ids: Optional[list[str]] = None,
        threat_level: Optional[str] = None,
        limit: int = 20,
    ) -> list[Event]:
        """Search events for a user with optional time range / camera / threat filters.

        Backs the query agent's `search_events` tool — all filters are pushed
        down to the database (see PostgresCRUD.get_user_events), not applied
        in Python, so this scales with real data volume.
        """
        if self._pg_available:
            try:
                pg_events = await self._pg.get_user_events(
                    user_id,
                    limit=limit,
                    camera_ids=camera_ids,
                    start_time=start_time,
                    end_time=end_time,
                    threat_level=threat_level,
                )
                return [
                    Event(
                        event_id=str(e.id),
                        user_id=e.user_id,
                        camera_id=e.camera_id,
                        event_type=e.incident_id or "motion",
                        threat_level=e.threat_level or "LOW",
                        thumbnail_url=e.thumbnail_url or f"/api/triggers/image/{e.incident_id}",
                        alert_message=(e.gemini_decision or {}).get("alert_message", ""),
                        camera_name=e.camera_id,
                        timestamp_start=str(e.timestamp_start) if e.timestamp_start else "",
                        timestamp_end=str(e.timestamp_end) if getattr(e, "timestamp_end", None) else None,
                        duration_sec=int(e.duration_sec or 0),
                        person_ids=(e.gemini_decision or {}).get("person_ids", []),
                        created_at=str(e.timestamp_start) if e.timestamp_start else "",
                    ) for e in pg_events
                ]
            except Exception as e:
                logger.error("PG events search failed: %s", e)

        return []

    async def get_events_by_person(
        self, user_id: str, person_uid: str, limit: int = 200,
    ) -> list[Event]:
        """Find events a person_uid appears in (for cross-camera tracking).

        person_ids are stored inside each event's gemini_decision JSON blob
        (there is no populated person_sightings table in the live pipeline
        yet), so this scans the user's recent events and filters in Python.
        `limit` bounds how many recent events are scanned, not how many are
        returned.
        """
        events = await self.get_user_events(user_id, limit=limit)
        return [e for e in events if person_uid in (e.person_ids or [])]

    async def get_camera_events(self, camera_id: str, limit: int = 50) -> list[Event]:
        """Get events for a specific camera."""
        if self._pg_available:
            try:
                pg_events = await self._pg.get_user_events(
                    user_id="", limit=limit, camera_id=camera_id
                )
                return [
                    Event(
                        event_id=str(e.id),
                        user_id=e.user_id,
                        camera_id=e.camera_id,
                        event_type=e.incident_id or "motion",
                        threat_level=e.threat_level or "LOW",
                        thumbnail_url=e.thumbnail_url or f"/api/triggers/image/{e.incident_id}",
                        alert_message=(e.gemini_decision or {}).get("alert_message", ""),
                        camera_name=e.camera_id,
                        timestamp_start=str(e.timestamp_start) if e.timestamp_start else "",
                        timestamp_end=str(e.timestamp_end) if getattr(e, "timestamp_end", None) else None,
                        duration_sec=int(e.duration_sec or 0),
                        person_ids=(e.gemini_decision or {}).get("person_ids", []),
                        details={
                            "image_base64": (e.gemini_decision or {}).get("image_base64", ""),
                            "frame_count": (e.gemini_decision or {}).get("frame_count", 0),
                        },
                        created_at=str(e.timestamp_start) if e.timestamp_start else "",
                    ) for e in pg_events
                ]
            except Exception as e:
                logger.error("PG camera events failed: %s", e)

        return []

    async def count_user_events(self, user_id: str) -> int:
        """Count events for a user."""
        if self._pg_available:
            try:
                return await self._pg.count_user_events(user_id)
            except Exception:
                pass
        return 0

    # ── Payments ───────────────────────────────────────────────────────────

    async def create_payment(
        self,
        user_id: str,
        tier: str,
        amount_bdt: int,
        transaction_id: str,
        payment_method: str = "bkash",
        notes: Optional[str] = None,
    ) -> Any:
        """Record a new payment transaction."""
        if self._pg_available:
            try:
                return await self._pg.create_payment(
                    user_id=user_id,
                    tier=tier,
                    amount_bdt=amount_bdt,
                    transaction_id=transaction_id,
                    payment_method=payment_method,
                    notes=notes,
                )
            except Exception as e:
                logger.error("PG create_payment failed: %s", e)

        raise RuntimeError("No storage backend available")

    async def get_user_payments(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list:
        """Get payment history for a user."""
        if self._pg_available:
            try:
                return await self._pg.get_user_payments(
                    user_id=user_id,
                    limit=limit,
                    offset=offset,
                )
            except Exception as e:
                logger.error("PG get_user_payments failed: %s", e)

        return []

    # ── Health ─────────────────────────────────────────────────────────────

    async def check_health(self) -> dict:
        """Check health of available storage backends."""
        pg_status = "unavailable"

        if self._pg_available:
            try:
                health = await self._pg.check_health()
                pg_status = health.get("status", "error")
            except Exception:
                pg_status = "error"

        return {
            "layer2_postgres": pg_status,
        }