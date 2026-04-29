"""Local Queue — SQLite-backed offline buffer for triggers.

Provides reliable local storage for trigger events when the
internet connection is unavailable.  Events are automatically
flushed to the backend when connectivity is restored.

Key features:
- SQLite-backed persistence (survives process restarts)
- 48-hour TTL (events older than this are auto-cleaned)
- Max 500 events (oldest dropped when capacity exceeded)
- FIFO ordering (oldest events flushed first)
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = "visionos_queue.db"
DEFAULT_MAX_EVENTS = 500
DEFAULT_TTL_HOURS = 48

# ── Schema ─────────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trigger_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp
    trigger_data TEXT   NOT NULL   -- JSON-encoded trigger payload
);
"""

INSERT_SQL = "INSERT INTO trigger_queue (created_at, trigger_data) VALUES (?, ?);"
SELECT_ALL_SQL = "SELECT id, trigger_data FROM trigger_queue ORDER BY id ASC;"
DELETE_BY_ID_SQL = "DELETE FROM trigger_queue WHERE id = ?;"
COUNT_SQL = "SELECT COUNT(*) FROM trigger_queue;"
DELETE_EXPIRED_SQL = "DELETE FROM trigger_queue WHERE created_at < ?;"
DELETE_OLDEST_SQL = "DELETE FROM trigger_queue WHERE id IN (SELECT id FROM trigger_queue ORDER BY id ASC LIMIT ?);"


class LocalQueue:
    """SQLite-backed offline buffer for triggers.

    Thread-safe: uses a threading.Lock to serialise all SQLite access.

    Usage:
        queue = LocalQueue()
        queue.enqueue({"type": "frame", "camera_id": "cam_001", ...})
        events = queue.dequeue_all()
        queue.close()
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        max_events: int = DEFAULT_MAX_EVENTS,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        """Initialize local queue.

        Args:
            db_path: Path to SQLite database file.
            max_events: Maximum number of events before dropping oldest.
            ttl_hours: Time-to-live in hours for queued events.
        """
        self._db_path = db_path
        self._max_events = max_events
        self._ttl_hours = ttl_hours
        self._lock = threading.Lock()

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(CREATE_TABLE_SQL)
        self._conn.commit()

        logger.info(
            "LocalQueue initialised: path=%s, max=%d, ttl=%dh",
            db_path,
            max_events,
            ttl_hours,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def enqueue(self, trigger_data: dict) -> None:
        """Add a trigger event to the queue.

        If the queue is at capacity, the oldest event is dropped
        to make room for the new one.

        Args:
            trigger_data: Dictionary with trigger payload
                          (e.g. ``{"type": "frame", "jpeg_bytes": ..., ...}``).
        """
        with self._lock:
            # Check capacity and drop oldest if full
            count = self._conn.execute(COUNT_SQL).fetchone()[0]
            if count >= self._max_events:
                overflow = count - self._max_events + 1
                self._conn.execute(DELETE_OLDEST_SQL, (overflow,))
                logger.warning(
                    "Queue at capacity (%d), dropped %d oldest event(s)",
                    self._max_events,
                    overflow,
                )

            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                INSERT_SQL,
                (now, json.dumps(trigger_data)),
            )
            self._conn.commit()

            logger.debug(
                "Event enqueued (queue_size=%d)",
                self._conn.execute(COUNT_SQL).fetchone()[0],
            )

    def dequeue_all(self) -> list[dict]:
        """Get all queued events (oldest first) and remove them from the queue.

        Returns:
            List of trigger data dicts in FIFO order.
        """
        with self._lock:
            rows = self._conn.execute(SELECT_ALL_SQL).fetchall()

            if not rows:
                return []

            events = []
            ids_to_delete = []
            for row_id, trigger_json in rows:
                try:
                    events.append(json.loads(trigger_json))
                    ids_to_delete.append(row_id)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed queue entry id=%d", row_id)
                    ids_to_delete.append(row_id)

            # Delete all dequeued events
            for row_id in ids_to_delete:
                self._conn.execute(DELETE_BY_ID_SQL, (row_id,))
            self._conn.commit()

            logger.info("Dequeued %d events from local queue", len(events))
            return events

    async def flush_to_server(self, sender) -> int:
        """Send all queued events to the backend.

        Each event is sent via the provided sender.  Events are
        removed from the queue only after successful transmission.

        Args:
            sender: A ``TriggerSender`` instance with
                    ``send_frame_trigger`` and ``send_audio_trigger`` methods.

        Returns:
            Number of events successfully sent.
        """
        events = self.dequeue_all()
        if not events:
            return 0

        sent_count = 0
        for event in events:
            try:
                event_type = event.get("type", "unknown")
                if event_type == "frame":
                    result = await sender.send_frame_trigger(
                        jpeg_bytes=event.get("jpeg_bytes", b""),
                        motion_result=event.get("motion_result", {}),
                        camera_id=event.get("camera_id", ""),
                        timestamp=event.get("timestamp", ""),
                    )
                elif event_type == "audio":
                    result = await sender.send_audio_trigger(
                        audio_bytes=event.get("audio_bytes", b""),
                        yamnet_result=event.get("yamnet_result", {}),
                        camera_id=event.get("camera_id", ""),
                        timestamp=event.get("timestamp", ""),
                    )
                else:
                    logger.warning("Unknown event type in queue: %s", event_type)
                    continue

                if result.get("status") != "error":
                    sent_count += 1
                else:
                    # Re-enqueue failed events
                    self.enqueue(event)

            except Exception:
                logger.exception("Failed to flush event to server")
                self.enqueue(event)

        logger.info(
            "Flushed %d/%d events to server",
            sent_count,
            len(events),
        )
        return sent_count

    def count(self) -> int:
        """Get the number of events currently in the queue.

        Returns:
            Event count as integer.
        """
        with self._lock:
            return self._conn.execute(COUNT_SQL).fetchone()[0]

    def cleanup_expired(self) -> int:
        """Remove events older than the TTL.

        Returns:
            Number of events removed.
        """
        with self._lock:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=self._ttl_hours)).isoformat()
            cursor = self._conn.execute(DELETE_EXPIRED_SQL, (cutoff,))
            self._conn.commit()
            removed = cursor.rowcount
            if removed > 0:
                logger.info("Cleaned up %d expired events (TTL=%dh)", removed, self._ttl_hours)
            return removed

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("LocalQueue connection closed")
