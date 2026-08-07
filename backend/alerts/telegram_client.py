"""
telegram_client.py — Telegram Bot API client for sending alerts.

Plain text format (NO markdown — timestamp underscores break markdown).
Supports text, photo, and voice note messages.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramClient:
    """Telegram Bot API client for sending alerts."""

    def __init__(self, bot_token: str):
        """Initialize Telegram bot.

        Args:
            bot_token: Bot token from @BotFather.
        """
        self.bot_token = bot_token
        self.api_base = f"{TELEGRAM_API_BASE}{bot_token}"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Timeout is read from config_store's telegram_timeout_sec once, when
        the client is first built (not on every call — the client is then
        reused for the lifetime of this TelegramClient instance, matching
        the existing lazy-singleton pattern).
        """
        if self._client is None:
            timeout = 30.0
            try:
                from backend.core.config_store import get_telegram_timeout
                timeout = await get_telegram_timeout()
            except Exception as exc:
                logger.warning("Failed to read telegram_timeout_sec config, using default: %s", exc)
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def send_text(self, chat_id: str, message: str) -> bool:
        """Send plain text message.

        NO markdown formatting (timestamp underscores break markdown).

        Args:
            chat_id: Telegram chat ID.
            message: Plain text message.

        Returns:
            True if sent successfully.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "",  # Explicitly no markdown
                },
            )
            data = response.json()
            if not data.get("ok"):
                logger.error("Telegram send_text failed: %s", data.get("description"))
                return False
            return True
        except Exception as exc:
            logger.error("Telegram send_text error: %s", exc, exc_info=True)
            return False

    async def send_photo(self, chat_id: str, jpeg_bytes: bytes,
                          caption: str) -> bool:
        """Send photo with caption.

        Args:
            chat_id: Telegram chat ID.
            jpeg_bytes: JPEG image bytes.
            caption: Plain text caption.

        Returns:
            True if sent successfully.
        """
        try:
            client = await self._get_client()
            files = {"photo": ("frame.jpg", jpeg_bytes, "image/jpeg")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": ""}
            response = await client.post(
                f"{self.api_base}/sendPhoto",
                data=data,
                files=files,
            )
            result = response.json()
            if not result.get("ok"):
                logger.error("Telegram send_photo failed: %s", result.get("description"))
                return False
            return True
        except Exception as exc:
            logger.error("Telegram send_photo error: %s", exc, exc_info=True)
            return False

    async def send_voice(self, chat_id: str, ogg_bytes: bytes,
                          caption: str) -> bool:
        """Send voice note (OGG Opus) with caption.

        Args:
            chat_id: Telegram chat ID.
            ogg_bytes: OGG Opus audio bytes.
            caption: Plain text caption.

        Returns:
            True if sent successfully.
        """
        try:
            client = await self._get_client()
            files = {"voice": ("voice.ogg", ogg_bytes, "audio/ogg")}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": ""}
            response = await client.post(
                f"{self.api_base}/sendVoice",
                data=data,
                files=files,
            )
            result = response.json()
            if not result.get("ok"):
                logger.error("Telegram send_voice failed: %s", result.get("description"))
                return False
            return True
        except Exception as exc:
            logger.error("Telegram send_voice error: %s", exc, exc_info=True)
            return False

    def _format_medium_message(self, camera_name: str, timestamp: str,
                                description: str) -> str:
        """Format MEDIUM alert message.

        Format:
        VisionOS MEDIUM - {camera_name} - {timestamp}
        {description}
        Camera: {camera_name}
        """
        return (
            f"VisionOS MEDIUM - {camera_name} - {timestamp}\n"
            f"{description}\n"
            f"Camera: {camera_name}"
        )

    def _format_high_message(self, camera_name: str, timestamp: str,
                              description: str) -> str:
        """Format HIGH alert message.

        Format:
        VisionOS HIGH ALERT - {camera_name} - {timestamp}
        {description}
        """
        return (
            f"VisionOS HIGH ALERT - {camera_name} - {timestamp}\n"
            f"{description}"
        )

    def _format_emergency_message(self, camera_name: str, timestamp: str,
                                   description: str, sighting_count: int) -> str:
        """Format EMERGENCY alert message.

        Format:
        VisionOS EMERGENCY - {camera_name} - {timestamp}
        {description}
        {sighting_count}th sighting today
        """
        return (
            f"VisionOS EMERGENCY - {camera_name} - {timestamp}\n"
            f"{description}\n"
            f"{sighting_count}th sighting today"
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
