"""Tests for Transport and Buffer modules (Sprint 2.4).

Tests WebSocket client, trigger sender, SMS sender, and local queue.
All tests use mocking — no real network or database required.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connect.transport.websocket_client import WSConfig, WebSocketClient
from connect.transport.trigger_sender import TriggerSender
from connect.transport.sms_sender import SMSSender
from connect.buffer.local_queue import LocalQueue


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def ws_config() -> WSConfig:
    """Create a WSConfig for testing."""
    return WSConfig(
        server_url="wss://test.visionos.app/ws",
        heartbeat_interval=30,
        reconnect_delay=1,
        max_reconnect_attempts=3,
    )


@pytest.fixture
def ws_client(ws_config: WSConfig) -> WebSocketClient:
    """Create a WebSocketClient for testing."""
    return WebSocketClient(
        config=ws_config,
        camera_id="cam_test_001",
        user_token="test_token_123",
    )


@pytest.fixture
def trigger_sender() -> TriggerSender:
    """Create a TriggerSender for testing."""
    return TriggerSender(
        backend_url="https://test.visionos.app",
        user_token="test_token_123",
    )


@pytest.fixture
def sms_sender() -> SMSSender:
    """Create an SMSSender for testing."""
    return SMSSender(
        api_key="test_api_key",
        api_secret="test_api_secret",
        sender_id="VisionOS",
    )


@pytest.fixture
def temp_db_path() -> str:
    """Create a temporary database path for LocalQueue tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    # Cleanup is handled by the local_queue fixture's close()
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass  # Windows may still hold the handle


@pytest.fixture
def local_queue(temp_db_path: str) -> LocalQueue:
    """Create a LocalQueue with a temporary database."""
    queue = LocalQueue(
        db_path=temp_db_path,
        max_events=10,
        ttl_hours=48,
    )
    yield queue
    queue.close()


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket Client Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebSocketClient:
    """Tests for WebSocketClient connection management."""

    async def test_connect_success(self, ws_client: WebSocketClient) -> None:
        """Test that connect establishes a WebSocket connection."""
        # The conftest mock makes websockets.connect return a MockWebSocketProtocol
        result = await ws_client.connect()

        assert result is True
        assert ws_client.is_connected is True

    async def test_connect_failure(self, ws_client: WebSocketClient) -> None:
        """Test that connect returns False on failure."""
        # Temporarily break the mock to simulate failure
        import connect.transport.websocket_client as ws_mod
        original_connect = ws_mod.websockets.connect

        async def _failing_connect(url, **kwargs):
            raise ConnectionError("Connection refused")

        ws_mod.websockets.connect = _failing_connect

        try:
            result = await ws_client.connect()
            assert result is False
            assert ws_client.is_connected is False
        finally:
            ws_mod.websockets.connect = original_connect

    async def test_send_message(self, ws_client: WebSocketClient) -> None:
        """Test that send_message sends JSON over WebSocket."""
        result = await ws_client.connect()
        assert result is True

        result = await ws_client.send_message({"type": "ping"})
        assert result is True

    async def test_send_message_when_disconnected(
        self,
        ws_client: WebSocketClient,
    ) -> None:
        """Test that send_message returns False when not connected."""
        result = await ws_client.send_message({"type": "ping"})
        assert result is False

    async def test_disconnect(self, ws_client: WebSocketClient) -> None:
        """Test that disconnect closes the WebSocket gracefully."""
        await ws_client.connect()
        assert ws_client.is_connected is True

        await ws_client.disconnect()
        assert ws_client.is_connected is False

    async def test_reconnect_with_backoff(
        self,
        ws_client: WebSocketClient,
    ) -> None:
        """Test that reconnect retries with exponential backoff."""
        # First attempt fails, second succeeds
        import connect.transport.websocket_client as ws_mod
        original_connect = ws_mod.websockets.connect

        call_count = [0]

        async def _alternating_connect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("First fail")
            from connect.tests.conftest import MockWebSocketProtocol
            return MockWebSocketProtocol()

        ws_mod.websockets.connect = _alternating_connect

        try:
            result = await ws_client.reconnect()
            assert result is True
        finally:
            ws_mod.websockets.connect = original_connect

    async def test_reconnect_exhausts_attempts(
        self,
        ws_client: WebSocketClient,
    ) -> None:
        """Test that reconnect returns False after exhausting attempts."""
        import connect.transport.websocket_client as ws_mod
        original_connect = ws_mod.websockets.connect

        async def _always_failing_connect(url, **kwargs):
            raise ConnectionError("Always fails")

        ws_mod.websockets.connect = _always_failing_connect

        try:
            result = await ws_client.reconnect()
            assert result is False
        finally:
            ws_mod.websockets.connect = original_connect

    async def test_heartbeat(self, ws_client: WebSocketClient) -> None:
        """Test that send_heartbeat sends a heartbeat message."""
        await ws_client.connect()
        assert ws_client.is_connected is True

        # send_heartbeat should not raise
        await ws_client.send_heartbeat()


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger Sender Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTriggerSender:
    """Tests for TriggerSender HTTP communication."""

    async def test_send_frame_trigger_success(
        self,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test that send_frame_trigger returns success on valid response."""
        result = await trigger_sender.send_frame_trigger(
            jpeg_bytes=b"fake_jpeg_bytes",
            motion_result={"pixel_diff": 5000, "diff_category": "urgent"},
            camera_id="cam_test_001",
            timestamp="2024-01-15T10:30:00Z",
        )

        assert result.get("status") == "success"
        assert "incident_id" in result

    async def test_send_audio_trigger_success(
        self,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test that send_audio_trigger returns success on valid response."""
        result = await trigger_sender.send_audio_trigger(
            audio_bytes=b"fake_audio_bytes",
            yamnet_result={"class_name": "glass_breaking", "confidence": 0.85},
            camera_id="cam_test_001",
            timestamp="2024-01-15T10:30:00Z",
        )

        assert result.get("status") == "success"

    async def test_health_check_success(
        self,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test that health_check returns True when backend is reachable."""
        healthy = await trigger_sender.health_check()
        assert healthy is True

    async def test_health_check_failure(
        self,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test that health_check returns False on failure."""
        # Patch the client to simulate failure
        with patch.object(trigger_sender, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_client

            healthy = await trigger_sender.health_check()
            assert healthy is False


# ═══════════════════════════════════════════════════════════════════════════════
# SMS Sender Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSMSSender:
    """Tests for SMSSender SSL Wireless API communication."""

    async def test_send_sms_success(
        self,
        sms_sender: SMSSender,
    ) -> None:
        """Test that send_sms returns True on success."""
        result = await sms_sender.send_sms(
            phone="+8801712345678",
            message="VisionOS HIGH ALERT - Motion detected",
        )
        assert result is True

    async def test_send_sms_failure(
        self,
        sms_sender: SMSSender,
    ) -> None:
        """Test that send_sms returns False on API failure."""
        with patch.object(sms_sender, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = Exception("API error")
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await sms_sender.send_sms(
                phone="+8801712345678",
                message="Test message",
            )
            assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Local Queue Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalQueue:
    """Tests for LocalQueue SQLite-backed offline buffer."""

    def test_enqueue_and_count(self, local_queue: LocalQueue) -> None:
        """Test that enqueue adds events and count reflects them."""
        assert local_queue.count() == 0

        local_queue.enqueue({"type": "frame", "camera_id": "cam_001"})
        assert local_queue.count() == 1

        local_queue.enqueue({"type": "audio", "camera_id": "cam_001"})
        assert local_queue.count() == 2

    def test_dequeue_all_returns_fifo(self, local_queue: LocalQueue) -> None:
        """Test that dequeue_all returns events in FIFO order."""
        local_queue.enqueue({"type": "frame", "seq": 1})
        local_queue.enqueue({"type": "audio", "seq": 2})
        local_queue.enqueue({"type": "frame", "seq": 3})

        events = local_queue.dequeue_all()

        assert len(events) == 3
        assert events[0]["seq"] == 1
        assert events[1]["seq"] == 2
        assert events[2]["seq"] == 3

    def test_dequeue_empties_queue(self, local_queue: LocalQueue) -> None:
        """Test that dequeue_all removes all events from the queue."""
        local_queue.enqueue({"type": "frame", "camera_id": "cam_001"})
        local_queue.enqueue({"type": "audio", "camera_id": "cam_001"})

        events = local_queue.dequeue_all()
        assert len(events) == 2
        assert local_queue.count() == 0

    def test_dequeue_empty_queue(self, local_queue: LocalQueue) -> None:
        """Test that dequeue_all returns empty list for empty queue."""
        events = local_queue.dequeue_all()
        assert events == []

    def test_queue_drops_oldest_at_capacity(self, local_queue: LocalQueue) -> None:
        """Test that queue drops oldest event when at capacity."""
        # Fill queue to max_events (10)
        for i in range(10):
            local_queue.enqueue({"type": "frame", "seq": i})
        assert local_queue.count() == 10

        # Add one more — oldest should be dropped
        local_queue.enqueue({"type": "frame", "seq": 10})
        assert local_queue.count() == 10

        # Verify seq 0 was dropped (oldest)
        events = local_queue.dequeue_all()
        seqs = [e["seq"] for e in events]
        assert 0 not in seqs
        assert 10 in seqs

    def test_cleanup_expired(self, local_queue: LocalQueue) -> None:
        """Test that cleanup_expired removes old events."""
        local_queue.enqueue({"type": "frame", "camera_id": "cam_001"})
        assert local_queue.count() == 1

        # Set TTL to 0 and cleanup — should remove everything
        local_queue._ttl_hours = 0
        removed = local_queue.cleanup_expired()
        assert removed == 1
        assert local_queue.count() == 0

    def test_close(self, local_queue: LocalQueue) -> None:
        """Test that close cleans up the database connection."""
        local_queue.enqueue({"type": "frame", "camera_id": "cam_001"})
        local_queue.close()
        # After close, the connection should be None
        assert local_queue._conn is None

    async def test_flush_to_server_empty(self, local_queue: LocalQueue) -> None:
        """Test that flush_to_server returns 0 for empty queue."""
        sender = MagicMock()
        sent = await local_queue.flush_to_server(sender)
        assert sent == 0

    async def test_flush_to_server_sends_events(
        self,
        local_queue: LocalQueue,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test that flush_to_server sends queued events."""
        # Use JSON-serializable data (no bytes)
        local_queue.enqueue({
            "type": "frame",
            "jpeg_bytes_hex": b"fake_jpeg".hex(),
            "motion_result": {"pixel_diff": 5000},
            "camera_id": "cam_001",
            "timestamp": "2024-01-15T10:30:00Z",
        })
        assert local_queue.count() == 1

        # flush_to_server calls dequeue_all then sends
        sent = await local_queue.flush_to_server(trigger_sender)
        assert sent == 1
        assert local_queue.count() == 0
