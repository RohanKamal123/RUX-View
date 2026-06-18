"""Pytest configuration for Vision OS tests."""

import pytest
import os

# ── Test Environment ─────────────────────────────────────────
# Use test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/visionos_test"
)
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-key"


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Return minimal valid JPEG bytes for testing."""
    # Minimal 1x1 JPEG
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
        b"\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
        b"\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00"
        b"\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01"
        b"\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03"
        b"\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03"
        b"\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x00\x01\x02\x03\x00"
        b'\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1'
        b"\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJST"
        b"UVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95"
        b"\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4"
        b"\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3"
        b"\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea"
        b"\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc0\x00\x1f\x01\x01\x01"
        b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
        b"\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04"
        b"\x03\x04\x07\x05\x04\x04\x00\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04"
        b'\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0'
        b"\x15br\xd1\n\x16$4\xe1%\xf1\x17\x18\x19\x1a&'()*56789:CDEFGHIJSTUVWXYZ"
        b"cdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95"
        b"\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4"
        b"\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3"
        b"\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2"
        b"\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xd9"
    )


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Return minimal valid WAV bytes for testing."""
    import struct
    import math

    sample_rate = 16000
    duration = 0.5  # 0.5 seconds
    num_samples = int(sample_rate * duration)

    # Generate a simple sine wave
    samples = []
    for i in range(num_samples):
        sample = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        samples.append(struct.pack("<h", sample))

    data = b"".join(samples)
    data_size = len(data)

    # WAV header
    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)  # chunk size
    header += struct.pack("<H", 1)  # PCM
    header += struct.pack("<H", 1)  # mono
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", sample_rate * 2)  # byte rate
    header += struct.pack("<H", 2)  # block align
    header += struct.pack("<H", 16)  # bits per sample
    header += b"data"
    header += struct.pack("<I", data_size)

    return header + data


@pytest.fixture
def mock_user_dict() -> dict:
    """Return a mock authenticated user."""
    return {
        "uid": "test-user-123",
        "email": "test@example.com",
        "tier": "household",
        "subscription_active": True,
    }


@pytest.fixture
def mock_free_user_dict() -> dict:
    """Return a mock free-tier user."""
    return {
        "uid": "test-user-free-456",
        "email": "free@example.com",
        "tier": "free",
        "subscription_active": False,
    }
