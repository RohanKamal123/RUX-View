"""Pytest configuration for Vision OS tests."""

import pytest
import os

# ── Test Environment ─────────────────────────────────────────
# Use test environment variables. "development" (not "test") because
# backend/dashboard/auth.py's dev-mode Firebase bypass only recognizes
# "development" -- the codebase has no separate "test" environment
# concept, so setting anything else here made auth fall through to the
# production path (which requires real Firebase creds) for every test.
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/visionos_test"
)
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://fake-redis.invalid")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def _reset_redis_singleton():
    """Reset the cached Upstash Redis client before every test.

    backend/core/redis_client.py caches its client in a bare module-level
    global with no per-test isolation. Whichever test happens to touch it
    first (e.g. by booting the FastAPI app) locks in that moment's
    settings.upstash_* values for the rest of the pytest process, silently
    breaking unrelated later tests depending on run order. Autouse so every
    test starts from a clean slate regardless of what ran before it.
    """
    from backend.core.redis_client import reset_redis_client

    reset_redis_client()
    yield
    reset_redis_client()


@pytest.fixture(autouse=True)
def _fake_get_redis_client():
    """Make every get_redis_client() call return instantly.

    config_store.get_config() (and therefore every config_store.get_*
    convenience accessor — get_max_cameras() etc.) fails open on Redis
    errors, but "fails open" still means it first tries a real network
    call against UPSTASH_REDIS_REST_URL. The upstash_redis client retries
    once with a 3s interval before giving up, so against the placeholder
    URL set above that's ~10+ real seconds *per call* — multiplied by
    every route/method that now reads config_store (dashboard pages,
    camera quota, cleanup, the pipeline...), full-file test runs were
    taking minutes.

    Patches EVERY module that imports get_redis_client via
    `from backend.core.redis_client import get_redis_client` — a plain
    `import backend.core.redis_client` patch only affects callers that
    look it up as an attribute at call time (redis_client.get_redis_client()),
    not modules that did `from ... import get_redis_client` at their own
    import time, which copies the reference into their own namespace
    before this fixture ever runs. Same gotcha as pipeline_v2._get_config
    in test_pipeline_dry_run.py's mock_config_store fixture — see that
    comment. Add new modules here if they start importing it the same way.

    Tests that want to exercise real Redis behavior (e.g. tracker state)
    already construct and inject their own mock/real client directly
    rather than going through this singleton, so overriding it here
    doesn't affect them.
    """
    from unittest.mock import AsyncMock, patch
    import backend.core.redis_client as redis_client_module

    fake = AsyncMock()
    fake.get = AsyncMock(return_value=None)
    fake.set = AsyncMock(return_value=True)
    fake.delete = AsyncMock(return_value=1)
    fake.hgetall = AsyncMock(return_value={})
    fake.hset = AsyncMock(return_value=1)
    fake.expire = AsyncMock(return_value=True)

    async def _fake_get_redis_client():
        return fake

    patch_targets = ["backend.core.redis_client.get_redis_client"]
    # Modules that copy the reference via `from ... import get_redis_client`
    # at their own import time — patching the source module alone doesn't
    # reach these once they've been imported once in the pytest process.
    for module_path in ["backend.core.config_store"]:
        try:
            module = __import__(module_path, fromlist=["get_redis_client"])
            if hasattr(module, "get_redis_client"):
                patch_targets.append(f"{module_path}.get_redis_client")
        except ImportError:
            pass

    patchers = [patch(target, _fake_get_redis_client) for target in patch_targets]
    for p in patchers:
        p.start()
    yield fake
    for p in patchers:
        p.stop()


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
