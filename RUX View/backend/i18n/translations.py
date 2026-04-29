"""Internationalization (i18n) module for Vision OS.

Provides translation services for multi-language support with English
and Bangla. Includes Jinja2 template extension and Telegram alert
translation helpers.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import json
import logging
import os

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages."""
    EN = "en"
    BN = "bn"


@dataclass
class TranslationBundle:
    """A loaded translation bundle for a language."""
    language: Language
    translations: dict = field(default_factory=dict)
    loaded_at: Optional[float] = None


class TranslationService:
    """Translation service for multi-language support.

    Loads JSON translation files and provides translation lookups
    with dot-notation key support and format parameter interpolation.
    Falls back to English when a translation key is missing.
    """

    def __init__(self, locales_dir: str = "./backend/i18n/locales"):
        """Initialize translation service.

        Args:
            locales_dir: Directory containing JSON translation files
        """
        self.locales_dir = locales_dir
        self._bundles: dict[Language, TranslationBundle] = {}
        self._user_languages: dict[str, Language] = {}

    async def translate(self, key: str, language: Language,
                         **kwargs) -> str:
        """Translate a key to the specified language.

        Args:
            key: Translation key (e.g. "alerts.high_threat")
            language: Target language
            **kwargs: Format parameters

        Returns:
            Translated string (falls back to English)
        """
        # Load translations if not cached
        if language not in self._bundles:
            await self.load_translations(language)

        bundle = self._bundles.get(language)
        if not bundle:
            return key

        # Try to get the translation
        value = self._get_nested(bundle.translations, key)

        # Fall back to English
        if value is None and language != Language.EN:
            if Language.EN not in self._bundles:
                await self.load_translations(Language.EN)
            en_bundle = self._bundles.get(Language.EN)
            if en_bundle:
                value = self._get_nested(en_bundle.translations, key)

        # Return key if no translation found
        if value is None:
            return key

        # Format with parameters
        return self._format_string(value, **kwargs)

    async def get_user_language(self, user_id: str) -> Language:
        """Get user's preferred language from settings.

        Args:
            user_id: User ID

        Returns:
            Language enum
        """
        return self._user_languages.get(user_id, Language.EN)

    async def set_user_language(self, user_id: str,
                                 language: Language) -> None:
        """Set user's preferred language.

        Args:
            user_id: User ID
            language: Language to set
        """
        self._user_languages[user_id] = language

    async def load_translations(self, language: Language) -> dict:
        """Load translation file for a language.

        Args:
            language: Language to load

        Returns:
            Dict of translation key-value pairs
        """
        file_path = os.path.join(self.locales_dir, f"{language.value}.json")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                translations = json.load(f)

            import time
            self._bundles[language] = TranslationBundle(
                language=language,
                translations=translations,
                loaded_at=time.time(),
            )
            return translations

        except FileNotFoundError:
            logger.warning(f"Translation file not found: {file_path}")
            self._bundles[language] = TranslationBundle(
                language=language,
                translations={},
            )
            return {}

        except json.JSONDecodeError as e:
            logger.error(f"Invalid translation file {file_path}: {e}")
            return {}

    async def reload_all(self) -> dict:
        """Reload all translation files.

        Returns:
            Dict with language codes as keys and translation counts as values
        """
        result = {}
        for language in Language:
            translations = await self.load_translations(language)
            result[language.value] = len(translations)
        return result

    def _get_nested(self, translations: dict, key: str) -> Optional[str]:
        """Get nested translation value using dot notation.

        Example: "alerts.high_threat" -> translations["alerts"]["high_threat"]

        Args:
            translations: Translation dict
            key: Dot-notation key

        Returns:
            Translation value or None
        """
        parts = key.split(".")
        current = translations

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current if isinstance(current, str) else None

    def _format_string(self, template: str, **kwargs) -> str:
        """Format a translation string with parameters.

        Uses Python string formatting.

        Args:
            template: Template string with {param} placeholders
            **kwargs: Format parameters

        Returns:
            Formatted string
        """
        try:
            return template.format(**kwargs)
        except KeyError:
            return template


class Jinja2I18nExtension:
    """Jinja2 extension for template translation.

    Provides translate filter and tag for use in Jinja2 templates.
    Uses synchronous translation lookup for Jinja2 compatibility.
    """

    def __init__(self, translation_service: TranslationService):
        """Initialize Jinja2 i18n extension.

        Args:
            translation_service: TranslationService instance
        """
        self.translation_service = translation_service
        # Pre-load translations synchronously for Jinja2 use
        self._sync_translations: dict[str, dict] = {}
        self._load_sync_translations()

    def _load_sync_translations(self) -> None:
        """Pre-load translations synchronously for Jinja2 template use."""
        import json
        import os

        for lang_code in ("en", "bn"):
            file_path = os.path.join(
                self.translation_service.locales_dir, f"{lang_code}.json"
            )
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._sync_translations[lang_code] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                self._sync_translations[lang_code] = {}

    def _get_sync_translation(self, key: str, language: str = "en",
                               **kwargs) -> str:
        """Get translation synchronously for Jinja2 templates.

        Args:
            key: Translation key with dot notation
            language: Language code ("en" or "bn")
            **kwargs: Format parameters

        Returns:
            Translated string
        """
        # Try requested language
        translations = self._sync_translations.get(language, {})
        parts = key.split(".")
        current = translations

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break

        # Fall back to English
        if current is None and language != "en":
            translations = self._sync_translations.get("en", {})
            current = translations
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = None
                    break

        if current is None or not isinstance(current, str):
            return key

        # Format with parameters
        try:
            return current.format(**kwargs)
        except KeyError:
            return current

    def translate_filter(self, key: str, language: str = "en",
                          **kwargs) -> str:
        """Jinja2 filter: {{ "alerts.high_threat" | translate(lang) }}

        Args:
            key: Translation key
            language: Language code
            **kwargs: Format parameters

        Returns:
            Translated string
        """
        return self._get_sync_translation(key, language, **kwargs)

    def translate_tag(self, key: str, language: str = "en",
                       **kwargs) -> str:
        """Jinja2 tag: {% t "alerts.high_threat" lang=user.lang %}

        Args:
            key: Translation key
            language: Language code
            **kwargs: Format parameters

        Returns:
            Translated string
        """
        return self._get_sync_translation(key, language, **kwargs)


class TelegramTranslator:
    """Translate Telegram alerts to user's language.

    Formats alert messages and digests in the user's preferred language.
    """

    def __init__(self, translation_service: TranslationService):
        """Initialize Telegram translator.

        Args:
            translation_service: TranslationService instance
        """
        self.translation_service = translation_service

    async def format_alert(self, alert_type: str,
                            language: Language,
                            **context) -> str:
        """Format a Telegram alert in the user's language.

        Args:
            alert_type: Type of alert (e.g. "high_threat", "motion")
            language: Target language
            context: Alert context (camera name, time, etc.)

        Returns:
            Formatted alert string
        """
        key = f"alerts.{alert_type}"
        return await self.translation_service.translate(key, language, **context)

    async def format_digest(self, digest_data: dict,
                             language: Language) -> str:
        """Format a digest in the user's language.

        Args:
            digest_data: Digest data dict
            language: Target language

        Returns:
            Plain text digest in target language
        """
        lines = []

        # Title
        if "date" in digest_data:
            title = await self.translation_service.translate(
                "digest.daily_title", language, **digest_data
            )
            lines.append(f"*{title}*")
            lines.append("")

        # Events summary
        if "event_count" in digest_data:
            events_text = await self.translation_service.translate(
                "digest.events", language, count=digest_data["event_count"]
            )
            lines.append(f"📊 {events_text}")

        # High alerts
        if "high_count" in digest_data and digest_data["high_count"] > 0:
            high_text = await self.translation_service.translate(
                "digest.high_count", language, count=digest_data["high_count"]
            )
            lines.append(f"🔴 {high_text}")

        # Visitors
        if all(k in digest_data for k in ("total_visitors", "familiar", "unknown")):
            visitors_text = await self.translation_service.translate(
                "digest.visitors", language,
                total=digest_data["total_visitors"],
                familiar=digest_data["familiar"],
                unknown=digest_data["unknown"],
            )
            lines.append(f"👥 {visitors_text}")

        # Audio alerts
        if "audio_count" in digest_data and digest_data["audio_count"] > 0:
            audio_text = await self.translation_service.translate(
                "digest.audio", language, count=digest_data["audio_count"]
            )
            lines.append(f"🔊 {audio_text}")

        # All clear
        if digest_data.get("all_clear", False):
            all_clear = await self.translation_service.translate(
                "digest.all_clear", language
            )
            lines.append(f"✅ {all_clear}")

        return "\n".join(lines)
