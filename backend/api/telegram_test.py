"""
telegram_test.py — Telegram diagnostic endpoint for Vision OS.

Provides GET /api/test/telegram that sends a real test message
using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from settings,
and returns the full API response for debugging.
"""

import logging
from fastapi import APIRouter

from backend.config import settings
from backend.alerts.telegram_client import TelegramClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["test"])


@router.get("/telegram")
async def test_telegram():
    """Send a test Telegram message and return the full API response.

    This endpoint is for debugging Telegram connectivity issues.
    It logs clearly if the token is missing, wrong, or if the
    Telegram API returns an error.

    Returns:
        Dict with success status, message, and detailed API response.
    """
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    # ── Check if token is configured ────────────────────────────
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is MISSING — not configured in environment")
        return {
            "success": False,
            "error": "TELEGRAM_BOT_TOKEN is not configured",
            "token_present": False,
            "chat_id_present": bool(chat_id),
        }

    if not chat_id:
        logger.error("TELEGRAM_CHAT_ID is MISSING — not configured in environment")
        return {
            "success": False,
            "error": "TELEGRAM_CHAT_ID is not configured",
            "token_present": True,
            "chat_id_present": False,
        }

    logger.info(
        "Telegram test: token=%s..., chat_id=%s",
        bot_token[:8] + "..." if len(bot_token) > 8 else "SET",
        chat_id,
    )

    # ── Send test message ───────────────────────────────────────
    client = TelegramClient(bot_token=bot_token)
    try:
        # Use the underlying httpx client to get the raw API response
        http_client = await client._get_client()
        response = await http_client.post(
            f"{client.api_base}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "VisionOS test message — if you see this, Telegram is working!",
                "parse_mode": "",
            },
        )
        data = response.json()
        status_code = response.status_code

        logger.info(
            "Telegram API response: status=%d, ok=%s, description=%s",
            status_code,
            data.get("ok"),
            data.get("description", "N/A"),
        )

        if data.get("ok"):
            logger.info("Telegram test SUCCESS — message sent to chat %s", chat_id)
            return {
                "success": True,
                "message": "Test Telegram message sent successfully",
                "api_status_code": status_code,
                "api_response": data,
                "token_present": True,
                "chat_id_present": True,
            }
        else:
            error_desc = data.get("description", "Unknown error")
            logger.error("Telegram API returned error: %s", error_desc)
            return {
                "success": False,
                "error": f"Telegram API error: {error_desc}",
                "api_status_code": status_code,
                "api_response": data,
                "token_present": True,
                "chat_id_present": True,
            }

    except Exception as exc:
        logger.error("Telegram test failed with exception: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": f"Exception: {str(exc)}",
            "exception_type": type(exc).__name__,
            "token_present": True,
            "chat_id_present": True,
        }
    finally:
        await client.close()
