"""
trigger_sender.py — Trigger Sender for Vision OS Client Agent (Sprint 11.7).

Sends camera triggers (frame/audio) to the Vision OS backend API.
Includes offline resilience with a local buffer queue.

Stack: Python + httpx + asyncio

Key Decisions:
- D026: All calls async
- Client sends frames to backend API (which stores in MEGA)
- Local queue for offline resilience (JSON files on disk)
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TriggerResponse:
    """Response from a trigger API call."""
    success: bool
    event_id: Optional[str]
    message: str
    status_code: int


class TriggerSender:
    """Sends camera triggers to the Vision OS backend API.

    Handles frame and audio triggers with authentication.
    """

    def __init__(self, api_base_url: str, auth_token: str, timeout: float = 10.0):
        """Initialize TriggerSender.

        Args:
            api_base_url: Base URL of the Vision OS API (e.g., https://api.visionos.com).
            auth_token: Firebase auth token for API authentication.
            timeout: HTTP request timeout in seconds.
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _send_trigger(
        self, camera_id: str, data_field: str, data_value: str, timestamp: float, endpoint: str
    ) -> TriggerResponse:
        """Send a trigger to the backend.

        Args:
            camera_id: Camera identifier.
            data_field: The field name for the data ("image_base64" or "audio_base64").
            data_value: The base64-encoded data.
            timestamp: Unix timestamp.
            endpoint: API endpoint path (e.g., "frame" or "audio").

        Returns:
            TriggerResponse with result.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_base_url}/api/triggers/{endpoint}",
                json={
                    "camera_id": camera_id,
                    data_field: data_value,
                    "confidence": 1.0,
                    "timestamp": timestamp,
                },
            )

            data = response.json() if response.content else {}

            return TriggerResponse(
                success=response.status_code < 500,
                event_id=data.get("event_id"),
                message=data.get("message", response.reason_phrase or ""),
                status_code=response.status_code,
            )

        except Exception as e:
            # Catch all exceptions including when httpx is mocked in tests
            # (mocked httpx.RequestError doesn't inherit from BaseException)
            err_msg = str(e)
            if "Timeout" in type(e).__name__ or "timeout" in err_msg.lower():
                logger.warning("Timeout sending %s trigger for camera %s", endpoint, camera_id)
                return TriggerResponse(
                    success=False,
                    event_id=None,
                    message="Request timed out",
                    status_code=408,
                )
            logger.warning("Network error sending %s trigger: %s", endpoint, e)
            return TriggerResponse(
                success=False,
                event_id=None,
                message=f"Network error: {e}",
                status_code=503,
            )

    async def send_frame_trigger(
        self, camera_id: str, image_base64: str, timestamp: float
    ) -> TriggerResponse:
        """Send a frame trigger to the backend.

        Args:
            camera_id: Camera identifier.
            image_base64: Base64-encoded JPEG image.
            timestamp: Unix timestamp of the frame.

        Returns:
            TriggerResponse with result.
        """
        return await self._send_trigger(
            camera_id, "image_base64", image_base64, timestamp, "frame"
        )

    async def send_audio_trigger(
        self, camera_id: str, audio_base64: str, timestamp: float
    ) -> TriggerResponse:
        """Send an audio trigger to the backend.

        Args:
            camera_id: Camera identifier.
            audio_base64: Base64-encoded audio data.
            timestamp: Unix timestamp of the audio.

        Returns:
            TriggerResponse with result.
        """
        return await self._send_trigger(
            camera_id, "audio_base64", audio_base64, timestamp, "audio"
        )

    async def check_health(self) -> bool:
        """Check if the backend API is healthy.

        Returns:
            True if the API is reachable and healthy.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.api_base_url}/health",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class LocalBuffer:
    """Local buffer queue for offline resilience.

    Stores triggers as JSON files on disk when the backend is unreachable.
    Flushes buffered triggers when the backend becomes available again.
    """

    def __init__(self, buffer_dir: str = "buffer"):
        """Initialize LocalBuffer.

        Args:
            buffer_dir: Directory path for storing buffered triggers.
        """
        self.buffer_dir = buffer_dir
        os.makedirs(buffer_dir, exist_ok=True)

    def enqueue(self, trigger: dict) -> bool:
        """Add a trigger to the local buffer.

        Args:
            trigger: Trigger data dict with camera_id, type, data, timestamp.

        Returns:
            True if buffered successfully.
        """
        try:
            filename = f"{uuid.uuid4().hex}.json"
            filepath = os.path.join(self.buffer_dir, filename)

            trigger["_buffered_at"] = datetime.utcnow().isoformat()
            trigger["_buffer_id"] = filename

            with open(filepath, "w") as f:
                json.dump(trigger, f)

            logger.debug("Buffered trigger: %s", filename)
            return True

        except Exception as e:
            logger.error("Failed to buffer trigger: %s", e)
            return False

    def dequeue_all(self) -> list[dict]:
        """Retrieve and remove all buffered triggers.

        Returns:
            List of trigger dicts from the buffer.
        """
        triggers = []

        try:
            files = sorted(os.listdir(self.buffer_dir))

            for filename in files:
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(self.buffer_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        trigger = json.load(f)
                    triggers.append(trigger)
                    os.remove(filepath)
                except Exception as e:
                    logger.warning("Failed to read buffered trigger %s: %s", filename, e)

        except Exception as e:
            logger.error("Failed to dequeue triggers: %s", e)

        return triggers

    def count(self) -> int:
        """Count the number of buffered triggers.

        Returns:
            Number of JSON files in the buffer directory.
        """
        try:
            return len([
                f for f in os.listdir(self.buffer_dir)
                if f.endswith(".json")
            ])
        except Exception:
            return 0

    async def flush_to_api(self, sender: TriggerSender) -> int:
        """Send all buffered triggers to the backend API.

        Args:
            sender: TriggerSender instance for API calls.

        Returns:
            Number of triggers successfully sent.
        """
        triggers = self.dequeue_all()
        if not triggers:
            return 0

        sent = 0
        for trigger in triggers:
            try:
                trigger_type = trigger.get("type", "frame")
                camera_id = trigger.get("camera_id", "")
                data = trigger.get("data", "")
                timestamp = trigger.get("timestamp", 0)

                if trigger_type == "frame":
                    response = await sender.send_frame_trigger(
                        camera_id, data, timestamp
                    )
                elif trigger_type == "audio":
                    response = await sender.send_audio_trigger(
                        camera_id, data, timestamp
                    )
                else:
                    logger.warning("Unknown trigger type: %s", trigger_type)
                    continue

                if response.success:
                    sent += 1
                else:
                    # Re-buffer if still failing
                    self.enqueue(trigger)

            except Exception as e:
                logger.error("Failed to flush trigger: %s", e)
                self.enqueue(trigger)

        logger.info("Flushed %d/%d buffered triggers", sent, len(triggers))
        return sent

    def clear(self) -> None:
        """Clear all buffered triggers."""
        try:
            for filename in os.listdir(self.buffer_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.buffer_dir, filename))
            logger.info("Cleared all buffered triggers")
        except Exception as e:
            logger.error("Failed to clear buffer: %s", e)
