"""
test_security_middleware.py — Tests for security hardening (Sprint 12.3).

Tests CORS, rate limiting, HTTPS redirect, request ID, security headers,
Firebase rules, and API key management.
"""

import json
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.security_middleware import (
    RateLimiter,
    RateLimitResult,
    RateLimitStats,
    cors_middleware,
    rate_limit_middleware,
    https_redirect_middleware,
    request_id_middleware,
    security_headers_middleware,
    add_all_middleware,
    _rate_limiter,
)
from backend.core.api_key_manager import (
    ApiKeyManager,
    ApiKey,
    ApiKeyUsage,
)


# ── Test RateLimiter ────────────────────────────────────────────


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a fresh RateLimiter for each test."""
        return RateLimiter(max_requests=10, window_seconds=60)

    @pytest.mark.asyncio
    async def test_rate_limit_allows_normal_traffic(self, limiter):
        """Verify normal traffic is allowed."""
        for _ in range(5):
            result = await limiter.check_rate_limit("192.168.1.1", "/api/cameras")
            assert result.allowed is True
            assert result.remaining >= 0

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_excessive_requests(self, limiter):
        """Verify excessive requests are blocked.

        Uses a path outside the built-in per-prefix tiers (/api/, /api/auth/,
        /api/signup, /static/ — see RateLimiter._endpoint_limits) so the
        fixture's own max_requests actually governs this test instead of
        being silently overridden by the tiered table.
        """
        for _ in range(10):
            await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")

        result = await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(self, limiter):
        """Verify rate limit resets after the window expires."""
        # Use a very short window for testing. Path must stay outside the
        # built-in per-prefix tiers — see test_rate_limit_blocks_excessive_requests.
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        result = await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        assert result.allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        result = await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_different_limits_per_endpoint(self, limiter):
        """Verify different endpoints have different limits."""
        # Auth endpoint should have lower limit
        for _ in range(10):
            await limiter.check_rate_limit("192.168.1.1", "/api/auth/login")

        result = await limiter.check_rate_limit("192.168.1.1", "/api/auth/login")
        assert result.allowed is False

        # Static endpoint should have higher limit
        for _ in range(10):
            await limiter.check_rate_limit("192.168.1.1", "/static/style.css")

        result = await limiter.check_rate_limit("192.168.1.1", "/static/style.css")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_get_remaining_returns_correct_count(self, limiter):
        """Verify get_remaining returns correct count.

        Path stays outside the built-in per-prefix tiers so the fixture's
        max_requests=10 is what's actually being counted down from.
        """
        remaining = await limiter.get_remaining("192.168.1.1", "/dashboard/status")
        assert remaining == 10

        await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        remaining = await limiter.get_remaining("192.168.1.1", "/dashboard/status")
        assert remaining == 9

    @pytest.mark.asyncio
    async def test_get_reset_time_returns_future(self, limiter):
        """Verify get_reset_time returns a future timestamp."""
        reset_at = await limiter.get_reset_time("192.168.1.1", "/api/test")
        assert reset_at > time.time()

    @pytest.mark.asyncio
    async def test_reset_limit_clears_tracking(self, limiter):
        """Verify reset_limit clears tracking for an IP+endpoint.

        Path stays outside the built-in per-prefix tiers — see
        test_get_remaining_returns_correct_count.
        """
        await limiter.check_rate_limit("192.168.1.1", "/dashboard/status")
        result = await limiter.reset_limit("192.168.1.1", "/dashboard/status")
        assert result["status"] == "reset"

        remaining = await limiter.get_remaining("192.168.1.1", "/dashboard/status")
        assert remaining == 10

    @pytest.mark.asyncio
    async def test_get_rate_limit_stats_returns_metrics(self, limiter):
        """Verify get_rate_limit_stats returns correct metrics."""
        await limiter.check_rate_limit("192.168.1.1", "/api/test")
        await limiter.check_rate_limit("192.168.1.2", "/api/test")

        stats = await limiter.get_rate_limit_stats()
        assert stats.total_requests_tracked >= 2
        assert stats.active_ips >= 2
        assert isinstance(stats.top_endpoints, list)


# ── Test Middleware Integration ─────────────────────────────────


class TestMiddleware:
    """Test suite for middleware integration."""

    @pytest.fixture
    def app(self):
        """Create a FastAPI app with all middleware."""
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/test")
        async def api_test():
            return {"message": "test"}

        add_all_middleware(app)
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_cors_middleware_allows_valid_origins(self, client):
        """Verify CORS headers are present."""
        response = client.get(
            "/health",
            headers={"Origin": "https://example.com"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_request_id_added_to_response(self, client):
        """Verify X-Request-ID header is added."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_security_headers_present_in_response(self, client):
        """Verify security headers are present."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-transport-security" in response.headers
        assert "content-security-policy" in response.headers
        assert "referrer-policy" in response.headers
        assert "permissions-policy" in response.headers

    def test_rate_limit_headers_present(self, client):
        """Verify rate limit headers are present on API endpoints."""
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers

    def test_health_endpoint_skips_rate_limit(self, client):
        """Verify health endpoint is not rate limited."""
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == 200


# ── Test Firebase Rules ─────────────────────────────────────────


class TestFirebaseRules:
    """Test suite for Firebase Security Rules validation."""

    def test_firebase_rules_file_exists(self):
        """Verify firebase_rules.json exists and is valid JSON."""
        import os
        rules_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "core", "firebase_rules.json",
        )
        assert os.path.exists(rules_path)

        with open(rules_path) as f:
            rules = json.load(f)

        assert "rules" in rules
        assert "users" in rules["rules"]
        assert "cameras" in rules["rules"]
        assert "events" in rules["rules"]
        assert "admin" in rules["rules"]

    def test_firebase_rules_owner_only_access(self):
        """Verify user data is owner-only access."""
        import os
        rules_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "core", "firebase_rules.json",
        )
        with open(rules_path) as f:
            rules = json.load(f)

        users_rule = rules["rules"]["users"]["$uid"]
        assert ".read" in users_rule
        assert "auth.uid === $uid" in users_rule[".read"]
        assert ".write" in users_rule
        assert "auth.uid === $uid" in users_rule[".write"]

    def test_firebase_rules_admin_access(self):
        """Verify admin section requires admin claim."""
        import os
        rules_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "core", "firebase_rules.json",
        )
        with open(rules_path) as f:
            rules = json.load(f)

        admin_rule = rules["rules"]["admin"]
        assert ".read" in admin_rule
        assert "auth.token.admin === true" in admin_rule[".read"]
        assert ".write" in admin_rule
        assert "auth.token.admin === true" in admin_rule[".write"]

    def test_firebase_rules_public_static_access(self):
        """Verify there's no public static access in rules (handled at CDN level)."""
        import os
        rules_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "core", "firebase_rules.json",
        )
        with open(rules_path) as f:
            rules = json.load(f)

        # All paths should have auth checks
        for path, rule in rules["rules"].items():
            if path == "admin":
                continue
            if "$uid" in rule:
                assert ".read" in rule["$uid"]
                assert ".write" in rule["$uid"]


# ── Test ApiKeyManager ──────────────────────────────────────────


class TestApiKeyManager:
    """Test suite for ApiKeyManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ApiKeyManager for each test."""
        return ApiKeyManager()

    @pytest.mark.asyncio
    async def test_generate_api_key_returns_valid_key(self, manager):
        """Verify generate_api_key returns a valid key."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras", "write:events"],
        )

        assert api_key.key_id.startswith("key_")
        assert api_key.user_id == "user123"
        assert api_key.name == "Test Key"
        assert len(api_key.permissions) == 2
        assert api_key.is_active is True
        assert raw_key.startswith("vos_")

    @pytest.mark.asyncio
    async def test_validate_api_key_valid(self, manager):
        """Verify validate_api_key returns key for valid key."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras"],
        )

        validated = await manager.validate_api_key(raw_key)
        assert validated is not None
        assert validated.key_id == api_key.key_id
        assert validated.user_id == "user123"

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self, manager):
        """Verify validate_api_key returns None for invalid key."""
        validated = await manager.validate_api_key("invalid_key_12345")
        assert validated is None

    @pytest.mark.asyncio
    async def test_validate_api_key_revoked(self, manager):
        """Verify validate_api_key returns None for revoked key."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras"],
        )

        await manager.revoke_api_key(api_key.key_id)
        validated = await manager.validate_api_key(raw_key)
        assert validated is None

    @pytest.mark.asyncio
    async def test_revoke_api_key_marks_inactive(self, manager):
        """Verify revoke_api_key marks key as inactive."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras"],
        )

        result = await manager.revoke_api_key(api_key.key_id)
        assert result["status"] == "revoked"
        assert result["key_id"] == api_key.key_id

    @pytest.mark.asyncio
    async def test_revoke_api_key_nonexistent_raises_error(self, manager):
        """Verify revoke_api_key raises ValueError for nonexistent key."""
        with pytest.raises(ValueError, match="API key not found"):
            await manager.revoke_api_key("nonexistent_key")

    @pytest.mark.asyncio
    async def test_rotate_api_key_generates_new_key(self, manager):
        """Verify rotate_api_key generates a new key and revokes old one."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras"],
        )

        new_key, new_raw_key = await manager.rotate_api_key(api_key.key_id)

        # Old key should be revoked
        assert api_key.is_active is False

        # New key should be active
        assert new_key.is_active is True
        assert new_key.user_id == "user123"
        assert new_key.name == "Test Key"
        assert new_key.permissions == ["read:cameras"]

        # Old raw key should no longer work
        old_validated = await manager.validate_api_key(raw_key)
        assert old_validated is None

        # New raw key should work
        new_validated = await manager.validate_api_key(new_raw_key)
        assert new_validated is not None

    @pytest.mark.asyncio
    async def test_list_user_api_keys_returns_user_keys(self, manager):
        """Verify list_user_api_keys returns only the user's keys."""
        await manager.generate_api_key("user1", "Key 1", ["read"])
        await manager.generate_api_key("user1", "Key 2", ["write"])
        await manager.generate_api_key("user2", "Key 3", ["read"])

        user1_keys = await manager.list_user_api_keys("user1")
        assert len(user1_keys) == 2

        user2_keys = await manager.list_user_api_keys("user2")
        assert len(user2_keys) == 1

    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(self, manager):
        """Verify API key usage tracking works."""
        api_key, raw_key = await manager.generate_api_key(
            user_id="user123",
            name="Test Key",
            permissions=["read:cameras"],
        )

        await manager.record_usage(api_key.key_id, "/api/cameras", success=True)
        await manager.record_usage(api_key.key_id, "/api/events", success=True)
        await manager.record_usage(
            api_key.key_id, "/api/cameras/123", success=False, error="Not found",
        )

        usage = await manager.get_api_key_usage(api_key.key_id)
        assert usage.total_requests == 3
        assert len(usage.endpoints_accessed) >= 2
        assert usage.last_error == "Not found"

    @pytest.mark.asyncio
    async def test_audit_log_creates_entry(self, manager):
        """Verify audit_log creates an entry."""
        entry = await manager.audit_log(
            action="delete_user",
            admin_id="admin123",
            details={"user_id": "user456", "reason": "GDPR request"},
        )

        assert entry["action"] == "delete_user"
        assert entry["admin_id"] == "admin123"
        assert entry["details"]["user_id"] == "user456"

    @pytest.mark.asyncio
    async def test_get_audit_logs_filters_by_action(self, manager):
        """Verify get_audit_logs filters by action."""
        await manager.audit_log("action_a", "admin1", {"detail": "a"})
        await manager.audit_log("action_b", "admin1", {"detail": "b"})
        await manager.audit_log("action_a", "admin2", {"detail": "c"})

        logs = await manager.get_audit_logs(action="action_a")
        assert len(logs) == 2

        logs = await manager.get_audit_logs(admin_id="admin1")
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_api_key_dataclass(self, manager):
        """Verify ApiKey dataclass fields."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        key = ApiKey(
            key_id="key_test123",
            user_id="user1",
            name="Test",
            key_prefix="vos_abcd",
            permissions=["read"],
            created_at=now,
        )
        assert key.key_id == "key_test123"
        assert key.is_active is True
        assert key.last_used_at is None

    @pytest.mark.asyncio
    async def test_api_key_usage_dataclass(self, manager):
        """Verify ApiKeyUsage dataclass fields."""
        usage = ApiKeyUsage(
            key_id="key_test123",
            total_requests=100,
            last_24h_requests=10,
            endpoints_accessed=["/api/cameras"],
        )
        assert usage.total_requests == 100
        assert usage.last_error is None
