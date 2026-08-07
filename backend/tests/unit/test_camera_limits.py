"""
test_camera_limits.py — Tests for camera limit enforcement (Sprint 12.1).

Tests the 20-camera-per-user limit across all tiers.
"""

import pytest
from backend.core.camera_limits import (
    CameraLimits,
    ValidationResult,
    QuotaInfo,
    MAX_CAMERAS_PER_USER,
    TIER_LIMITS,
)


class TestCameraLimits:
    """Test suite for CameraLimits class."""

    def test_max_cameras_constant_is_20(self):
        """Verify MAX_CAMERAS_PER_USER is 20."""
        assert MAX_CAMERAS_PER_USER == 20

    def test_get_max_cameras_returns_20_for_all_tiers(self):
        """Verify all tiers return 20 cameras."""
        for tier in ["free", "household", "business"]:
            assert CameraLimits.get_max_cameras(tier) == 20

    def test_get_max_cameras_unknown_tier_returns_default(self):
        """Verify unknown tier returns default 20."""
        assert CameraLimits.get_max_cameras("enterprise") == 20

    def test_validate_camera_count_under_limit_returns_allowed(self):
        """Verify adding cameras under limit is allowed."""
        result = CameraLimits.validate_camera_count(
            user_id="user1",
            current_count=5,
            new_count=3,
            tier="free",
        )
        assert result.allowed is True
        assert result.remaining == 12  # 20 - 5 - 3
        assert result.current_count == 5
        assert result.max_count == 20

    def test_validate_camera_count_at_limit_returns_allowed(self):
        """Verify adding cameras exactly at limit is allowed."""
        result = CameraLimits.validate_camera_count(
            user_id="user1",
            current_count=15,
            new_count=5,
            tier="free",
        )
        assert result.allowed is True
        assert result.remaining == 0

    def test_validate_camera_count_over_limit_returns_blocked(self):
        """Verify adding cameras over limit is blocked."""
        result = CameraLimits.validate_camera_count(
            user_id="user1",
            current_count=18,
            new_count=5,
            tier="free",
        )
        assert result.allowed is False
        assert result.remaining == 2
        assert "exceed the limit" in result.message.lower()

    def test_validate_camera_count_exactly_at_20_blocks_additional(self):
        """Verify adding when already at 20 is blocked."""
        result = CameraLimits.validate_camera_count(
            user_id="user1",
            current_count=20,
            new_count=1,
            tier="free",
        )
        assert result.allowed is False
        assert result.remaining == 0

    def test_get_camera_usage_percentage_calculates_correctly(self):
        """Verify usage percentage calculation."""
        pct = CameraLimits.get_camera_usage_percentage("user1", 10, "free")
        assert pct == 50.0

        pct = CameraLimits.get_camera_usage_percentage("user1", 20, "free")
        assert pct == 100.0

        pct = CameraLimits.get_camera_usage_percentage("user1", 0, "free")
        assert pct == 0.0

    def test_get_camera_usage_percentage_handles_zero_max(self):
        """Verify usage percentage handles an unknown tier gracefully.

        "unknown" isn't in TIER_LIMITS, so this falls back to the default
        20 (per get_max_cameras), not an actual max_cameras=0 case (that's
        a different code path in get_camera_usage_percentage — the
        `if max_cameras == 0: return 100.0` branch, not exercised here).
        """
        pct = CameraLimits.get_camera_usage_percentage("user1", 5, "unknown")
        assert pct == 25.0  # falls back to default 20, so 5/20 = 25%

    def test_get_upgrade_suggestion_when_near_limit(self):
        """Verify upgrade suggestion when near limit."""
        suggestion = CameraLimits.get_upgrade_suggestion(16)
        assert "remaining" in suggestion.lower()
        assert "4" in suggestion  # 20 - 16 = 4 remaining

    def test_get_upgrade_suggestion_at_limit(self):
        """Verify upgrade suggestion at limit."""
        suggestion = CameraLimits.get_upgrade_suggestion(20)
        assert "maximum" in suggestion.lower()
        assert "enterprise" in suggestion.lower()

    def test_get_upgrade_suggestion_far_from_limit(self):
        """Verify no suggestion when far from limit."""
        suggestion = CameraLimits.get_upgrade_suggestion(5)
        assert suggestion == ""

    def test_create_camera_enforces_20_limit(self):
        """Verify create_camera enforces 20 limit (via validate)."""
        # Simulate having 20 cameras already
        result = CameraLimits.validate_camera_count("user1", 20, 1, "free")
        assert result.allowed is False

        # Simulate having 19 cameras, adding 1 should work
        result = CameraLimits.validate_camera_count("user1", 19, 1, "free")
        assert result.allowed is True
        assert result.remaining == 0

    def test_bulk_create_enforces_total_20(self):
        """Verify bulk create enforces total 20 limit."""
        # 15 current + 10 new = 25 > 20
        result = CameraLimits.validate_camera_count("user1", 15, 10, "free")
        assert result.allowed is False

        # 10 current + 10 new = 20 <= 20
        result = CameraLimits.validate_camera_count("user1", 10, 10, "free")
        assert result.allowed is True
        assert result.remaining == 0

    def test_get_camera_quota_returns_correct_remaining(self):
        """Verify get_quota_info returns correct values."""
        quota = CameraLimits.get_quota_info(15, "free")
        assert isinstance(quota, QuotaInfo)
        assert quota.total_cameras == 15
        assert quota.max_cameras == 20
        assert quota.remaining == 5
        assert quota.usage_percentage == 75.0
        assert quota.tier == "free"

    def test_existing_user_with_10_cameras_can_add_10_more(self):
        """Verify backward compatibility: 10 existing + 10 new = 20."""
        result = CameraLimits.validate_camera_count("user1", 10, 10, "free")
        assert result.allowed is True
        assert result.remaining == 0

    def test_tier_limits_dict_all_20(self):
        """Verify TIER_LIMITS has all tiers at 20."""
        for tier in ["free", "household", "business"]:
            assert TIER_LIMITS[tier] == 20

    def test_validation_result_dataclass(self):
        """Verify ValidationResult dataclass fields."""
        result = ValidationResult(
            allowed=True,
            current_count=5,
            max_count=20,
            remaining=15,
            message="OK",
            upgrade_suggestion="Consider upgrading",
        )
        assert result.allowed is True
        assert result.current_count == 5
        assert result.max_count == 20
        assert result.remaining == 15
        assert result.message == "OK"
        assert result.upgrade_suggestion == "Consider upgrading"

    def test_quota_info_dataclass(self):
        """Verify QuotaInfo dataclass fields."""
        quota = QuotaInfo(
            total_cameras=10,
            max_cameras=20,
            remaining=10,
            usage_percentage=50.0,
            tier="household",
        )
        assert quota.total_cameras == 10
        assert quota.max_cameras == 20
        assert quota.remaining == 10
        assert quota.usage_percentage == 50.0
        assert quota.tier == "household"
