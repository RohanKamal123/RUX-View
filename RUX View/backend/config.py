"""
config.py — Centralized configuration for Vision OS.

Uses Pydantic Settings to load environment variables from .env file.
All API keys, database URLs, and app settings are defined here.

Usage:
    from backend.config import settings

    # Access any setting
    db_url = settings.database_url
    gemini_key = settings.gemini_api_key
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database (Neon PostgreSQL + pgvector) ──────────────────
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/visionos"

    # ── AI APIs ─────────────────────────────────────────────────
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # ── Firebase Auth ───────────────────────────────────────────
    firebase_credentials_path: str = ""
    firebase_credentials_json: str = ""  # Inline JSON for production

    # ── Telegram ────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── SMS (SSL Wireless Bangladesh) ──────────────────────────
    ssl_wireless_api_key: str = ""
    ssl_wireless_api_secret: str = ""
    ssl_wireless_sid: str = ""

    # ── bKash Billing ───────────────────────────────────────────
    bkash_app_key: str = "01751549994"
    bkash_app_secret: str = ""
    bkash_username: str = ""
    bkash_password: str = ""
    bkash_sandbox: bool = True
    bkash_number: str = ""

    # ── Application ─────────────────────────────────────────────
    secret_key: str = ""
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"

    # ── Google Cloud (for deployment) ──────────────────────────
    google_cloud_project: str = ""
    google_cloud_region: str = "asia-south1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global singleton — import this everywhere
settings = Settings()
