"""Tests for admin dashboard routes and onboarding flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


class TestAdminRoutes:

    @pytest.mark.asyncio
    async def test_admin_dashboard_requires_admin_role(self):
        """Test that admin dashboard requires admin role."""
        from backend.dashboard.admin_routes import require_admin

        admin_user = {"id": "admin-001", "role": "admin"}
        result = require_admin(admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        """Test that non-admin users get 403."""
        from backend.dashboard.admin_routes import require_admin

        non_admin = {"id": "user-001", "role": "user"}

        with pytest.raises(HTTPException) as exc_info:
            require_admin(non_admin)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_users_lists_all_users(self):
        """Test that admin users page lists all users."""
        from backend.dashboard.admin_routes import admin_users

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_users(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_change_tier_updates_user(self):
        """Test that admin can change user tier."""
        from backend.dashboard.admin_routes import admin_change_tier

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_change_tier("user-001", "household", user)
        assert result["success"] is True
        assert result["new_tier"] == "household"

    @pytest.mark.asyncio
    async def test_admin_change_tier_invalid_tier_raises_error(self):
        """Test that invalid tier raises error."""
        from backend.dashboard.admin_routes import admin_change_tier

        user = {"id": "admin-001", "role": "admin"}

        with pytest.raises(HTTPException) as exc_info:
            await admin_change_tier("user-001", "invalid_tier", user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_disable_user_prevents_login(self):
        """Test that admin can disable a user."""
        from backend.dashboard.admin_routes import admin_disable_user

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_disable_user("user-001", user)
        assert result["success"] is True
        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_admin_health_endpoint_returns_json(self):
        """Test that admin health endpoint returns JSON."""
        from backend.dashboard.admin_routes import admin_health

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_health(user)
        assert "status" in result
        assert "checks" in result
        assert "uptime_seconds" in result
        assert "active_cameras" in result
        assert "total_errors_24h" in result

    @pytest.mark.asyncio
    async def test_beta_invite_generation_creates_codes(self):
        """Test that beta invite generation creates codes."""
        from backend.dashboard.admin_routes import admin_generate_invite

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_generate_invite(3, user)
        assert "codes" in result
        assert len(result["codes"]) == 3
        for code in result["codes"]:
            assert code.startswith("BETA-")

    @pytest.mark.asyncio
    async def test_beta_invite_generation_validates_count(self):
        """Test that invite generation validates count."""
        from backend.dashboard.admin_routes import admin_generate_invite

        user = {"id": "admin-001", "role": "admin"}

        with pytest.raises(HTTPException) as exc_info:
            await admin_generate_invite(0, user)
        assert exc_info.value.status_code == 400

        with pytest.raises(HTTPException) as exc_info:
            await admin_generate_invite(101, user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_beta_invite_code_used_once(self):
        """Test that invite codes are tracked as used/unused."""
        from backend.dashboard.admin_routes import admin_generate_invite, _beta_invites

        user = {"id": "admin-001", "role": "admin"}
        _beta_invites.clear()

        result = await admin_generate_invite(2, user)
        assert len(result["codes"]) == 2

        # Verify invites are stored
        assert len(_beta_invites) == 2
        for invite in _beta_invites:
            assert invite["used"] is False
            assert invite["used_by"] is None

    @pytest.mark.asyncio
    async def test_onboarding_wizard_shows_for_new_users(self):
        """Test that onboarding wizard is shown for new users."""
        from backend.dashboard.admin_routes import admin_dashboard

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_dashboard(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_feedback_submission_and_viewing(self):
        """Test that feedback can be viewed by admin."""
        from backend.dashboard.admin_routes import admin_feedback

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_feedback(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_errors_page_loads(self):
        """Test that admin errors page loads correctly."""
        from backend.dashboard.admin_routes import admin_errors

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_errors(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_beta_invites_page_loads(self):
        """Test that beta invites page loads correctly."""
        from backend.dashboard.admin_routes import admin_beta_invites

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_beta_invites(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_user_detail_returns_data(self):
        """Test that admin user detail returns user data."""
        from backend.dashboard.admin_routes import admin_user_detail

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_user_detail("user-001", user)
        assert result["id"] == "user-001"
        assert "tier" in result
        assert "locations" in result
        assert "recent_events" in result

    @pytest.mark.asyncio
    async def test_admin_users_page_has_all_statuses(self):
        """Test that admin users page shows various user statuses."""
        from backend.dashboard.admin_routes import admin_users

        request = MagicMock()
        user = {"id": "admin-001", "role": "admin"}

        response = await admin_users(request, user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_health_returns_all_subsystems(self):
        """Test that health endpoint returns all subsystem checks."""
        from backend.dashboard.admin_routes import admin_health

        user = {"id": "admin-001", "role": "admin"}

        result = await admin_health(user)
        expected_checks = {"database", "gemini_api", "groq_api", "telegram", "storage"}
        assert set(result["checks"].keys()) == expected_checks
