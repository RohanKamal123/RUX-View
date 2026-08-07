"""
camera_limits.py — Centralized camera limit constants and validation for Vision OS.

Single source of truth for camera capacity limits across all tiers.
Enforces the 20-camera-per-user limit at the application layer.

Key decisions:
- D026: All calls async
- Centralized limit constants (single source of truth)
- No migration needed — constraint is enforced in application layer, not DB schema
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Constants ───────────────────────────────────────────────────

MAX_CAMERAS_PER_USER: int = 20

TIER_LIMITS: dict = {
    "free": 20,
    "household": 20,
    "business": 20,
}


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of a camera count validation."""

    allowed: bool
    current_count: int
    max_count: int
    remaining: int
    message: str
    upgrade_suggestion: Optional[str] = None


@dataclass
class QuotaInfo:
    """Camera quota information for a user."""

    total_cameras: int
    max_cameras: int
    remaining: int
    usage_percentage: float
    tier: str


# ── CameraLimits ────────────────────────────────────────────────


class CameraLimits:
    """Centralized camera limit management.

    Provides validation, quota checking, and upgrade suggestions
    for the 20-camera-per-user limit across all tiers.
    """

    MAX_CAMERAS_PER_USER = MAX_CAMERAS_PER_USER
    TIER_LIMITS = TIER_LIMITS

    @staticmethod
    def get_max_cameras(tier: str, override: Optional[int] = None) -> int:
        """Get the maximum number of cameras allowed for a given tier.

        Args:
            tier: Subscription tier (free/household/business).
            override: If given, used instead of the TIER_LIMITS table — for
                      callers that have already fetched the live
                      max_cameras_per_user value from config_store
                      (backend.core.config_store.get_max_cameras()), since
                      this module's own constants are static and not
                      runtime-tunable. Every TIER_LIMITS entry is 20 today,
                      i.e. there is no actual per-tier differentiation yet —
                      the override lets the one runtime-tunable knob take
                      effect without this module needing to become async.

        Returns:
            Maximum cameras allowed for the tier.
        """
        if override is not None:
            return override
        return TIER_LIMITS.get(tier, MAX_CAMERAS_PER_USER)

    @staticmethod
    def validate_camera_count(
        user_id: str,
        current_count: int,
        new_count: int,
        tier: str = "free",
        max_cameras_override: Optional[int] = None,
    ) -> ValidationResult:
        """Validate whether adding new_count cameras would exceed the limit.

        Args:
            user_id: Unique user identifier.
            current_count: Current number of cameras the user has.
            new_count: Number of new cameras being added.
            tier: Subscription tier (free/household/business).
            max_cameras_override: See get_max_cameras().

        Returns:
            ValidationResult with allowed status and details.
        """
        max_cameras = CameraLimits.get_max_cameras(tier, override=max_cameras_override)
        total_after = current_count + new_count
        remaining = max_cameras - current_count

        if total_after > max_cameras:
            return ValidationResult(
                allowed=False,
                current_count=current_count,
                max_count=max_cameras,
                remaining=remaining,
                message=(
                    f"Cannot add {new_count} camera(s). "
                    f"You currently have {current_count} of {max_cameras} cameras. "
                    f"Adding {new_count} would exceed the limit of {max_cameras}."
                ),
                upgrade_suggestion=CameraLimits.get_upgrade_suggestion(current_count),
            )

        return ValidationResult(
            allowed=True,
            current_count=current_count,
            max_count=max_cameras,
            remaining=remaining - new_count,
            message=(
                f"Can add {new_count} camera(s). "
                f"You have {current_count} of {max_cameras} cameras. "
                f"{remaining - new_count} slot(s) remaining."
            ),
        )

    @staticmethod
    def get_camera_usage_percentage(user_id: str, current_count: int, tier: str = "free") -> float:
        """Calculate the percentage of camera limit used.

        Args:
            user_id: Unique user identifier.
            current_count: Current number of cameras.
            tier: Subscription tier.

        Returns:
            Usage percentage as a float (0.0 to 100.0).
        """
        max_cameras = CameraLimits.get_max_cameras(tier)
        if max_cameras == 0:
            return 100.0
        return (current_count / max_cameras) * 100.0

    @staticmethod
    def get_upgrade_suggestion(current_count: int) -> str:
        """Get a suggestion for upgrading when near the limit.

        Args:
            current_count: Current number of cameras.

        Returns:
            Suggestion string.
        """
        if current_count >= MAX_CAMERAS_PER_USER:
            return (
                f"You've reached the maximum of {MAX_CAMERAS_PER_USER} cameras. "
                "Contact support for enterprise options."
            )
        elif current_count >= MAX_CAMERAS_PER_USER - 5:
            remaining = MAX_CAMERAS_PER_USER - current_count
            return (
                f"You have {remaining} camera slot(s) remaining. "
                "Consider upgrading to a higher tier for more capacity."
            )
        return ""

    @staticmethod
    def get_quota_info(current_count: int, tier: str = "free") -> QuotaInfo:
        """Get full quota information for a user.

        Args:
            current_count: Current number of cameras.
            tier: Subscription tier.

        Returns:
            QuotaInfo with all quota details.
        """
        max_cameras = CameraLimits.get_max_cameras(tier)
        remaining = max_cameras - current_count
        usage_pct = CameraLimits.get_camera_usage_percentage("", current_count, tier)

        return QuotaInfo(
            total_cameras=current_count,
            max_cameras=max_cameras,
            remaining=remaining,
            usage_percentage=usage_pct,
            tier=tier,
        )
