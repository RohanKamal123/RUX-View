"""
Tests for Sprint 3.5 — Alert Router + Telegram + Voice Notes + SMS.

Tests routing logic, message formatting, and delivery channels.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.alerts.alert_router import AlertRouter, AlertAction
from backend.alerts.telegram_client import TelegramClient
from backend.alerts.sms_client import SMSClient


class TestAlertRouter:
    @pytest.mark.asyncio
    async def test_low_threat_logs_only(self):
        """LOW threat should return log channel."""
        router = AlertRouter(
            telegram_client=MagicMock(),
            voice_note_generator=MagicMock(),
            sms_client=MagicMock(),
        )
        incident = {"threat_level": "LOW", "alert_message": "Test low alert"}
        user = {"user_id": "user-001"}
        action = await router._route_low(incident)
        assert action.channel == "log"

    @pytest.mark.asyncio
    async def test_medium_sends_telegram_text(self):
        """MEDIUM threat should send Telegram text."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_text = AsyncMock(return_value=True)
        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=MagicMock(),
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "MEDIUM",
            "alert_message": "Suspicious person",
            "camera_name": "Front Gate",
            "timestamp": "2024-01-01T12:00:00",
        }
        user = {"telegram_chat_id": "123456"}

        action = await router._route_medium(incident, user)
        assert action.channel == "telegram_text"
        telegram.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_medium_no_chat_id_falls_back_to_log(self):
        """MEDIUM without chat_id should fall back to log."""
        router = AlertRouter(
            telegram_client=MagicMock(),
            voice_note_generator=MagicMock(),
            sms_client=MagicMock(),
        )
        incident = {"alert_message": "Test", "threat_level": "MEDIUM"}
        user = {}  # No telegram_chat_id

        action = await router._route_medium(incident, user)
        assert action.channel == "log"

    @pytest.mark.asyncio
    async def test_high_sends_telegram_photo(self):
        """HIGH threat should send Telegram photo."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_photo = AsyncMock(return_value=True)
        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=MagicMock(),
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "HIGH",
            "alert_message": "Intruder detected",
            "camera_name": "Back Door",
            "timestamp": "2024-01-01T13:00:00",
            "jpeg_bytes": b"fake_jpeg_data",
        }
        user = {"telegram_chat_id": "123456"}

        action = await router._route_high(incident, user)
        assert action.channel == "telegram_photo"
        telegram.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_high_no_jpeg_sends_text(self):
        """HIGH without JPEG should send text."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_text = AsyncMock(return_value=True)
        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=MagicMock(),
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "HIGH",
            "alert_message": "Alert",
            "camera_name": "Camera",
            "timestamp": "2024-01-01T14:00:00",
        }
        user = {"telegram_chat_id": "123456"}

        action = await router._route_high(incident, user)
        assert action.channel == "telegram_photo"
        telegram.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_emergency_sends_voice_note(self):
        """EMERGENCY should attempt voice note delivery."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_text = AsyncMock(return_value=True)
        telegram.send_photo = AsyncMock(return_value=True)
        telegram.send_voice = AsyncMock(return_value=True)

        voice = MagicMock()
        voice.generate_voice_note = AsyncMock(return_value=b"fake_ogg_data")

        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=voice,
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "EMERGENCY",
            "alert_message": "BREAK-IN",
            "camera_name": "Main Door",
            "timestamp": "2024-01-01T03:00:00",
            "sighting_count": 4,
        }
        user = {"telegram_chat_id": "123456"}

        action = await router._route_emergency(incident, user)
        assert action.channel == "telegram_voice"
        assert action.acknowledged is True

    @pytest.mark.asyncio
    async def test_retry_on_telegram_failure(self):
        """Retry logic should attempt multiple times."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_text = AsyncMock(return_value=False)
        telegram.send_photo = AsyncMock(return_value=False)
        telegram.send_voice = AsyncMock(return_value=False)

        voice = MagicMock()
        voice.generate_voice_note = AsyncMock(return_value=b"fake_ogg_data")

        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=voice,
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "EMERGENCY",
            "alert_message": "Test",
            "camera_name": "Camera",
            "timestamp": "2024-01-01T00:00:00",
        }
        user = {"telegram_chat_id": "123456"}

        action = await router._retry_with_escalation(
            lambda: telegram.send_text("123456", "test"), incident, user
        )
        assert action.acknowledged is False
        assert action.retry_count == 3  # MAX_RETRIES

    @pytest.mark.asyncio
    async def test_secondary_contact_escalation(self):
        """Secondary contact should be notified after retries fail."""
        telegram = AsyncMock(spec=TelegramClient)
        telegram.send_text = AsyncMock(return_value=False)
        telegram.send_photo = AsyncMock(return_value=False)
        telegram.send_voice = AsyncMock(return_value=False)

        voice = MagicMock()
        voice.generate_voice_note = AsyncMock(return_value=b"fake_ogg_data")

        router = AlertRouter(
            telegram_client=telegram,
            voice_note_generator=voice,
            sms_client=MagicMock(),
        )
        incident = {
            "threat_level": "EMERGENCY",
            "alert_message": "Test",
            "camera_name": "Camera",
            "timestamp": "2024-01-01T00:00:00",
        }
        user = {
            "telegram_chat_id": "123456",
            "secondary_contact": {"telegram_chat_id": "789012"},
        }

        await router._retry_with_escalation(
            lambda: telegram.send_text("123456", "test"), incident, user
        )
        # Should have attempted to notify secondary contact
        assert telegram.send_text.call_count > 3

    def test_plain_text_no_markdown(self):
        """Messages should not contain markdown formatting."""
        telegram = TelegramClient(bot_token="test_token")
        msg = telegram._format_medium_message(
            "Cam_01", "2024-01-01_12:00:00", "Test description"
        )
        # No markdown characters
        assert "*" not in msg
        assert "`" not in msg

    def test_alert_format_messages(self):
        """Alert messages should follow expected format."""
        telegram = TelegramClient(bot_token="test_token")

        medium = telegram._format_medium_message(
            "Front_Gate", "2024-01-01 12:00:00", "Suspicious activity"
        )
        assert "VisionOS MEDIUM" in medium
        assert "Front_Gate" in medium
        assert "Suspicious activity" in medium

        high = telegram._format_high_message(
            "Back_Door", "2024-01-01 13:00:00", "Breaking and entering"
        )
        assert "VisionOS HIGH ALERT" in high
        assert "Back_Door" in high
        assert "Breaking and entering" in high

        emergency = telegram._format_emergency_message(
            "Main_Gate", "2024-01-01 03:00:00", "Armed intruder", 4
        )
        assert "VisionOS EMERGENCY" in emergency
        assert "Main_Gate" in emergency
        assert "4th sighting" in emergency


class TestTelegramClient:
    def test_format_medium_message(self):
        """Medium message format should be correct."""
        client = TelegramClient("fake_token")
        msg = client._format_medium_message(
            "Front Gate", "2024-01-01 12:00:00", "Person loitering"
        )
        lines = msg.split("\n")
        assert lines[0].startswith("VisionOS MEDIUM")
        assert lines[1] == "Person loitering"
        assert lines[2].startswith("Camera:")

    def test_format_high_message(self):
        """High message format should be correct."""
        client = TelegramClient("fake_token")
        msg = client._format_high_message(
            "Back Door", "2024-01-01 13:00:00", "Breaking in"
        )
        assert msg.startswith("VisionOS HIGH ALERT")

    def test_format_emergency_message(self):
        """Emergency message format should include sighting count."""
        client = TelegramClient("fake_token")
        msg = client._format_emergency_message(
            "Main Door", "2024-01-01 03:00:00", "Intruder", 4
        )
        assert "4th sighting today" in msg


class TestSMSClient:
    def test_sms_initialization(self):
        """SMSClient should initialize with API credentials."""
        client = SMSClient("api_key_123", "api_secret_456", "VisionOS")
        assert client.api_key == "api_key_123"
        assert client.api_secret == "api_secret_456"
        assert client.sender_id == "VisionOS"
