"""
config.py — Centralized configuration for Vision OS.

Uses Pydantic Settings to load environment variables from .env file.
All API keys, database URLs, and app settings are defined here.

Usage:
    from backend.config import settings

    # Access any setting
    db_url = settings.database_url
    gemini_key = settings.gemini_api_key
    groq_key = settings.groq_api_key
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/visionos"

    # ── AI APIs ─────────────────────────────────────────────────

    gemini_api_key: str = "AIzaSyCZMS2WlRsTesfgoV7WX6kyKj0WjcOAp7A"

    groq_api_key: str = "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"

    # ── Firebase Auth ───────────────────────────────────────────
    firebase_credentials_path: str = "./firebase-service-account.json"

    # ── Telegram ────────────────────────────────────────────────
    telegram_bot_token: str = "8209307824:AAHd9TfVzzCVp54Cm_55xi9i7fQCa1NzBhE"
    telegram_chat_id: str = "-1001945678901"

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

    # ── Application ─────────────────────────────────────────────
    secret_key: str = ""
    environment: str = "development"
    log_level: str = "INFO"

    # ── Google Cloud (for deployment) ──────────────────────────
    google_cloud_project: str = ""
    google_cloud_region: str = "asia-south1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global singleton — import this everywhere
settings = Settings()
