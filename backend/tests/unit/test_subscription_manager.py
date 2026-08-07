"""

test_subscription_manager.py — Tests for Subscription Management.
"""

import pytest
pytest.importorskip("backend.billing")  # skip if not installed

from datetime import datetime, timedelta, timezone
from backend.billing.subscription_manager import (
    SubscriptionManager,
    Subscription,
    BillSummary,
    TrialStatus,
    TIER_PRICES,
    TRIAL_DAYS,
    GRACE_DAYS,
)


@pytest.fixture
def manager():
    """Create a fresh SubscriptionManager for each test."""
    from backend.billing.subscription_manager import _subscriptions, _billing_history
    _subscriptions.clear()
    _billing_history.clear()
    return SubscriptionManager()


@pytest.fixture
def sample_user():
    return "test_user_456"


# ── Test: Create Subscription ───────────────────────────────────


@pytest.mark.asyncio
async def test_create_subscription_free_tier(manager, sample_user):
    sub = await manager.create_subscription(sample_user, "free", 1)

    assert sub.user_id == sample_user
    assert sub.tier == "free"
    assert sub.status == "trial"
    assert sub.camera_count == 1
    assert sub.price_per_camera == 0.0
    assert sub.total_monthly == 0.0
    assert sub.trial_ends_at is not None


@pytest.mark.asyncio
async def test_create_subscription_household(manager, sample_user):
    sub = await manager.create_subscription(sample_user, "household", 3)

    assert sub.tier == "household"
    assert sub.status == "active"
    assert sub.camera_count == 3
    assert sub.price_per_camera == 299.0
    assert sub.total_monthly == 897.0  # 299 * 3


@pytest.mark.asyncio
async def test_create_subscription_business(manager, sample_user):
    sub = await manager.create_subscription(sample_user, "business", 5)

    assert sub.tier == "business"
    assert sub.status == "active"
    assert sub.camera_count == 5
    assert sub.price_per_camera == 499.0
    assert sub.total_monthly == 2495.0  # 499 * 5


@pytest.mark.asyncio
async def test_create_subscription_invalid_tier(manager, sample_user):
    with pytest.raises(ValueError, match="Invalid tier"):
        await manager.create_subscription(sample_user, "premium", 1)


# ── Test: Get Subscription ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_subscription_returns_data(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 2)
    sub = await manager.get_subscription(sample_user)

    assert sub.user_id == sample_user
    assert sub.tier == "household"


@pytest.mark.asyncio
async def test_get_subscription_not_found(manager):
    with pytest.raises(ValueError, match="No subscription found"):
        await manager.get_subscription("nonexistent")


# ── Test: Update Subscription ───────────────────────────────────


@pytest.mark.asyncio
async def test_update_subscription_changes_fields(manager, sample_user):
    await manager.create_subscription(sample_user, "free", 1)
    sub = await manager.update_subscription(
        sample_user, {"camera_count": 3, "auto_renew": False}
    )

    assert sub.camera_count == 3
    assert sub.auto_renew is False


# ── Test: Change Tier ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_change_tier_updates_pricing(manager, sample_user):
    await manager.create_subscription(sample_user, "free", 2)
    sub = await manager.change_tier(sample_user, "household")

    assert sub.tier == "household"
    assert sub.price_per_camera == 299.0
    assert sub.total_monthly == 598.0  # 299 * 2


# ── Test: Cancel Subscription ───────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_subscription_sets_cancelled(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 1)
    sub = await manager.cancel_subscription(sample_user)

    assert sub.status == "cancelled"
    assert sub.cancelled_at is not None
    assert sub.auto_renew is False


# ── Test: Renew Subscription ────────────────────────────────────


@pytest.mark.asyncio
async def test_renew_subscription_extends_period(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 1)
    await manager.cancel_subscription(sample_user)

    sub = await manager.renew_subscription(sample_user)

    assert sub.status == "active"
    assert sub.cancelled_at is None
    assert sub.auto_renew is True


# ── Test: Calculate Bill ────────────────────────────────────────


@pytest.mark.asyncio
async def test_calculate_bill_correct_amount(manager, sample_user):
    await manager.create_subscription(sample_user, "business", 4)
    bill = await manager.calculate_bill(sample_user)

    assert bill.tier == "business"
    assert bill.camera_count == 4
    assert bill.price_per_camera == 499.0
    assert bill.subtotal == 1996.0  # 499 * 4
    assert bill.total == 1996.0


# ── Test: Billing History ───────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_history_returns_list(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 2)

    # Add some billing records
    for i in range(3):
        bill = await manager.calculate_bill(sample_user)
        await manager.add_billing_record(sample_user, bill)

    history = await manager.get_billing_history(sample_user)
    assert len(history) == 3


# ── Test: Trial Status ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_trial_status_days_remaining(manager, sample_user):
    await manager.create_subscription(sample_user, "free", 1)
    status = await manager.check_trial_status(sample_user)

    assert status.is_trial is True
    assert status.days_remaining == TRIAL_DAYS
    assert status.total_trial_days == TRIAL_DAYS
    assert status.trial_ends_at is not None


@pytest.mark.asyncio
async def test_trial_status_no_subscription(manager):
    status = await manager.check_trial_status("nonexistent")

    assert status.is_trial is False
    assert status.days_remaining == 0
    assert status.will_expire_soon is False


# ── Test: Extend Trial ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_extend_trial_adds_days(manager, sample_user):
    await manager.create_subscription(sample_user, "free", 1)
    original_end = (await manager.get_subscription(sample_user)).trial_ends_at

    sub = await manager.extend_trial(sample_user, 15)

    assert sub.status == "trial"
    assert sub.trial_ends_at > original_end
    # Should be ~15 days later
    diff = (sub.trial_ends_at - original_end).days
    assert diff == 15


# ── Test: Handle Expiry ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_expiry_enters_grace(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 1)
    result = await manager.handle_expiry(sample_user)

    assert result["new_status"] == "grace"
    assert result["days_of_grace"] == GRACE_DAYS

    sub = await manager.get_subscription(sample_user)
    assert sub.status == "grace"
    assert sub.grace_ends_at is not None


# ── Test: Get Expired Subscriptions ─────────────────────────────


@pytest.mark.asyncio
async def test_get_expired_subscriptions(manager, sample_user):
    await manager.create_subscription(sample_user, "free", 1)

    # Manually set trial to expired
    sub = await manager.get_subscription(sample_user)
    sub.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)

    expired = await manager.get_expired_subscriptions()
    assert sample_user in expired


# ── Test: Subscriptions Due Today ───────────────────────────────


@pytest.mark.asyncio
async def test_subscriptions_due_today(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 1)

    # Manually set period end to today
    sub = await manager.get_subscription(sample_user)
    sub.current_period_end = datetime.now(timezone.utc)

    due = await manager.get_subscriptions_due_today()
    assert sample_user in due


# ── Test: Camera Count Updates Bill ─────────────────────────────


@pytest.mark.asyncio
async def test_camera_count_updates_bill(manager, sample_user):
    await manager.create_subscription(sample_user, "household", 1)
    bill = await manager.calculate_bill(sample_user)
    assert bill.total == 299.0

    await manager.update_subscription(sample_user, {"camera_count": 5})
    bill = await manager.calculate_bill(sample_user)
    assert bill.total == 1495.0  # 299 * 5


# ── Test: Subscription Dataclass ────────────────────────────────


def test_subscription_defaults():
    sub = Subscription(user_id="test")
    assert sub.tier == "free"
    assert sub.status == "trial"
    assert sub.camera_count == 1
    assert sub.auto_renew is True


# ── Test: BillSummary Dataclass ─────────────────────────────────


def test_bill_summary_defaults():
    now = datetime.now(timezone.utc)
    bill = BillSummary(
        user_id="test",
        period_start=now,
        period_end=now + timedelta(days=30),
        tier="household",
        camera_count=2,
        price_per_camera=299.0,
        subtotal=598.0,
        total=598.0,
    )
    assert bill.paid is False
    assert bill.payment_method is None


# ── Test: TrialStatus Dataclass ─────────────────────────────────


def test_trial_status_defaults():
    status = TrialStatus(is_trial=True, days_remaining=30)
    assert status.total_trial_days == TRIAL_DAYS
    assert status.will_expire_soon is False
