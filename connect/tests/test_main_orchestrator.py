"""End-to-End Tests for VisionOSConnect Main Orchestrator.

Tests the full application lifecycle: start → process → stop.
All external dependencies (RTSP, HTTP, WebSocket, PyAudio) are mocked.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from connect.main import VisionOSConnect
from connect.config import AppConfig


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def app_config() -> AppConfig:
    """Create a minimal AppConfig for testing."""
    return AppConfig(
        rtsp_url="rtsp://test:554/stream1",
        camera_id="test-cam-001",
        backend_url="https://api.visionos.test",
        api_key="test-api-key-123",
        motion_threshold=0.02,
        motion_min_area=5000,
        audio_enabled=False,
        mode="motion",
    )


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Create a synthetic BGR frame (480x640)."""
    return np.ones((480, 640, 3), dtype=np.uint8) * 128


# ═══════════════════════════════════════════════════════════════════════════════
# VisionOSConnect Orchestrator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestVisionOSConnect:
    """Tests for the main VisionOSConnect orchestrator."""

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_start_stop(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: Start and stop the orchestrator cleanly."""
        # ── Mock RTSP Reader ────────────────────────────────────────────────
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=True)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        # ── Mock TriggerSender ──────────────────────────────────────────────
        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        # ── Mock WebSocketClient ────────────────────────────────────────────
        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        # ── Mock LocalQueue ─────────────────────────────────────────────────
        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        # ── Test ────────────────────────────────────────────────────────────
        app = VisionOSConnect(app_config)
        assert app.status == "stopped"

        await app.start()
        assert app.status == "running"

        await app.stop()
        assert app.status == "stopped"

        # Verify lifecycle
        mock_reader.connect.assert_called_once()
        mock_ws.connect.assert_called_once()
        mock_sender.close.assert_called_once()
        mock_reader.release.assert_called_once()
        mock_ws.disconnect.assert_called_once()

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_start_camera_failure(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: Start continues even if camera connection fails."""
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=False)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        app = VisionOSConnect(app_config)
        await app.start()
        assert app.status == "running"  # Should still start

        await app.stop()

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_start_ws_failure(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: Start continues even if WebSocket connection fails."""
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=True)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=False)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        app = VisionOSConnect(app_config)
        await app.start()
        assert app.status == "running"  # Should still start

        await app.stop()

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_double_start(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: Calling start twice should be a no-op."""
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=True)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        app = VisionOSConnect(app_config)
        await app.start()
        await app.start()  # Second start should be no-op
        assert app.status == "running"

        await app.stop()

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_status_property(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: status property reflects current state."""
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=True)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        app = VisionOSConnect(app_config)
        assert app.status == "stopped"

        await app.start()
        assert app.status == "running"

        await app.stop()
        assert app.status == "stopped"

    @patch("connect.main.RTSPReader")
    @patch("connect.main.TriggerSender")
    @patch("connect.main.WebSocketClient")
    @patch("connect.main.LocalQueue")
    @patch("connect.main.ClientConfigSync")
    async def test_config_property(
        self,
        mock_sync_cls: MagicMock,
        mock_queue_cls: MagicMock,
        mock_ws_cls: MagicMock,
        mock_sender_cls: MagicMock,
        mock_reader_cls: MagicMock,
        app_config: AppConfig,
    ) -> None:
        """Test: config property returns the configuration."""
        mock_reader = MagicMock()
        mock_reader.connect = AsyncMock(return_value=True)
        mock_reader.release = AsyncMock()
        mock_reader_cls.return_value = mock_reader

        mock_sender = MagicMock()
        mock_sender.close = AsyncMock()
        mock_sender_cls.return_value = mock_sender

        mock_ws = MagicMock()
        mock_ws.connect = AsyncMock(return_value=True)
        mock_ws.disconnect = AsyncMock()
        mock_ws.receive_messages = AsyncMock()
        mock_ws_cls.return_value = mock_ws

        mock_queue = MagicMock()
        mock_queue.count.return_value = 0
        mock_queue_cls.return_value = mock_queue

        # ── Mock ClientConfigSync ───────────────────────────────────────────
        mock_sync = MagicMock()
        mock_sync.run_forever = AsyncMock(return_value=None)
        mock_sync.close = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        app = VisionOSConnect(app_config)
        assert app.config is app_config
        assert app.config.camera_id == "test-cam-001"
