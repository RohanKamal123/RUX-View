"""RTSP Reader — manages RTSP connection to IP camera with auto-reconnect.

Connects to local IP cameras via RTSP on customer premises.
All connections are outbound only (solves NAT — D009).
Trigger-only architecture — no continuous streaming (D005).
"""

import asyncio
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES = 5
JPEG_QUALITY = 85
RECONNECT_BASE_DELAY = 5  # seconds


class RTSPReader:
    """Manages RTSP connection to IP camera with auto-reconnect.

    Wraps cv2.VideoCapture for RTSP stream access.
    Provides async read methods for single frames and bursts.
    Implements exponential backoff reconnection on connection loss.
    """

    def __init__(
        self,
        rtsp_url: str,
        camera_id: str,
        reconnect_delay: int = RECONNECT_BASE_DELAY,
    ) -> None:
        """Initialize RTSP reader.

        Args:
            rtsp_url: Full RTSP URL
                (e.g. rtsp://admin:pass@192.168.1.100:554/stream1)
            camera_id: Unique camera identifier
            reconnect_delay: Seconds to wait between reconnection attempts
        """
        self._rtsp_url = rtsp_url
        self._camera_id = camera_id
        self._reconnect_delay = reconnect_delay
        self._cap: Optional[cv2.VideoCapture] = None
        self._retries = 0

    # ── Public API ───────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Open RTSP connection with cv2.VideoCapture.

        Returns:
            True if connection successful, False otherwise.
        """
        loop = asyncio.get_running_loop()

        def _open() -> cv2.VideoCapture:
            cap = cv2.VideoCapture(self._rtsp_url)
            # Set buffer size to minimum for low-latency reads
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap

        # Run blocking cv2.VideoCapture in thread pool to avoid blocking event loop
        self._cap = await loop.run_in_executor(None, _open)

        if self._cap.isOpened():
            self._retries = 0
            logger.info(
                "Camera %s connected to %s", self._camera_id, self._rtsp_url
            )
            return True

        logger.warning(
            "Camera %s failed to connect to %s",
            self._camera_id,
            self._rtsp_url,
        )
        self._cap = None
        return False

    async def read_frame(self) -> Optional[bytes]:
        """Read a single frame from RTSP stream.

        Returns:
            JPEG bytes of the frame, or None if read failed.
        """
        if not self.is_connected:
            logger.warning("Camera %s not connected, cannot read frame", self._camera_id)
            return None

        loop = asyncio.get_running_loop()

        def _read() -> tuple[bool, Optional[bytes]]:
            if self._cap is None:
                return False, None
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return False, None
            # Encode frame to JPEG bytes
            success, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
            )
            if not success:
                return False, None
            return True, encoded.tobytes()

        success, jpeg_bytes = await loop.run_in_executor(None, _read)

        if not success:
            logger.debug("Camera %s: frame read failed", self._camera_id)
            return None

        return jpeg_bytes

    async def read_burst(self, n_frames: int = 8) -> list[bytes]:
        """Read N consecutive frames as fast as possible.

        Args:
            n_frames: Number of frames to read (default: 8).

        Returns:
            List of JPEG byte arrays. May contain fewer than N frames
            if the stream drops mid-burst.
        """
        frames: list[bytes] = []
        for _ in range(n_frames):
            frame = await self.read_frame()
            if frame is not None:
                frames.append(frame)
            # Yield control briefly to allow other tasks to run
            await asyncio.sleep(0)
        return frames

    async def reconnect(self) -> bool:
        """Attempt reconnection with exponential backoff.

        Retries up to MAX_RETRIES (5) times with exponential backoff.
        Delay between retries: reconnect_delay * (2 ** retry_count).

        Returns:
            True if reconnection successful.

        Raises:
            ConnectionError: If all retry attempts fail.
        """
        while self._retries < MAX_RETRIES:
            delay = self._reconnect_delay * (2 ** self._retries)
            logger.info(
                "Camera %s: reconnection attempt %d/%d in %ds",
                self._camera_id,
                self._retries + 1,
                MAX_RETRIES,
                delay,
            )
            await asyncio.sleep(delay)

            success = await self.connect()
            if success:
                logger.info(
                    "Camera %s reconnected successfully after %d attempts",
                    self._camera_id,
                    self._retries,
                )
                return True

            self._retries += 1

        raise ConnectionError(
            f"Camera {self._camera_id}: failed to reconnect after "
            f"{MAX_RETRIES} attempts"
        )

    async def disconnect(self) -> None:
        """Release VideoCapture resource."""
        if self._cap is not None:
            loop = asyncio.get_running_loop()

            def _release() -> None:
                if self._cap is not None:
                    self._cap.release()

            await loop.run_in_executor(None, _release)
            self._cap = None
            self._retries = 0
            logger.info("Camera %s disconnected", self._camera_id)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Check if camera is currently connected."""
        return self._cap is not None and self._cap.isOpened()

    @property
    def camera_id(self) -> str:
        """Get the camera identifier."""
        return self._camera_id

    @property
    def rtsp_url(self) -> str:
        """Get the RTSP URL."""
        return self._rtsp_url
