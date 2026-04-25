"""
groq_client.py — Vision OS Groq Audio Transcription Client

Handles Bangla audio transcription via Groq's Whisper-compatible API
(whisper-large-v3-turbo). All functions are async.

Replaces OpenAI Whisper per decision D003.
"""

import logging
from typing import Optional

from groq import AsyncGroq

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Module-level cache ─────────────────────────────────────────
_client: Optional[AsyncGroq] = None


def _get_client() -> AsyncGroq:
    """Lazy-init Groq async client singleton."""
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


# ── Transcription ──────────────────────────────────────────────


async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe Bangla audio using Groq Whisper-compatible API.

    Uses whisper-large-v3-turbo model for fast, accurate Bangla transcription.

    Args:
        audio_bytes: Raw audio bytes (WAV, MP3, etc.).

    Returns:
        Transcribed text string.

    Raises:
        Exception: If Groq API call fails (caller should handle).
    """
    if not audio_bytes or len(audio_bytes) == 0:
        logger.warning("Empty audio bytes received")
        return ""

    try:
        client = _get_client()
        # Groq's transcription API accepts file-like uploads
        # We pass the bytes with a filename hint for MIME detection
        transcription = await client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3-turbo",
            language="bn",  # Bangla
            response_format="text",
        )

        # The Groq SDK returns the transcript text directly
        # when response_format="text"
        if hasattr(transcription, "text"):
            result = transcription.text.strip()
        else:
            result = str(transcription).strip()

        logger.info("Groq transcription successful: %d chars", len(result))
        return result

    except Exception as exc:
        logger.error("Groq transcription failed: %s", exc, exc_info=True)
        raise
