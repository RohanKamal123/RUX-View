"""config_sync.py — Client-side sync of backend runtime-tunable config.

connect/ is a separate Windows deployable with no direct Redis access, so
it has never had any way to pick up config_store's motion_*/rtsp_* tuning
(dashboard "Tuning" page, backed by backend/core/config_store.py) short of
a client rebuild with new env-var overrides. ClientConfigSync closes that
gap by polling GET /api/config/client (backend/api/config.py) and applying
the result live to a MotionDetector and RTSPReader.

Trigger-only architecture (D005) -- this is config metadata only, never
frame/video data, so it fits the same "small, infrequent HTTPS calls"
shape as the rest of the client's backend traffic.
"""

import asyncio
import logging
from typing import Optional

import httpx

from connect.camera.motion_detector import MotionDetector
from connect.camera.rtsp_reader import RTSPReader

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 60.0


class ClientConfigSync:
    """Background poller that keeps a MotionDetector and RTSPReader's
    tunables in sync with the backend's config_store.

    Failures (network error, backend down, bad response) are logged and
    swallowed -- a config sync is a nice-to-have, never a reason to stop
    processing camera triggers.
    """

    def __init__(
        self,
        backend_url: str,
        auth_token: str,
        motion_detector: MotionDetector,
        rtsp_reader: RTSPReader,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SEC,
    ) -> None:
        """Initialize ClientConfigSync.

        Args:
            backend_url: Backend API base URL (same as AppConfig.backend_url).
            auth_token: Bearer token used for /api/triggers/* -- the client
                config endpoint is protected by the same get_current_user
                dependency, so no separate credential is needed.
            motion_detector: The live MotionDetector instance to update.
            rtsp_reader: The live RTSPReader instance to update.
            poll_interval: Seconds between polls.
        """
        self.backend_url = backend_url.rstrip("/")
        self.auth_token = auth_token
        self.motion_detector = motion_detector
        self.rtsp_reader = rtsp_reader
        self.poll_interval = poll_interval
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                headers={"Authorization": f"Bearer {self.auth_token}"},
            )
        return self._client

    async def sync_once(self) -> bool:
        """Fetch the latest client config from the backend and apply it.

        Returns:
            True if the sync succeeded and was applied, False on any
            failure -- callers should treat False as "try again next poll",
            never as fatal.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.backend_url}/api/config/client")
            response.raise_for_status()
            config = response.json()
        except Exception as exc:
            logger.debug("Config sync failed (will retry next poll): %s", exc)
            return False

        try:
            self.motion_detector.update_config(config)
            if "rtsp_reconnect_delay_sec" in config:
                self.rtsp_reader.reconnect_delay = config["rtsp_reconnect_delay_sec"]
            if "rtsp_connect_timeout_sec" in config:
                self.rtsp_reader.connect_timeout = config["rtsp_connect_timeout_sec"]
        except Exception:
            logger.exception("Failed to apply synced config")
            return False

        logger.debug("Applied synced config: %s", config)
        return True

    async def run_forever(self) -> None:
        """Poll indefinitely until cancelled.

        The first sync happens immediately on start (not after the first
        poll_interval wait) so a freshly-launched client agent doesn't run
        on stale local defaults for up to a minute.
        """
        while True:
            await self.sync_once()
            await asyncio.sleep(self.poll_interval)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
