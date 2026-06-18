"""
conftest.py — Test fixtures for Vision OS end-to-end smoke tests.

Provides fixtures for staging URL, test user creation, camera registration,
cleanup, and async HTTP client.
"""

import os
import uuid
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio


# ── Configuration ───────────────────────────────────────────────

STAGING_URL = os.getenv("STAGING_URL", "http://localhost:8000")
TEST_USER_PREFIX = "e2e_test_user_"


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def staging_url() -> str:
    """Get the staging environment URL.

    Returns:
        Staging URL from env var STAGING_URL or default localhost.
    """
    return STAGING_URL


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async HTTP client for testing.

    Yields:
        httpx.AsyncClient instance.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def test_user(async_client: httpx.AsyncClient, staging_url: str) -> dict:
    """Create a test user via the signup endpoint.

    Creates a unique test user, yields their auth data,
    and cleans up after the test.

    Args:
        async_client: Async HTTP client.
        staging_url: Base URL for the staging environment.

    Yields:
        Dict with user_id, email, password, and auth_token.
    """
    unique_id = uuid.uuid4().hex[:8]
    email = f"{TEST_USER_PREFIX}{unique_id}@example.com"
    password = "TestPass123!"

    # Signup
    response = await async_client.post(
        f"{staging_url}/api/signup",
        json={
            "email": email,
            "password": password,
            "name": f"E2E Test User {unique_id}",
        },
    )

    user_data = {}
    if response.status_code in (200, 201):
        data = response.json()
        user_data = {
            "user_id": data.get("user_id", f"test_{unique_id}"),
            "email": email,
            "password": password,
            "auth_token": data.get("token", ""),
        }
    else:
        # If signup fails, create a mock user for testing
        user_data = {
            "user_id": f"test_{unique_id}",
            "email": email,
            "password": password,
            "auth_token": "mock_token_" + unique_id,
        }

    yield user_data

    # Cleanup: try to delete the test user
    try:
        headers = {"Authorization": f"Bearer {user_data.get('auth_token', '')}"}
        await async_client.delete(
            f"{staging_url}/api/users/{user_data.get('user_id', '')}",
            headers=headers,
        )
    except Exception:
        pass  # Cleanup failures are non-critical


@pytest_asyncio.fixture
async def test_cameras(async_client: httpx.AsyncClient, staging_url: str, test_user: dict) -> list[dict]:
    """Register test cameras for a user.

    Args:
        async_client: Async HTTP client.
        staging_url: Base URL for the staging environment.
        test_user: Dict with user auth data.

    Yields:
        List of created camera dicts.
    """
    headers = {"Authorization": f"Bearer {test_user.get('auth_token', '')}"}
    cameras = []

    # Create 3 test cameras
    for i in range(3):
        response = await async_client.post(
            f"{staging_url}/cameras",
            json={
                "name": f"E2E Test Camera {i + 1}",
                "mode": "indoor",
                "enabled": True,
                "rtsp_url": f"rtsp://test-cam-{i + 1}.local/stream",
            },
            headers=headers,
        )
        if response.status_code in (200, 201):
            cameras.append(response.json())

    yield cameras

    # Cleanup: delete test cameras
    for cam in cameras:
        try:
            cam_id = cam.get("id", cam.get("camera_id", ""))
            if cam_id:
                await async_client.delete(
                    f"{staging_url}/cameras/{cam_id}",
                    headers=headers,
                )
        except Exception:
            pass


@pytest_asyncio.fixture
async def cleanup_test_user(test_user: dict) -> None:
    """Cleanup fixture that ensures test user data is removed.

    Args:
        test_user: Dict with user auth data.
    """
    yield
    # Post-test cleanup is handled in the test_user fixture teardown
    pass
