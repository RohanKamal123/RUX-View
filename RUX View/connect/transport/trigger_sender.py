"""Trigger Sender — send JPEG + audio triggers to backend via HTTPS POST.

Uses httpx for async HTTP communication with the backend API.
All connections are outbound only (solves NAT — D009).
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT = 30.0  # seconds


class TriggerSender:
    """Send JPEG + audio triggers to backend via HTTPS POST.

    Usage:
        sender = TriggerSender(
            backend_url="https://api.visionos.app",
            user_token="abc123",
        )
        result = await sender.send_frame_trigger(
            jpeg_bytes=frame_data,
            motion_result={"pixel_diff": 5000, "diff_category": "urgent"},
            camera_id="cam_001",
            timestamp="2024-01-15T10:30:00Z",
        )
    """

    def __init__(
        self,
        backend_url: str,
        user_token: str,
    ) -> None:
        """Initialize trigger sender.

        Args:
            backend_url: Base URL of the backend API
                         (e.g. ``https://api.visionos.app``).
            user_token: Firebase ID token for authentication.
        """
        self._backend_url = backend_url.rstrip("/")
        self._user_token = user_token
        self._client: Optional[httpx.AsyncClient] = None

    # ── Public API ───────────────────────────────────────────────────────────

    async def send_frame_trigger(
        self,
        jpeg_bytes: bytes,
        motion_result: dict,
        camera_id: str,
        timestamp: str,
    ) -> dict:
        """POST a frame trigger to the backend.

        Sends the JPEG frame along with motion analysis metadata
        to ``/triggers/frame``.

        Args:
            jpeg_bytes: JPEG-encoded frame bytes.
            motion_result: Dict with motion analysis
                           (``pixel_diff``, ``diff_category``, etc.).
            camera_id: Unique camera identifier.
            timestamp: ISO 8601 timestamp string.

        Returns:
            Dict with ``status`` and ``incident_id`` on success,
            or ``{"status": "error"}`` on failure.
        """
        client = await self._get_client()

        try:
            # Build multipart form data
            files = {
                "frame": ("frame.jpg", jpeg_bytes, "image/jpeg"),
            }
            data = {
                "camera_id": camera_id,
                "timestamp": timestamp,
                "motion_result": json.dumps(motion_result),
            }
            headers = {
                "Authorization": f"Bearer {self._user_token}",
            }

            response = await client.post(
                f"{self._backend_url}/triggers/frame",
                files=files,
                data=data,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                "Frame trigger sent (camera=%s, incident=%s)",
                camera_id,
                result.get("incident_id", "unknown"),
            )
            return result

        except httpx.TimeoutException:
            logger.warning("Frame trigger timed out (camera=%s)", camera_id)
            return {"status": "error", "detail": "timeout"}
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Frame trigger HTTP error (camera=%s): %d %s",
                camera_id,
                exc.response.status_code,
                exc.response.text,
            )
            return {"status": "error", "detail": f"http_{exc.response.status_code}"}
        except Exception:
            logger.exception("Frame trigger failed (camera=%s)", camera_id)
            return {"status": "error", "detail": "unknown"}

    async def send_audio_trigger(
        self,
        audio_bytes: bytes,
        yamnet_result: dict,
        camera_id: str,
        timestamp: str,
    ) -> dict:
        """POST an audio trigger to the backend.

        Sends the audio chunk along with YAMNet classification
        metadata to ``/triggers/audio``.

        Args:
            audio_bytes: Raw audio bytes (WAV or float32 PCM).
            yamnet_result: Dict with YAMNet classification
                           (``class_name``, ``confidence``, etc.).
            camera_id: Unique camera identifier.
            timestamp: ISO 8601 timestamp string.

        Returns:
            Dict with ``status`` and ``audio_event_id`` on success,
            or ``{"status": "error"}`` on failure.
        """
        client = await self._get_client()

        try:
            files = {
                "audio": ("audio.wav", audio_bytes, "audio/wav"),
            }
            data = {
                "camera_id": camera_id,
                "timestamp": timestamp,
                "yamnet_result": json.dumps(yamnet_result),
            }
            headers = {
                "Authorization": f"Bearer {self._user_token}",
            }

            response = await client.post(
                f"{self._backend_url}/triggers/audio",
                files=files,
                data=data,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                "Audio trigger sent (camera=%s, event=%s)",
                camera_id,
                result.get("audio_event_id", "unknown"),
            )
            return result

        except httpx.TimeoutException:
            logger.warning("Audio trigger timed out (camera=%s)", camera_id)
            return {"status": "error", "detail": "timeout"}
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Audio trigger HTTP error (camera=%s): %d %s",
                camera_id,
                exc.response.status_code,
                exc.response.text,
            )
            return {"status": "error", "detail": f"http_{exc.response.status_code}"}
        except Exception:
            logger.exception("Audio trigger failed (camera=%s)", camera_id)
            return {"status": "error", "detail": "unknown"}

    async def health_check(self) -> bool:
        """Check if the backend is reachable.

        Sends a GET request to ``/health``.

        Returns:
            True if the backend responds with 200 OK.
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._backend_url}/health",
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            logger.warning("Health check failed for %s", self._backend_url)
            return False

    # ── Internal: Client Management ──────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
