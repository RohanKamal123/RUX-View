"""Tests for TriggerSender and LocalBuffer (Sprint 11.7).

All tests use mocking — no real backend API required.
TriggerSender uses httpx.AsyncClient for HTTP calls.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from connect.transport.trigger_sender import (
    LocalBuffer,
    TriggerResponse,
    TriggerSender,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def trigger_sender() -> TriggerSender:
    """Create a TriggerSender for testing."""
    return TriggerSender(
        api_base_url="https://api.visionos.test",
        auth_token="test-auth-token-123",
        timeout=5.0,
    )


@pytest.fixture
def local_buffer() -> LocalBuffer:
    """Create a LocalBuffer with a temp directory."""
    tmp_dir = tempfile.mkdtemp()
    buffer = LocalBuffer(buffer_dir=tmp_dir)
    yield buffer
    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TriggerSender Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTriggerSender:
    """Tests for TriggerSender HTTP communication."""

    def test_init_stores_params(self) -> None:
        """__init__ should store API parameters."""
        sender = TriggerSender("https://api.test.com", "token-abc", timeout=15.0)
        assert sender.api_base_url == "https://api.test.com"
        assert sender.auth_token == "token-abc"
        assert sender.timeout == 15.0

    def test_init_strips_trailing_slash(self) -> None:
        """__init__ should strip trailing slash from base URL."""
        sender = TriggerSender("https://api.test.com/", "token")
        assert sender.api_base_url == "https://api.test.com"

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_send_frame_trigger_success(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test successful frame trigger send."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"event_id": "evt-001", "message": "ok"}'
        mock_response.json.return_value = {"event_id": "evt-001", "message": "ok"}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.send_frame_trigger(
            camera_id="cam-001",
            image_base64="base64encodedimagestring",
            timestamp=1234567890.0,
        )

        assert result.success is True
        assert result.event_id == "evt-001"
        assert result.status_code == 200

        # Verify the correct API call was made
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "api/triggers/frame" in call_args[0][0]
        assert call_args[1]["json"]["camera_id"] == "cam-001"
        assert call_args[1]["json"]["image_base64"] == "base64encodedimagestring"

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_send_audio_trigger_success(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test successful audio trigger send."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"event_id": "evt-002", "message": "ok"}'
        mock_response.json.return_value = {"event_id": "evt-002", "message": "ok"}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.send_audio_trigger(
            camera_id="cam-001",
            audio_base64="base64encodedaudiostream",
            timestamp=1234567890.0,
        )

        assert result.success is True
        assert result.event_id == "evt-002"
        assert result.status_code == 200

        # Verify the correct API call was made
        call_args = mock_client.post.call_args
        assert "api/triggers/audio" in call_args[0][0]
        assert call_args[1]["json"]["audio_base64"] == "base64encodedaudiostream"

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_send_trigger_server_error(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test trigger send with server error (500)."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b'{"message": "Internal server error"}'
        mock_response.json.return_value = {"message": "Internal server error"}
        mock_response.reason_phrase = "Internal Server Error"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.send_frame_trigger(
            camera_id="cam-001",
            image_base64="data",
            timestamp=1234567890.0,
        )

        assert result.success is False
        assert result.status_code == 500

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_send_trigger_timeout(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test trigger send with timeout."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.send_frame_trigger(
            camera_id="cam-001",
            image_base64="data",
            timestamp=1234567890.0,
        )

        assert result.success is False
        assert result.status_code == 408
        assert "timed out" in result.message.lower()

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_send_trigger_network_error(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test trigger send with network error."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.send_frame_trigger(
            camera_id="cam-001",
            image_base64="data",
            timestamp=1234567890.0,
        )

        assert result.success is False
        assert result.status_code == 503

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_check_health_success(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test health check returns True when API is healthy."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.check_health()

        assert result is True

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_check_health_failure(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test health check returns False when API is unhealthy."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.check_health()

        assert result is False

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_check_health_network_error(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test health check returns False on network error."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await trigger_sender.check_health()

        assert result is False

    @patch("connect.transport.trigger_sender.httpx.AsyncClient")
    async def test_close(
        self,
        mock_client_cls: MagicMock,
        trigger_sender: TriggerSender,
    ) -> None:
        """Test close cleans up the HTTP client."""
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        mock_client_cls.return_value = mock_client

        # Trigger client creation
        await trigger_sender._get_client()
        await trigger_sender.close()

        mock_client.aclose.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# LocalBuffer Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalBuffer:
    """Tests for LocalBuffer offline resilience."""

    def test_init_creates_directory(self) -> None:
        """__init__ should create the buffer directory."""
        tmp_dir = tempfile.mkdtemp()
        buffer_dir = os.path.join(tmp_dir, "test_buffer")
        buffer = LocalBuffer(buffer_dir=buffer_dir)
        assert os.path.isdir(buffer_dir)
        buffer.clear()
        os.rmdir(buffer_dir)
        os.rmdir(tmp_dir)

    def test_enqueue_returns_true(self, local_buffer: LocalBuffer) -> None:
        """enqueue should return True on success."""
        result = local_buffer.enqueue({
            "type": "frame",
            "camera_id": "cam-001",
            "data": "base64data",
            "timestamp": 1234567890.0,
        })
        assert result is True

    def test_enqueue_creates_file(self, local_buffer: LocalBuffer) -> None:
        """enqueue should create a JSON file."""
        local_buffer.enqueue({
            "type": "frame",
            "camera_id": "cam-001",
            "data": "base64data",
            "timestamp": 1234567890.0,
        })
        files = [f for f in os.listdir(local_buffer.buffer_dir) if f.endswith(".json")]
        assert len(files) == 1

    def test_count_returns_zero_initially(self, local_buffer: LocalBuffer) -> None:
        """count should return 0 for empty buffer."""
        assert local_buffer.count() == 0

    def test_count_after_enqueue(self, local_buffer: LocalBuffer) -> None:
        """count should reflect enqueued items."""
        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "d", "timestamp": 1.0})
        local_buffer.enqueue({"type": "audio", "camera_id": "cam-001", "data": "d", "timestamp": 2.0})
        assert local_buffer.count() == 2

    def test_dequeue_all_returns_empty(self, local_buffer: LocalBuffer) -> None:
        """dequeue_all should return empty list for empty buffer."""
        assert local_buffer.dequeue_all() == []

    def test_dequeue_all_returns_events(self, local_buffer: LocalBuffer) -> None:
        """dequeue_all should return all events."""
        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "first", "timestamp": 1.0})
        local_buffer.enqueue({"type": "audio", "camera_id": "cam-001", "data": "second", "timestamp": 2.0})

        events = local_buffer.dequeue_all()
        assert len(events) == 2
        # Both events should be present (order may vary by filesystem)
        datas = {e["data"] for e in events}
        assert "first" in datas
        assert "second" in datas

    def test_dequeue_all_removes_files(self, local_buffer: LocalBuffer) -> None:
        """dequeue_all should remove files after reading."""
        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "d", "timestamp": 1.0})
        local_buffer.dequeue_all()
        assert local_buffer.count() == 0

    def test_clear_empties_buffer(self, local_buffer: LocalBuffer) -> None:
        """clear should remove all buffered files."""
        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "d", "timestamp": 1.0})
        local_buffer.enqueue({"type": "audio", "camera_id": "cam-001", "data": "d", "timestamp": 2.0})
        local_buffer.clear()
        assert local_buffer.count() == 0

    @patch("connect.transport.trigger_sender.TriggerSender")
    async def test_flush_to_api_sends_events(
        self,
        mock_sender_cls: MagicMock,
        local_buffer: LocalBuffer,
    ) -> None:
        """flush_to_api should send all events via TriggerSender."""
        mock_sender = MagicMock()
        mock_sender.send_frame_trigger = AsyncMock(return_value=TriggerResponse(
            success=True, event_id="evt-001", message="ok", status_code=200
        ))
        mock_sender.send_audio_trigger = AsyncMock(return_value=TriggerResponse(
            success=True, event_id="evt-002", message="ok", status_code=200
        ))

        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "d1", "timestamp": 1.0})
        local_buffer.enqueue({"type": "audio", "camera_id": "cam-001", "data": "d2", "timestamp": 2.0})

        sent = await local_buffer.flush_to_api(mock_sender)

        assert sent == 2
        mock_sender.send_frame_trigger.assert_called_once()
        mock_sender.send_audio_trigger.assert_called_once()

    @patch("connect.transport.trigger_sender.TriggerSender")
    async def test_flush_to_api_rebuffers_on_failure(
        self,
        mock_sender_cls: MagicMock,
        local_buffer: LocalBuffer,
    ) -> None:
        """flush_to_api should re-buffer events that fail to send."""
        mock_sender = MagicMock()
        mock_sender.send_frame_trigger = AsyncMock(return_value=TriggerResponse(
            success=False, event_id=None, message="fail", status_code=500
        ))

        local_buffer.enqueue({"type": "frame", "camera_id": "cam-001", "data": "d1", "timestamp": 1.0})

        sent = await local_buffer.flush_to_api(mock_sender)

        assert sent == 0
        # Event should be re-buffered
        assert local_buffer.count() == 1
