"""
subscription_manager.py — Subscription Management for Vision OS.

Manages user subscriptions with tier-based features:
- Tiers: free (trial), household (299 BDT/camera/month), business (499 BDT/camera/month)
- Per-camera billing calculation
- Trial period management (30 days free)
- Auto-renewal and expiry handling
- Grace period before data deletion
- Subscription history tracking

Key decisions:
- D014: Three pricing tiers (free/household/business)
- D026: All calls async
- Billing per camera per month (not flat rate)
- 7-day grace period after expiry
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────

TIER_PRICES = {
    "free": 0.0,
    "household": 299.0,
    "business": 499.0,
}

TIER_NAMES = ["free", "household", "business"]
TRIAL_DAYS = 30
GRACE_DAYS = 7
AUTO_RENEW_DEFAULT = True


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class Subscription:
    """Represents a user's subscription."""

    user_id: str
    tier: str = "free"  # free/household/business
    status: str = "trial"  # active/trial/expired/cancelled/grace
    camera_count: int = 1
    price_per_camera: float = 0.0
    total_monthly: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trial_ends_at: Optional[datetime] = None
    current_period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_period_end: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30)
    )
    cancelled_at: Optional[datetime] = None
    grace_ends_at: Optional[datetime] = None
    auto_renew: bool = AUTO_RENEW_DEFAULT


@dataclass
class BillSummary:
    """Summary of a billing period."""

    user_id: str
    period_start: datetime
    period_end: datetime
    tier: str
    camera_count: int
    price_per_camera: float
    subtotal: float
    discount: float = 0.0
    total: float = 0.0
    paid: bool = False
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None


@dataclass
class TrialStatus:
    """Status of a user's trial period."""

    is_trial: bool
    days_remaining: int
    total_trial_days: int = TRIAL_DAYS
    trial_ends_at: Optional[datetime] = None
    will_expire_soon: bool = False  # < 3 days remaining


# ── In-Memory Store (replace with DB in production) ────────────

_subscriptions: dict[str, Subscription] = {}
_billing_history: dict[str, list[BillSummary]] = {}


# ── SubscriptionManager ─────────────────────────────────────────


class SubscriptionManager:
    """Manages user subscriptions, billing, and trial periods."""

    async def create_subscription(
        self, user_id: str, tier: str, camera_count: int
    ) -> Subscription:
        """Create a new subscription for a user.

        Args:
            user_id: Unique user identifier.
            tier: Subscription tier (free/household/business).
            camera_count: Number of cameras.

        Returns:
            New Subscription instance.

        Raises:
            ValueError: If tier is invalid.
        """
        if tier not in TIER_NAMES:
            raise ValueError(f"Invalid tier: {tier}. Must be one of {TIER_NAMES}")

        now = datetime.now(timezone.utc)
        price_per_camera = TIER_PRICES[tier]
        total_monthly = price_per_camera * camera_count

        trial_ends_at = now + timedelta(days=TRIAL_DAYS)
        period_end = now + timedelta(days=30)

        sub = Subscription(
            user_id=user_id,
            tier=tier,
            status="trial" if tier == "free" else "active",
            camera_count=camera_count,
            price_per_camera=price_per_camera,
            total_monthly=total_monthly,
            started_at=now,
            trial_ends_at=trial_ends_at,
            current_period_start=now,
            current_period_end=period_end,
            auto_renew=AUTO_RENEW_DEFAULT,
        )

        _subscriptions[user_id] = sub
        logger.info(
            "Subscription created for user: %s, tier: %s, cameras: %d",
            user_id, tier, camera_count,
        )
        return sub

    async def get_subscription(self, user_id: str) -> Subscription:
        """Get the current subscription for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            Current Subscription.

        Raises:
            ValueError: If no subscription exists.
        """
        if user_id not in _subscriptions:
            raise ValueError(f"No subscription found for user: {user_id}")
        return _subscriptions[user_id]

    async def update_subscription(
        self, user_id: str, updates: dict
    ) -> Subscription:
        """Update fields on an existing subscription.

        Args:
            user_id: Unique user identifier.
            updates: Dict of fields to update.

        Returns:
            Updated Subscription.

        Raises:
            ValueError: If subscription not found.
        """
        sub = await self.get_subscription(user_id)

        for key, value in updates.items():
            if hasattr(sub, key):
                setattr(sub, key, value)

        # Recalculate total if tier or camera count changed
        if "tier" in updates or "camera_count" in updates:
            sub.price_per_camera = TIER_PRICES.get(sub.tier, 0.0)
            sub.total_monthly = sub.price_per_camera * sub.camera_count

        logger.info("Subscription updated for user: %s", user_id)
        return sub

    async def change_tier(self, user_id: str, new_tier: str) -> Subscription:
        """Change a user's subscription tier.

        Args:
            user_id: Unique user identifier.
            new_tier: New tier (free/household/business).

        Returns:
            Updated Subscription.

        Raises:
            ValueError: If tier is invalid or subscription not found.
        """
        if new_tier not in TIER_NAMES:
            raise ValueError(f"Invalid tier: {new_tier}")

        return await self.update_subscription(user_id, {"tier": new_tier})

    async def cancel_subscription(self, user_id: str) -> Subscription:
        """Cancel a user's subscription.

        Args:
            user_id: Unique user identifier.

        Returns:
            Updated Subscription with cancelled status.
        """
        sub = await self.get_subscription(user_id)
        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        sub.auto_renew = False

        logger.info("Subscription cancelled for user: %s", user_id)
        return sub

    async def renew_subscription(self, user_id: str) -> Subscription:
        """Renew a user's subscription for another period.

        Args:
            user_id: Unique user identifier.

        Returns:
            Updated Subscription with new period.
        """
        sub = await self.get_subscription(user_id)
        now = datetime.now(timezone.utc)

        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.cancelled_at = None
        sub.grace_ends_at = None
        sub.auto_renew = AUTO_RENEW_DEFAULT

        logger.info("Subscription renewed for user: %s", user_id)
        return sub

    async def calculate_bill(self, user_id: str) -> BillSummary:
        """Calculate the current bill for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            BillSummary with calculated amounts.
        """
        sub = await self.get_subscription(user_id)
        now = datetime.now(timezone.utc)

        subtotal = sub.price_per_camera * sub.camera_count

        return BillSummary(
            user_id=user_id,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            tier=sub.tier,
            camera_count=sub.camera_count,
            price_per_camera=sub.price_per_camera,
            subtotal=subtotal,
            total=subtotal,
        )

    async def get_billing_history(
        self, user_id: str, limit: int = 12
    ) -> list[BillSummary]:
        """Get billing history for a user.

        Args:
            user_id: Unique user identifier.
            limit: Maximum number of records to return.

        Returns:
            List of BillSummary records.
        """
        history = _billing_history.get(user_id, [])
        return history[-limit:]

    async def check_trial_status(self, user_id: str) -> TrialStatus:
        """Check the trial status for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            TrialStatus with days remaining and expiry info.
        """
        try:
            sub = await self.get_subscription(user_id)
        except ValueError:
            return TrialStatus(
                is_trial=False,
                days_remaining=0,
                will_expire_soon=False,
            )

        if not sub.trial_ends_at:
            return TrialStatus(
                is_trial=False,
                days_remaining=0,
                will_expire_soon=False,
            )

        now = datetime.now(timezone.utc)
        remaining = (sub.trial_ends_at - now).days
        if remaining < 0:
            remaining = 0

        return TrialStatus(
            is_trial=sub.status == "trial",
            days_remaining=remaining,
            total_trial_days=TRIAL_DAYS,
            trial_ends_at=sub.trial_ends_at,
            will_expire_soon=remaining < 3,
        )

    async def extend_trial(self, user_id: str, days: int) -> Subscription:
        """Extend a user's trial period.

        Args:
            user_id: Unique user identifier.
            days: Number of days to extend.

        Returns:
            Updated Subscription.
        """
        sub = await self.get_subscription(user_id)
        if sub.trial_ends_at:
            sub.trial_ends_at += timedelta(days=days)
        else:
            sub.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=days)

        sub.status = "trial"
        logger.info(
            "Trial extended by %d days for user: %s", days, user_id
        )
        return sub

    async def handle_expiry(self, user_id: str) -> dict:
        """Handle subscription expiry — enter grace period.

        Args:
            user_id: Unique user identifier.

        Returns:
            Dict with expiry handling details.
        """
        sub = await self.get_subscription(user_id)
        now = datetime.now(timezone.utc)

        sub.status = "grace"
        sub.grace_ends_at = now + timedelta(days=GRACE_DAYS)

        result = {
            "user_id": user_id,
            "previous_status": "active",
            "new_status": "grace",
            "grace_ends_at": sub.grace_ends_at.isoformat(),
            "days_of_grace": GRACE_DAYS,
        }

        logger.info(
            "Subscription expired for user: %s. Entered grace period until %s",
            user_id, sub.grace_ends_at,
        )
        return result

    async def get_expired_subscriptions(self) -> list[str]:
        """Get list of users with expired subscriptions.

        Returns:
            List of user IDs with expired subscriptions.
        """
        now = datetime.now(timezone.utc)
        expired = []

        for user_id, sub in _subscriptions.items():
            if sub.status == "active" and sub.current_period_end < now:
                expired.append(user_id)
            elif sub.status == "trial" and sub.trial_ends_at and sub.trial_ends_at < now:
                expired.append(user_id)

        return expired

    async def get_subscriptions_due_today(self) -> list[str]:
        """Get list of users whose subscriptions are due today.

        Returns:
            List of user IDs with subscriptions due today.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        due = []
        for user_id, sub in _subscriptions.items():
            if today_start <= sub.current_period_end < today_end:
                due.append(user_id)

        return due

    async def add_billing_record(self, user_id: str, bill: BillSummary) -> None:
        """Add a billing record to history.

        Args:
            user_id: Unique user identifier.
            bill: BillSummary to add.
        """
        if user_id not in _billing_history:
            _billing_history[user_id] = []
        _billing_history[user_id].append(bill)
