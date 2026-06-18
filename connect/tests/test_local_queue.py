"""Tests for LocalQueue (SQLite-backed offline buffer).

All tests use an in-memory SQLite database (":memory:") to avoid
side effects on disk.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connect.buffer.local_queue import LocalQueue


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def queue() -> LocalQueue:
    """Create a LocalQueue with in-memory SQLite database."""
    q = LocalQueue(db_path=":memory:", max_events=100, ttl_hours=48)
    yield q
    q.close()


@pytest.fixture
def sample_frame_event() -> dict:
    """Create a sample frame trigger event."""
    return {
        "type": "frame",
        "camera_id": "cam-001",
        "image_base64": "base64encodedjpeg",
        "timestamp": 1234567890.0,
    }


@pytest.fixture
def sample_audio_event() -> dict:
    """Create a sample audio trigger event."""
    return {
        "type": "audio",
        "camera_id": "cam-001",
        "audio_base64": "base64encodedaudio",
        "timestamp": 1234567890.0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LocalQueue Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalQueue:
    """Tests for LocalQueue SQLite-backed offline buffer."""

    def test_init_creates_table(self) -> None:
        """__init__ should create the trigger_queue table."""
        q = LocalQueue(db_path=":memory:")
        # Table should exist — count should work
        assert q.count() == 0
        q.close()

    def test_init_stores_params(self) -> None:
        """__init__ should store configuration parameters."""
        q = LocalQueue(db_path=":memory:", max_events=100, ttl_hours=24)
        assert q._max_events == 100
        assert q._ttl_hours == 24
        q.close()

    def test_count_returns_zero_initially(self, queue: LocalQueue) -> None:
        """count should return 0 for empty queue."""
        assert queue.count() == 0

    def test_enqueue_increases_count(self, queue: LocalQueue, sample_frame_event: dict) -> None:
        """enqueue should increase the queue count."""
        queue.enqueue(sample_frame_event)
        assert queue.count() == 1

    def test_enqueue_multiple(self, queue: LocalQueue, sample_frame_event: dict, sample_audio_event: dict) -> None:
        """enqueue should handle multiple events."""
        queue.enqueue(sample_frame_event)
        queue.enqueue(sample_audio_event)
        assert queue.count() == 2

    def test_dequeue_all_returns_empty(self, queue: LocalQueue) -> None:
        """dequeue_all should return empty list for empty queue."""
        assert queue.dequeue_all() == []

    def test_dequeue_all_returns_events_fifo(self, queue: LocalQueue) -> None:
        """dequeue_all should return events in FIFO order."""
        queue.enqueue({"type": "frame", "camera_id": "cam-001", "data": "first"})
        queue.enqueue({"type": "audio", "camera_id": "cam-001", "data": "second"})

        events = queue.dequeue_all()
        assert len(events) == 2
        assert events[0]["data"] == "first"
        assert events[1]["data"] == "second"

    def test_dequeue_all_removes_events(self, queue: LocalQueue, sample_frame_event: dict) -> None:
        """dequeue_all should remove events from the queue."""
        queue.enqueue(sample_frame_event)
        queue.dequeue_all()
        assert queue.count() == 0

    def test_enqueue_drops_oldest_when_full(self) -> None:
        """enqueue should drop oldest event when queue is at capacity."""
        q = LocalQueue(db_path=":memory:", max_events=3, ttl_hours=48)

        # Add 3 events (fills the queue)
        q.enqueue({"type": "frame", "id": 1})
        q.enqueue({"type": "frame", "id": 2})
        q.enqueue({"type": "frame", "id": 3})
        assert q.count() == 3

        # Add 4th event — oldest (id=1) should be dropped
        q.enqueue({"type": "frame", "id": 4})
        assert q.count() == 3

        # Verify oldest was dropped
        events = q.dequeue_all()
        ids = [e["id"] for e in events]
        assert 1 not in ids  # Oldest dropped
        assert 4 in ids  # Newest present
        q.close()

    def test_cleanup_expired_removes_old_events(self) -> None:
        """cleanup_expired should remove events older than TTL."""
        q = LocalQueue(db_path=":memory:", max_events=10, ttl_hours=0)  # 0 TTL = everything older than now is expired

        # Enqueue an event - it was created at "now"
        q.enqueue({"type": "frame", "camera_id": "cam-001"})
        assert q.count() == 1

        # With TTL=0, cutoff = now - 0 = now. Events created at the same
        # microsecond as the cutoff may or may not be deleted depending on
        # string comparison. Use a negative TTL to guarantee expiry.
        q.close()

        # Use a queue with negative TTL to ensure events are expired
        q2 = LocalQueue(db_path=":memory:", max_events=10, ttl_hours=-1)
        q2.enqueue({"type": "frame", "camera_id": "cam-001"})
        assert q2.count() == 1

        removed = q2.cleanup_expired()
        assert removed == 1
        assert q2.count() == 0
        q2.close()

    def test_cleanup_expired_keeps_recent_events(self) -> None:
        """cleanup_expired should keep events within TTL."""
        q = LocalQueue(db_path=":memory:", max_events=10, ttl_hours=48)

        q.enqueue({"type": "frame", "camera_id": "cam-001"})
        assert q.count() == 1

        removed = q.cleanup_expired()
        assert removed == 0  # Event is recent, should not be removed
        assert q.count() == 1
        q.close()

    def test_close_prevents_further_operations(self, queue: LocalQueue) -> None:
        """close should prevent further enqueue/dequeue operations."""
        queue.close()
        # Should not raise, but should log a warning
        queue.enqueue({"type": "frame", "camera_id": "cam-001"})
        assert queue.count() == 0

    def test_close_idempotent(self, queue: LocalQueue) -> None:
        """close should be idempotent."""
        queue.close()
        queue.close()  # Should not raise

    async def test_flush_to_server_sends_frame_events(
        self,
        queue: LocalQueue,
    ) -> None:
        """flush_to_server should send frame events via TriggerSender."""
        mock_sender = MagicMock()
        mock_sender.send_frame_trigger = AsyncMock(return_value=MagicMock(success=True))
        mock_sender.send_audio_trigger = AsyncMock(return_value=MagicMock(success=True))

        queue.enqueue({
            "type": "frame",
            "camera_id": "cam-001",
            "image_base64": "base64data",
            "timestamp": 1234567890.0,
        })

        sent = await queue.flush_to_server(mock_sender)

        assert sent == 1
        mock_sender.send_frame_trigger.assert_called_once()

    async def test_flush_to_server_sends_audio_events(
        self,
        queue: LocalQueue,
    ) -> None:
        """flush_to_server should send audio events via TriggerSender."""
        mock_sender = MagicMock()
        mock_sender.send_audio_trigger = AsyncMock(return_value=MagicMock(success=True))

        queue.enqueue({
            "type": "audio",
            "camera_id": "cam-001",
            "audio_base64": "base64data",
            "timestamp": 1234567890.0,
        })

        sent = await queue.flush_to_server(mock_sender)

        assert sent == 1
        mock_sender.send_audio_trigger.assert_called_once()

    async def test_flush_to_server_re_enqueues_on_failure(
        self,
        queue: LocalQueue,
    ) -> None:
        """flush_to_server should re-enqueue events that fail to send."""
        mock_sender = MagicMock()
        mock_sender.send_frame_trigger = AsyncMock(return_value=MagicMock(success=False))

        queue.enqueue({
            "type": "frame",
            "camera_id": "cam-001",
            "image_base64": "base64data",
            "timestamp": 1234567890.0,
        })

        sent = await queue.flush_to_server(mock_sender)

        assert sent == 0
        # Event should be re-enqueued
        assert queue.count() == 1

    def test_enqueue_handles_large_payload(self, queue: LocalQueue) -> None:
        """enqueue should handle large trigger payloads."""
        large_payload = {
            "type": "frame",
            "camera_id": "cam-001",
            "image_base64": "A" * 100000,  # 100KB base64 string
            "timestamp": 1234567890.0,
        }
        queue.enqueue(large_payload)
        assert queue.count() == 1

        events = queue.dequeue_all()
        assert len(events) == 1
        assert len(events[0]["image_base64"]) == 100000

    def test_concurrent_enqueue_dequeue(self) -> None:
        """enqueue and dequeue should be thread-safe."""
        q = LocalQueue(db_path=":memory:", max_events=500, ttl_hours=48)

        import threading

        def enqueue_worker(lq: LocalQueue, count: int) -> None:
            for i in range(count):
                lq.enqueue({"type": "frame", "id": i})

        threads = []
        for _ in range(5):
            t = threading.Thread(target=enqueue_worker, args=(q, 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert q.count() == 50

        events = q.dequeue_all()
        assert len(events) == 50
        q.close()
