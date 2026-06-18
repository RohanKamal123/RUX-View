"""WebSocket Client — persistent outbound connection with heartbeat and reconnect.

Maintains a persistent WebSocket connection to the backend server.
Sends authentication on connect, periodic heartbeats every 30s,
and supports automatic reconnection with exponential backoff.

All connections are outbound only (solves NAT — D009).
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import websockets

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_HEARTBEAT_INTERVAL = 30
DEFAULT_RECONNECT_DELAY = 5
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10
MAX_BACKOFF = 120  # maximum backoff in seconds


@dataclass
class WSConfig:
    """WebSocket connection configuration.

    Attributes:
        server_url: WebSocket server URL (e.g. wss://api.visionos.app/ws).
        heartbeat_interval: Seconds between heartbeat pings (default: 30).
        reconnect_delay: Initial delay before reconnect attempt (default: 5).
        max_reconnect_attempts: Maximum reconnection attempts (default: 10).
    """
    server_url: str
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    reconnect_delay: int = DEFAULT_RECONNECT_DELAY
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS


class WebSocketClient:
    """Persistent WebSocket connection to backend.

    Usage:
        config = WSConfig(server_url="wss://api.visionos.app/ws")
        ws = WebSocketClient(config, camera_id="cam_001", user_token="abc123")
        await ws.connect()
        await ws.send_message({"type": "ping"})
        # ... receive messages via handler ...
        await ws.disconnect()
    """

    def __init__(
        self,
        config: WSConfig,
        camera_id: str,
        user_token: str,
    ) -> None:
        """Initialize WebSocket client.

        Args:
            config: WSConfig with server URL and connection parameters.
            camera_id: Unique camera identifier for authentication.
            user_token: Firebase ID token for authentication.
        """
        self._config = config
        self._camera_id = camera_id
        self._user_token = user_token

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0

    # ── Public API ───────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Establish WebSocket connection.

        Sends authentication message ``{camera_id, token}`` on connect.

        Returns:
            True if connection was established successfully.
        """
        try:
            logger.info(
                "Connecting to WebSocket: %s (camera=%s)",
                self._config.server_url,
                self._camera_id,
            )
            self._ws = await websockets.connect(
                self._config.server_url,
                ping_interval=None,  # we handle heartbeats ourselves
                ping_timeout=None,
            )

            # Send authentication
            auth_msg = json.dumps({
                "type": "auth",
                "camera_id": self._camera_id,
                "token": self._user_token,
            })
            await self._ws.send(auth_msg)

            self._connected = True
            self._reconnect_attempts = 0
            logger.info("WebSocket connected (camera=%s)", self._camera_id)

            # Start heartbeat and receive tasks
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop()
            )
            return True

        except Exception:
            logger.exception("WebSocket connection failed (camera=%s)", self._camera_id)
            self._connected = False
            self._ws = None
            return False

    async def send_heartbeat(self) -> None:
        """Send a single heartbeat message to keep the connection alive."""
        if not self._connected or self._ws is None:
            logger.warning("Cannot send heartbeat — not connected")
            return

        try:
            await self._ws.send(json.dumps({"type": "heartbeat"}))
            logger.debug("Heartbeat sent (camera=%s)", self._camera_id)
        except Exception:
            logger.exception("Failed to send heartbeat (camera=%s)", self._camera_id)
            self._connected = False

    async def send_message(self, message: dict) -> bool:
        """Send a JSON message over WebSocket.

        Args:
            message: Dictionary to serialise as JSON and send.

        Returns:
            True if the message was sent successfully.
        """
        if not self._connected or self._ws is None:
            logger.warning("Cannot send message — not connected")
            return False

        try:
            payload = json.dumps(message)
            await self._ws.send(payload)
            logger.debug("Message sent (camera=%s): %s", self._camera_id, message.get("type", "unknown"))
            return True
        except Exception:
            logger.exception("Failed to send message (camera=%s)", self._camera_id)
            self._connected = False
            return False

    async def receive_messages(self, handler: Callable) -> None:
        """Continuously receive messages and pass them to the handler.

        This method runs indefinitely until the connection is closed.
        The handler is called with the parsed JSON dict for each message.

        Args:
            handler: Async callable that accepts a dict (parsed JSON message).
        """
        while self._connected and self._ws is not None:
            try:
                raw = await self._ws.recv()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                message = json.loads(raw)
                logger.debug("Message received (camera=%s): %s", self._camera_id, message.get("type", "unknown"))

                # Dispatch to handler
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)

            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "WebSocket connection closed (camera=%s)",
                    self._camera_id,
                )
                self._connected = False
                break
            except Exception:
                logger.exception(
                    "Error receiving message (camera=%s)",
                    self._camera_id,
                )
                # Continue listening unless connection is lost
                if not self._connected:
                    break

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        # Cancel background tasks
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None

        if self._ws is not None:
            try:
                await self._ws.close()
                logger.info("WebSocket disconnected (camera=%s)", self._camera_id)
            except Exception:
                logger.exception("Error closing WebSocket (camera=%s)", self._camera_id)
            finally:
                self._ws = None

        self._connected = False

    async def reconnect(self) -> bool:
        """Reconnect with exponential backoff.

        Attempts reconnection up to ``max_reconnect_attempts`` times.
        Backoff doubles each attempt, capped at ``MAX_BACKOFF`` (120s).

        Returns:
            True if reconnection succeeded.
        """
        while self._reconnect_attempts < self._config.max_reconnect_attempts:
            self._reconnect_attempts += 1
            delay = min(
                self._config.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                MAX_BACKOFF,
            )

            logger.info(
                "Reconnect attempt %d/%d in %.1fs (camera=%s)",
                self._reconnect_attempts,
                self._config.max_reconnect_attempts,
                delay,
                self._camera_id,
            )

            await asyncio.sleep(delay)

            if await self.connect():
                return True

        logger.error(
            "Max reconnect attempts reached (%d) (camera=%s)",
            self._config.max_reconnect_attempts,
            self._camera_id,
        )
        return False

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket connection is currently active."""
        return self._connected

    # ── Internal: Heartbeat Loop ─────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Periodically send heartbeats to keep the connection alive."""
        try:
            while self._connected:
                await asyncio.sleep(self._config.heartbeat_interval)
                await self.send_heartbeat()
        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled (camera=%s)", self._camera_id)
        except Exception:
            logger.exception("Heartbeat loop error (camera=%s)", self._camera_id)
