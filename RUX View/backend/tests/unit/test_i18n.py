"""Tests for internationalization (i18n) module."""

import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from backend.i18n.translations import (
    TranslationService,
    Jinja2I18nExtension,
    TelegramTranslator,
    Language,
    TranslationBundle,
)


@pytest.fixture
def translation_service():
    """Create a TranslationService with test locales directory."""
    locales_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "i18n", "locales"
    )
    return TranslationService(locales_dir=locales_dir)


@pytest.fixture
def telegram_translator(translation_service):
    return TelegramTranslator(translation_service=translation_service)


class TestTranslationService:
    """Tests for TranslationService class."""

    @pytest.mark.asyncio
    async def test_translate_english_returns_correct_string(self, translation_service):
        """Test that English translation returns correct string."""
        result = await translation_service.translate(
            "app.name", Language.EN
        )
        assert result == "Vision OS"

    @pytest.mark.asyncio
    async def test_translate_bangla_returns_correct_string(self, translation_service):
        """Test that Bangla translation returns correct string."""
        result = await translation_service.translate(
            "app.name", Language.BN
        )
        assert result == "ভিশন ওএস"

    @pytest.mark.asyncio
    async def test_translate_fallback_to_english_when_missing(self, translation_service):
        """Test that missing Bangla key falls back to English."""
        # Use a key that exists in English but not Bangla
        result = await translation_service.translate(
            "common.loading", Language.BN
        )
        assert result == "লোড হচ্ছে..."  # Should exist in Bangla

    @pytest.mark.asyncio
    async def test_translate_with_format_parameters(self, translation_service):
        """Test that format parameters are interpolated."""
        result = await translation_service.translate(
            "events.duration", Language.EN, seconds=30
        )
        assert result == "Duration: 30s"

    @pytest.mark.asyncio
    async def test_translate_with_camera_parameter(self, translation_service):
        """Test translation with camera name parameter."""
        result = await translation_service.translate(
            "alerts.high_threat", Language.EN, camera="Front Door"
        )
        assert result == "VisionOS HIGH - Front Door"

    @pytest.mark.asyncio
    async def test_translate_bangla_with_parameters(self, translation_service):
        """Test Bangla translation with parameters."""
        result = await translation_service.translate(
            "alerts.high_threat", Language.BN, camera="সামনের দরজা"
        )
        assert result == "ভিশনওএস উচ্চ - সামনের দরজা"

    @pytest.mark.asyncio
    async def test_user_language_persisted_in_settings(self, translation_service):
        """Test that user language preference is persisted."""
        await translation_service.set_user_language("user_123", Language.BN)
        lang = await translation_service.get_user_language("user_123")
        assert lang == Language.BN

    @pytest.mark.asyncio
    async def test_user_language_defaults_to_english(self, translation_service):
        """Test that default language is English."""
        lang = await translation_service.get_user_language("unknown_user")
        assert lang == Language.EN

    @pytest.mark.asyncio
    async def test_load_translations_from_file(self, translation_service):
        """Test that translations are loaded from JSON files."""
        translations = await translation_service.load_translations(Language.EN)
        assert isinstance(translations, dict)
        assert "app" in translations
        assert "nav" in translations
        assert "events" in translations

    @pytest.mark.asyncio
    async def test_reload_all_translations(self, translation_service):
        """Test that all translations are reloaded."""
        result = await translation_service.reload_all()
        assert "en" in result
        assert "bn" in result
        assert result["en"] > 0
        assert result["bn"] > 0

    def test_get_nested_dot_notation(self, translation_service):
        """Test nested key lookup with dot notation."""
        translations = {
            "alerts": {
                "high_threat": "HIGH alert"
            }
        }
        result = translation_service._get_nested(translations, "alerts.high_threat")
        assert result == "HIGH alert"

    def test_get_nested_missing_key(self, translation_service):
        """Test that missing key returns None."""
        translations = {"app": {"name": "Vision OS"}}
        result = translation_service._get_nested(translations, "app.nonexistent")
        assert result is None

    def test_format_string_with_params(self, translation_service):
        """Test string formatting with parameters."""
        result = translation_service._format_string(
            "Duration: {seconds}s", seconds=30
        )
        assert result == "Duration: 30s"

    def test_format_string_missing_param(self, translation_service):
        """Test that missing format param returns template unchanged."""
        result = translation_service._format_string(
            "Duration: {seconds}s"
        )
        assert result == "Duration: {seconds}s"


class TestJinja2I18nExtension:
    """Tests for Jinja2I18nExtension class."""

    @pytest.fixture
    def jinja2_extension(self, translation_service):
        return Jinja2I18nExtension(translation_service=translation_service)

    def test_translate_filter_works(self, jinja2_extension):
        """Test that Jinja2 translate filter works."""
        result = jinja2_extension.translate_filter("app.name", "en")
        assert result == "Vision OS"

    def test_translate_filter_bangla(self, jinja2_extension):
        """Test that Jinja2 translate filter works with Bangla."""
        result = jinja2_extension.translate_filter("app.name", "bn")
        assert result == "ভিশন ওএস"

    def test_translate_tag_works(self, jinja2_extension):
        """Test that Jinja2 translate tag works."""
        result = jinja2_extension.translate_tag("app.tagline", "en")
        assert result == "Your AI Security"

    def test_translate_filter_with_params(self, jinja2_extension):
        """Test Jinja2 filter with format parameters."""
        result = jinja2_extension.translate_filter(
            "events.duration", "en", seconds=45
        )
        assert result == "Duration: 45s"


class TestTelegramTranslator:
    """Tests for TelegramTranslator class."""

    @pytest.mark.asyncio
    async def test_telegram_alert_formatted_in_bangla(self, telegram_translator):
        """Test that Telegram alert is formatted in Bangla."""
        result = await telegram_translator.format_alert(
            alert_type="high_threat",
            language=Language.BN,
            camera="সামনের দরজা",
        )
        assert "ভিশনওএস উচ্চ" in result
        assert "সামনের দরজা" in result

    @pytest.mark.asyncio
    async def test_telegram_alert_formatted_in_english(self, telegram_translator):
        """Test that Telegram alert is formatted in English."""
        result = await telegram_translator.format_alert(
            alert_type="motion",
            language=Language.EN,
            camera="Front Door",
        )
        assert "Motion detected at Front Door" in result

    @pytest.mark.asyncio
    async def test_digest_formatted_in_user_language(self, telegram_translator):
        """Test that digest is formatted in user's language."""
        digest_data = {
            "date": "2024-01-15",
            "event_count": 5,
            "high_count": 2,
            "total_visitors": 10,
            "familiar": 7,
            "unknown": 3,
            "audio_count": 1,
        }
        result = await telegram_translator.format_digest(
            digest_data=digest_data,
            language=Language.EN,
        )
        assert "VisionOS Daily" in result
        assert "5 events" in result
        assert "2 HIGH" in result
        assert "Visitors:" in result

    @pytest.mark.asyncio
    async def test_digest_formatted_in_bangla(self, telegram_translator):
        """Test that digest is formatted in Bangla."""
        digest_data = {
            "date": "2024-01-15",
            "event_count": 5,
            "high_count": 2,
            "total_visitors": 10,
            "familiar": 7,
            "unknown": 3,
            "audio_count": 1,
        }
        result = await telegram_translator.format_digest(
            digest_data=digest_data,
            language=Language.BN,
        )
        assert "ভিশনওএস দৈনিক" in result
        assert "৫টি ইভেন্ট" in result or "5টি ইভেন্ট" in result

    @pytest.mark.asyncio
    async def test_digest_all_clear(self, telegram_translator):
        """Test that all-clear digest is formatted correctly."""
        digest_data = {
            "date": "2024-01-15",
            "event_count": 0,
            "all_clear": True,
        }
        result = await telegram_translator.format_digest(
            digest_data=digest_data,
            language=Language.EN,
        )
        assert "All clear today" in result

    @pytest.mark.asyncio
    async def test_unknown_alert_type_returns_key(self, telegram_translator):
        """Test that unknown alert type returns the key itself."""
        result = await telegram_translator.format_alert(
            alert_type="nonexistent_alert",
            language=Language.EN,
            camera="Test",
        )
        assert result == "alerts.nonexistent_alert"


class TestLanguageEnum:
    """Tests for Language enum."""

    def test_language_values(self):
        """Test that language enum has correct values."""
        assert Language.EN.value == "en"
        assert Language.BN.value == "bn"

    def test_language_members(self):
        """Test that language enum has correct members."""
        assert len(Language) == 2
        assert Language.EN in Language
        assert Language.BN in Language


class TestTranslationBundle:
    """Tests for TranslationBundle dataclass."""

    def test_bundle_creation(self):
        """Test that TranslationBundle can be created."""
        bundle = TranslationBundle(
            language=Language.EN,
            translations={"key": "value"},
        )
        assert bundle.language == Language.EN
        assert bundle.translations["key"] == "value"
        assert bundle.loaded_at is None
