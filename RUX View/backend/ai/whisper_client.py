"""
whisper_client.py — OpenAI Whisper API client for Vision OS.

Handles Bangla audio transcription using OpenAI Whisper API (whisper-1).
All functions are async.
"""

import os
from io import BytesIO
from typing import Optional

from openai import AsyncOpenAI

# ── Configuration ─────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Lazy-load the OpenAI async client singleton."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


# ── Transcription ─────────────────────────────────────────────


async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using OpenAI Whisper API.

    Args:
        audio_bytes: Raw audio bytes (WAV, MP3, etc.).

    Returns:
        Transcribed text string. For Bangla audio, returns Bangla text.

    Raises:
        Exception: If transcription fails.
    """
    client = _get_client()

    # Create a file-like object from bytes
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.wav"

    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="bn",  # Bangla
        response_format="text",
    )

    return response.strip()
