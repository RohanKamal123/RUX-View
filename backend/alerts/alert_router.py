"""
alert_router.py — Route alerts by threat level + user tier.

Routing logic:
  LOW:       → Dashboard only, no Telegram
  MEDIUM:    → Telegram text message
  HIGH:      → Telegram photo + caption
  EMERGENCY: → Telegram urgent message + voice note
               Retry every 90s, max 3 attempts
               If no response → secondary contact
               If still no response → log as unacknowledged

During internet outage (HIGH only):
              → SSL Wireless SMS (~0.30 BDT)
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

RETRY_INTERVAL = 90  # seconds between retries
MAX_RETRIES = 3


@dataclass
class AlertAction:
    channel: str  # "log" / "telegram_text" / "telegram_photo" / "telegram_voice" / "sms"
    message: str
    jpeg_bytes: Optional[bytes] = None
    retry_count: int = 0
    acknowledged: bool = False


class AlertRouter:
    """Route alerts by threat level + user tier."""

    def __init__(self, telegram_client, voice_note_generator, sms_client):
        """Initialize with delivery channel clients.

        Args:
            telegram_client: TelegramClient instance.
            voice_note_generator: VoiceNoteGenerator instance.
            sms_client: SMSClient instance.
        """
        self.telegram = telegram_client
        self.voice = voice_note_generator
        self.sms = sms_client

    async def route_alert(self, incident: dict, user: dict, tier: str) -> AlertAction:
        """Route an alert based on threat level and user tier.

        Args:
            incident: Dict with threat_level, alert_message, person_ids, timeline, jpeg_bytes.
            user: User dict with telegram_chat_id, secondary_contact, etc.
            tier: User tier (free/household/business).

        Returns:
            AlertAction with delivery result.
        """
        threat_level = incident.get("threat_level", "LOW").upper()
        logger.info(
            "Routing alert: threat=%s, user=%s, tier=%s",
            threat_level, user.get("user_id"), tier,
        )

        if threat_level == "LOW":
            return await self._route_low(incident)

        if threat_level == "MEDIUM":
            return await self._route_medium(incident, user)

        if threat_level == "HIGH":
            return await self._route_high(incident, user)

        if threat_level == "EMERGENCY":
            return await self._route_emergency(incident, user)

        # Fallback: log only
        return AlertAction(channel="log", message="Unknown threat level: %s" % threat_level)

    async def _route_low(self, incident: dict) -> AlertAction:
        """LOW: Log only, no Telegram.

        Args:
            incident: Incident data dict.

        Returns:
            AlertAction with channel="log".
        """
        message = incident.get("alert_message", "Low threat incident")
        logger.info("LOW alert (log only): %s", message)
        return AlertAction(channel="log", message=message)

    async def _route_medium(self, incident: dict, user: dict) -> AlertAction:
        """MEDIUM: Telegram text message.

        Args:
            incident: Incident data dict.
            user: User dict with telegram_chat_id.

        Returns:
            AlertAction with channel="telegram_text".
        """
        chat_id = user.get("telegram_chat_id")
        if not chat_id:
            logger.warning("No telegram_chat_id for user, falling back to log")
            return AlertAction(channel="log", message=incident.get("alert_message", ""))

        camera_name = incident.get("camera_name", "Unknown Camera")
        timestamp = incident.get("timestamp", "Unknown Time")
        description = incident.get("alert_message", "Motion detected")

        message = self.telegram._format_medium_message(camera_name, timestamp, description)
        success = await self.telegram.send_text(chat_id, message)

        if success:
            logger.info("MEDIUM alert sent via Telegram text to %s", chat_id)
            return AlertAction(channel="telegram_text", message=message)
        else:
            logger.error("Failed to send MEDIUM Telegram text")
            return AlertAction(channel="log", message=message)

    async def _route_high(self, incident: dict, user: dict) -> AlertAction:
        """HIGH: Telegram photo + caption.

        Also sends SMS during internet outage (handled by caller).

        Args:
            incident: Incident data dict.
            user: User dict with telegram_chat_id.

        Returns:
            AlertAction with channel="telegram_photo".
        """
        chat_id = user.get("telegram_chat_id")
        if not chat_id:
            logger.warning("No telegram_chat_id for HIGH alert")
            return AlertAction(channel="log", message=incident.get("alert_message", ""))

        camera_name = incident.get("camera_name", "Unknown Camera")
        timestamp = incident.get("timestamp", "Unknown Time")
        description = incident.get("alert_message", "HIGH threat detected")
        jpeg_bytes = incident.get("jpeg_bytes")

        caption = self.telegram._format_high_message(camera_name, timestamp, description)

        if jpeg_bytes:
            success = await self.telegram.send_photo(chat_id, jpeg_bytes, caption)
        else:
            success = await self.telegram.send_text(chat_id, caption)

        if success:
            logger.info("HIGH alert sent via Telegram photo to %s", chat_id)
            return AlertAction(channel="telegram_photo", message=caption, jpeg_bytes=jpeg_bytes)
        else:
            logger.error("Failed to send HIGH Telegram alert")
            return AlertAction(channel="log", message=caption)

    async def _route_emergency(self, incident: dict, user: dict) -> AlertAction:
        """EMERGENCY: Telegram urgent + voice note + retry logic.

        Args:
            incident: Incident data dict.
            user: User dict with telegram_chat_id, secondary_contact.

        Returns:
            AlertAction after retry attempts.
        """
        chat_id = user.get("telegram_chat_id")
        if not chat_id:
            logger.warning("No telegram_chat_id for EMERGENCY alert")
            return AlertAction(channel="log", message=incident.get("alert_message", ""))

        camera_name = incident.get("camera_name", "Unknown Camera")
        timestamp = incident.get("timestamp", "Unknown Time")
        description = incident.get("alert_message", "EMERGENCY threat!")
        sighting_count = incident.get("sighting_count", 1)
        jpeg_bytes = incident.get("jpeg_bytes")

        text_message = self.telegram._format_emergency_message(
            camera_name, timestamp, description, sighting_count
        )

        # Send the alert with retry
        async def send_emergency():
            # Send text first
            text_ok = await self.telegram.send_text(chat_id, text_message)
            # Send photo if available
            photo_ok = True
            if jpeg_bytes:
                photo_ok = await self.telegram.send_photo(
                    chat_id, jpeg_bytes, text_message[:200]
                )
            # Generate and send voice note
            voice_ok = False
            try:
                voice_bytes = await self.voice.generate_voice_note(
                    camera_name, timestamp, description
                )
                if voice_bytes:
                    voice_ok = await self.telegram.send_voice(
                        chat_id, voice_bytes, text_message[:100]
                    )
            except Exception as exc:
                logger.error("Voice note generation/send failed: %s", exc)

            return text_ok and (photo_ok or voice_ok)

        action = await self._retry_with_escalation(send_emergency, incident, user)
        return action

    async def _retry_with_escalation(self, send_func, incident: dict,
                                      user: dict) -> AlertAction:
        """Retry delivery with secondary contact escalation.

        Args:
            send_func: Async callable that returns True on success.
            incident: Incident data dict.
            user: User dict with secondary_contact.

        Returns:
            AlertAction after retry attempts.
        """
        message = incident.get("alert_message", "Emergency alert")

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("Emergency alert retry attempt %d/%d", attempt, MAX_RETRIES)

            success = await send_func()

            if success:
                logger.info("Emergency alert delivered on attempt %d", attempt)
                return AlertAction(
                    channel="telegram_voice",
                    message=message,
                    retry_count=attempt,
                    acknowledged=True,
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_INTERVAL)

        # All retries failed — try secondary contact
        secondary = user.get("secondary_contact")
        if secondary:
            logger.info("Escalating to secondary contact: %s", secondary)
            secondary_chat_id = secondary.get("telegram_chat_id")
            if secondary_chat_id:
                secondary_msg = (
                    f"Primary contact unreachable for EMERGENCY alert.\n"
                    f"{message}"
                )
                await self.telegram.send_text(secondary_chat_id, secondary_msg)

        logger.error("Emergency alert undelivered after %d attempts", MAX_RETRIES)
        return AlertAction(
            channel="log",
            message=message,
            retry_count=MAX_RETRIES,
            acknowledged=False,
        )
