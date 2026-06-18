"""
test_auth.py — Unit tests for Vision OS Authentication middleware.

Tests token verification, user extraction, and tier-based access control.
In development mode, Firebase is bypassed — tests verify both dev and
production paths.
"""

import pytest
from unittest.mock import patch

from fastapi import HTTPException

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_firebase_state():
    """Reset the module-level Firebase state before each test."""
    import backend.dashboard.auth as auth_mod

    auth_mod._firebase_app = None
    auth_mod._firebase_available = False
    yield


@pytest.fixture
def mock_firebase_auth():
    """Mock firebase_admin.auth module (used inside verify_token in production).

    Since firebase_auth is imported *inside* verify_token(), we patch
    it at the firebase_admin module level. We use create=True because
    'auth' is a lazy-loaded submodule that may not exist yet.
    """
    with patch("firebase_admin.auth", create=True) as mock:
        yield mock


@pytest.fixture
def mock_firebase_init():
    """Mock firebase_admin.initialize_app to prevent real init.

    Since firebase_admin is imported *inside* init_firebase(), we patch
    it at the firebase_admin module level.
    """
    with patch("firebase_admin.initialize_app") as mock:
        yield mock


@pytest.fixture
def mock_credentials():
    """Mock firebase_admin.credentials to prevent real cert loading.

    Since credentials is imported *inside* init_firebase(), we patch
    it at the firebase_admin module level.
    """
    with patch("firebase_admin.credentials") as mock:
        yield mock


@pytest.fixture
def valid_token() -> str:
    return "valid-firebase-id-token-12345"


@pytest.fixture
def valid_user_dict() -> dict:
    return {
        "uid": "test-user-123",
        "email": "test@example.com",
        "tier": "household",
        "subscription_active": True,
    }


# ── Test: init_firebase ───────────────────────────────────────


@pytest.mark.asyncio
async def test_init_firebase_no_credentials(mock_firebase_init, mock_credentials):
    """Test init_firebase handles missing credentials gracefully."""
    from backend.dashboard.auth import init_firebase

    # Should not raise
    init_firebase()


@pytest.mark.asyncio
async def test_init_firebase_sets_available_on_success(
    mock_firebase_init, mock_credentials
):
    """Test init_firebase sets _firebase_available = True on success."""
    import backend.dashboard.auth as auth_mod

    auth_mod.init_firebase()
    assert auth_mod._firebase_available is True


# ── Test: verify_token (dev mode) ─────────────────────────────


@pytest.mark.asyncio
async def test_dev_mode_returns_dev_user():
    """Test that in development mode, verify_token returns the dev user."""
    from backend.dashboard.auth import verify_token

    result = await verify_token("any-token-works-in-dev")
    assert result["uid"] == "dev-user-001"
    assert result["email"] == "dev@visionos.local"
    assert result["tier"] == "business"
    assert result["subscription_active"] is True


@pytest.mark.asyncio
async def test_dev_mode_ignores_invalid_tokens():
    """Test that even invalid tokens work in dev mode (no Firebase check)."""
    from backend.dashboard.auth import verify_token

    result = await verify_token("")
    assert result["uid"] == "dev-user-001"


# ── Test: verify_token (production mode) ──────────────────────


@pytest.mark.asyncio
async def test_valid_token_passes(mock_firebase_auth, valid_token, valid_user_dict):
    """Test that a valid Firebase token returns user info in production mode."""
    import backend.dashboard.auth as auth_mod

    # Simulate production mode with Firebase available
    auth_mod._firebase_available = True
    mock_firebase_auth.verify_id_token.return_value = {
        "uid": "test-user-123",
        "email": "test@example.com",
        "claims": {
            "tier": "household",
            "subscription_active": True,
        },
    }

    result = await auth_mod.verify_token(valid_token)
    assert result["uid"] == "test-user-123"
    assert result["email"] == "test@example.com"
    assert result["tier"] == "household"
    assert result["subscription_active"] is True


@pytest.mark.asyncio
async def test_invalid_token_rejected(mock_firebase_auth):
    """Test that an invalid token raises HTTPException 401 in production mode."""
    import backend.dashboard.auth as auth_mod

    auth_mod._firebase_available = True
    mock_firebase_auth.verify_id_token.side_effect = ValueError("Invalid token")

    with pytest.raises(HTTPException) as exc_info:
        await auth_mod.verify_token("invalid-token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(mock_firebase_auth):
    """Test that an expired token raises HTTPException 401 in production mode."""
    import backend.dashboard.auth as auth_mod

    auth_mod._firebase_available = True
    mock_firebase_auth.verify_id_token.side_effect = ValueError("Token expired")

    with pytest.raises(HTTPException) as exc_info:
        await auth_mod.verify_token("expired-token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_without_claims_defaults_free(mock_firebase_auth):
    """Test that a token without custom claims defaults to free tier in production."""
    import backend.dashboard.auth as auth_mod

    auth_mod._firebase_available = True
    mock_firebase_auth.verify_id_token.return_value = {
        "uid": "test-user-456",
        "email": "user@example.com",
        # No claims key
    }

    result = await auth_mod.verify_token("some-token")
    assert result["tier"] == "free"
    assert result["subscription_active"] is False


# ── Test: get_current_user ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_user_missing_header():
    """Test that missing Authorization header raises 401."""
    from backend.dashboard.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=None)
    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_invalid_format():
    """Test that malformed Authorization header raises 401."""
    from backend.dashboard.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="NotBearer token123")
    assert exc_info.value.status_code == 401
    assert "Invalid" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_empty_token():
    """Test that empty token after Bearer raises 401."""
    from backend.dashboard.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Bearer ")
    assert exc_info.value.status_code == 401


# ── Test: require_tier ────────────────────────────────────────


@pytest.mark.asyncio
async def test_tier_check_household_allowed(valid_user_dict):
    """Test that a household-tier user can access household routes."""
    from backend.dashboard.auth import require_tier

    @require_tier("household")
    async def dummy_route(user: dict = None):
        return {"success": True}

    result = await dummy_route(user=valid_user_dict)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_tier_check_business_allowed():
    """Test that a business-tier user can access business routes."""
    from backend.dashboard.auth import require_tier

    @require_tier("business")
    async def dummy_route(user: dict = None):
        return {"success": True}

    result = await dummy_route(
        user={
            "uid": "biz-user",
            "email": "biz@example.com",
            "tier": "business",
            "subscription_active": True,
        }
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_free_tier_blocked_premium_route():
    """Test that a free-tier user is blocked from household routes."""
    from backend.dashboard.auth import require_tier

    @require_tier("household")
    async def premium_route(user: dict = None):
        return {"success": True}

    with pytest.raises(HTTPException) as exc_info:
        await premium_route(
            user={
                "uid": "free-user",
                "email": "free@example.com",
                "tier": "free",
                "subscription_active": False,
            }
        )
    assert exc_info.value.status_code == 403
    assert "Premium" in exc_info.value.detail


@pytest.mark.asyncio
async def test_household_blocked_business_route():
    """Test that a household-tier user is blocked from business routes."""
    from backend.dashboard.auth import require_tier

    @require_tier("business")
    async def business_route(user: dict = None):
        return {"success": True}

    with pytest.raises(HTTPException) as exc_info:
        await business_route(
            user={
                "uid": "household-user",
                "email": "household@example.com",
                "tier": "household",
                "subscription_active": True,
            }
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_tier_no_user():
    """Test that require_tier raises 401 when no user is provided."""
    from backend.dashboard.auth import require_tier

    @require_tier("household")
    async def protected_route(user: dict = None):
        return {"success": True}

    with pytest.raises(HTTPException) as exc_info:
        await protected_route(user=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_tier_invalid_tier():
    """Test that an invalid tier name raises ValueError."""
    from backend.dashboard.auth import require_tier

    with pytest.raises(ValueError, match="Unknown tier"):
        require_tier("platinum")
