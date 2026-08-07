"""Tests for connect/config_sync.py — ClientConfigSync.

All HTTP calls are mocked (patches connect.config_sync.httpx.AsyncClient),
same pattern as test_transport.py's TriggerSender tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connect.camera.motion_detector import MotionDetector
from connect.camera.rtsp_reader import RTSPReader
from connect.config_sync import ClientConfigSync, DEFAULT_POLL_INTERVAL_SEC


@pytest.fixture
def motion_detector() -> MotionDetector:
    return MotionDetector(threshold=0.05, min_area=8000)


@pytest.fixture
def rtsp_reader() -> RTSPReader:
    return RTSPReader("rtsp://test:554/stream1", "cam-001")


@pytest.fixture
def config_sync(motion_detector: MotionDetector, rtsp_reader: RTSPReader) -> ClientConfigSync:
    return ClientConfigSync(
        backend_url="https://api.visionos.test/",
        auth_token="test-token",
        motion_detector=motion_detector,
        rtsp_reader=rtsp_reader,
    )


class TestClientConfigSyncInit:
    def test_init_strips_trailing_slash(self, config_sync: ClientConfigSync) -> None:
        assert config_sync.backend_url == "https://api.visionos.test"

    def test_init_default_poll_interval(self, config_sync: ClientConfigSync) -> None:
        assert config_sync.poll_interval == DEFAULT_POLL_INTERVAL_SEC


class TestSyncOnce:
    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_sync_once_applies_motion_config(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
        motion_detector: MotionDetector,
    ) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "motion_min_area": 12000,
            "motion_threshold": 0.09,
            "motion_history": 500,
            "motion_var_threshold": 56,
            "fg_mask_threshold": 200,
            "rtsp_reconnect_delay_sec": 5,
            "rtsp_connect_timeout_sec": 10.0,
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await config_sync.sync_once()

        assert result is True
        assert motion_detector.min_area == 12000
        assert motion_detector.threshold == 0.09
        mock_client.get.assert_called_once_with(
            "https://api.visionos.test/api/config/client"
        )

    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_sync_once_applies_rtsp_config(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
        rtsp_reader: RTSPReader,
    ) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "rtsp_reconnect_delay_sec": 20,
            "rtsp_connect_timeout_sec": 25.0,
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await config_sync.sync_once()

        assert result is True
        assert rtsp_reader.reconnect_delay == 20
        assert rtsp_reader.connect_timeout == 25.0

    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_sync_once_returns_false_on_network_error(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
        motion_detector: MotionDetector,
    ) -> None:
        """A backend-unreachable poll must not raise -- it's a
        nice-to-have, never a reason to interrupt trigger processing.
        Uses a plain exception rather than a real httpx.ConnectError since
        connect/tests/conftest.py replaces the httpx module in sys.modules
        with a lightweight mock (no real network dependency needed for the
        rest of the suite) -- sync_once()'s except clause is a bare
        ``except Exception`` anyway, so this exercises the same path."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client_cls.return_value = mock_client
        original_min_area = motion_detector.min_area

        result = await config_sync.sync_once()

        assert result is False
        assert motion_detector.min_area == original_min_area

    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_sync_once_returns_false_on_http_error_status(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
    ) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=RuntimeError("HTTP 401"))
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await config_sync.sync_once()

        assert result is False

    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_sync_once_sends_auth_header(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
    ) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await config_sync.sync_once()

        _, kwargs = mock_client_cls.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"


class TestRunForever:
    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_run_forever_syncs_immediately_then_sleeps(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
    ) -> None:
        """First sync happens before the first sleep -- a freshly-launched
        agent shouldn't run on stale defaults for up to a minute."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client
        config_sync.poll_interval = 0.01

        task = asyncio.create_task(config_sync.run_forever())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert mock_client.get.call_count >= 1

    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_run_forever_cancellation_propagates(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
    ) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client
        config_sync.poll_interval = 5.0

        task = asyncio.create_task(config_sync.run_forever())
        await asyncio.sleep(0.01)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


class TestClose:
    @patch("connect.config_sync.httpx.AsyncClient")
    async def test_close_closes_client(
        self,
        mock_client_cls: MagicMock,
        config_sync: ClientConfigSync,
    ) -> None:
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client_cls.return_value = mock_client

        await config_sync._get_client()
        await config_sync.close()

        mock_client.aclose.assert_awaited_once()
        assert config_sync._client is None

    async def test_close_without_client_does_not_crash(
        self, config_sync: ClientConfigSync,
    ) -> None:
        await config_sync.close()  # Should not raise
