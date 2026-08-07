"""

test_trial_manager.py — Tests for Trial Management.
"""

import pytest
pytest.importorskip("backend.billing")  # skip if not installed

from datetime import datetime, timedelta, timezone
from backend.billing.trial_manager import (
    TrialManager,
    TrialInfo,
    TRIAL_DAYS,
    GRACE_DAYS,
    TRIAL_WARNINGS,
    GRACE_WARNINGS,
)


@pytest.fixture
def manager():
    """Create a fresh TrialManager for each test."""
    from backend.billing.trial_manager import _trials
    _trials.clear()
    return TrialManager()


@pytest.fixture
def sample_user():
    return "test_user_trial"


# ── Test: Start Trial ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_trial_creates_30_day_period(manager, sample_user):
    trial = await manager.start_trial(sample_user)

    assert trial.user_id == sample_user
    assert trial.is_active is True
    assert trial.is_in_grace is False
    assert trial.days_remaining == TRIAL_DAYS
    assert trial.converted_to_paid is False

    # Check trial period is ~30 days
    diff = (trial.trial_ends_at - trial.started_at).days
    assert diff == TRIAL_DAYS


# ── Test: Get Trial Info ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trial_info_returns_correct_data(manager, sample_user):
    await manager.start_trial(sample_user)
    trial = await manager.get_trial_info(sample_user)

    assert trial.user_id == sample_user
    assert trial.days_remaining > 0


@pytest.mark.asyncio
async def test_get_trial_info_not_found(manager):
    with pytest.raises(ValueError, match="No trial found"):
        await manager.get_trial_info("nonexistent")


# ── Test: Days Remaining ────────────────────────────────────────


@pytest.mark.asyncio
async def test_days_remaining_decreases_over_time(manager, sample_user):
    await manager.start_trial(sample_user)
    days = await manager.get_days_remaining(sample_user)

    assert days == TRIAL_DAYS

    # Simulate time passing by modifying trial_ends_at
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=5)

    days = await manager.get_days_remaining(sample_user)
    assert days == 5


# ── Test: Is Trial Active ───────────────────────────────────────


@pytest.mark.asyncio
async def test_is_trial_active_true_within_period(manager, sample_user):
    await manager.start_trial(sample_user)
    assert await manager.is_trial_active(sample_user) is True


@pytest.mark.asyncio
async def test_is_trial_expired_after_period(manager, sample_user):
    await manager.start_trial(sample_user)

    # Set trial to expired
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)

    assert await manager.is_trial_active(sample_user) is False
    assert await manager.is_trial_expired(sample_user) is True


# ── Test: Extend Trial ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_extend_trial_adds_days(manager, sample_user):
    await manager.start_trial(sample_user)
    original_end = (await manager.get_trial_info(sample_user)).trial_ends_at

    trial = await manager.extend_trial(sample_user, 15, "admin_001")

    assert trial.is_active is True
    diff = (trial.trial_ends_at - original_end).days
    assert diff == 15


# ── Test: End Trial Early ───────────────────────────────────────


@pytest.mark.asyncio
async def test_end_trial_early(manager, sample_user):
    await manager.start_trial(sample_user)
    trial = await manager.end_trial_early(sample_user)

    assert trial.is_active is False
    assert trial.days_remaining == 0


# ── Test: Convert to Paid ───────────────────────────────────────


@pytest.mark.asyncio
async def test_convert_to_paid_marks_converted(manager, sample_user):
    await manager.start_trial(sample_user)
    trial = await manager.convert_to_paid(sample_user, "household")

    assert trial.converted_to_paid is True
    assert trial.converted_tier == "household"
    assert trial.converted_at is not None


# ── Test: Get Users Near Expiry ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_users_near_expiry(manager, sample_user):
    await manager.start_trial(sample_user)

    # Set trial to expire in 2 days
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=2)

    near_expiry = await manager.get_users_near_expiry(days_threshold=3)
    assert sample_user in near_expiry


# ── Test: Get Expired Users ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_expired_users(manager, sample_user):
    await manager.start_trial(sample_user)

    # Set trial to expired
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)

    expired = await manager.get_expired_users()
    assert sample_user in expired


# ── Test: Trial Conversion Rate ─────────────────────────────────


@pytest.mark.asyncio
async def test_trial_conversion_rate_calculation(manager):
    user_a = "user_a"
    user_b = "user_b"
    user_c = "user_c"

    await manager.start_trial(user_a)
    await manager.start_trial(user_b)
    await manager.start_trial(user_c)

    await manager.convert_to_paid(user_a, "household")
    await manager.convert_to_paid(user_b, "business")

    since = datetime.now(timezone.utc) - timedelta(days=1)
    rate = await manager.get_trial_conversion_rate(since)

    assert rate == pytest.approx(2 / 3, abs=0.01)


# ── Test: Send Expiry Warnings ──────────────────────────────────


@pytest.mark.asyncio
async def test_send_expiry_warnings_returns_count(manager, sample_user):
    await manager.start_trial(sample_user)

    # Simulate being on day 28 (2 days remaining)
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=2)

    count = await manager.send_expiry_warnings()
    assert count >= 1


# ── Test: Handle Grace Period ───────────────────────────────────


@pytest.mark.asyncio
async def test_handle_grace_period(manager, sample_user):
    await manager.start_trial(sample_user)

    # Set trial to expired
    trial = await manager.get_trial_info(sample_user)
    trial.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)

    result = await manager.handle_grace_period(sample_user)

    assert result["days_of_grace"] == GRACE_DAYS
    assert "trial has ended" in result["message"].lower()

    trial = await manager.get_trial_info(sample_user)
    assert trial.is_in_grace is True
    assert trial.grace_ends_at is not None


# ── Test: Schedule Data Deletion ────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_data_deletion(manager, sample_user):
    await manager.start_trial(sample_user)
    result = await manager.schedule_data_deletion(sample_user)

    assert result["user_id"] == sample_user
    assert "deletion_date" in result
    assert "deletion_scheduled_at" in result


# ── Test: Warning Schedule Days Match ───────────────────────────


def test_warning_schedule_days_match():
    # Trial warnings
    assert 1 in TRIAL_WARNINGS
    assert 5 in TRIAL_WARNINGS
    assert 7 in TRIAL_WARNINGS
    assert 14 in TRIAL_WARNINGS
    assert 21 in TRIAL_WARNINGS
    assert 28 in TRIAL_WARNINGS
    assert 29 in TRIAL_WARNINGS
    assert 30 in TRIAL_WARNINGS
    assert len(TRIAL_WARNINGS) == 8

    # Grace warnings
    assert 1 in GRACE_WARNINGS
    assert 5 in GRACE_WARNINGS
    assert 7 in GRACE_WARNINGS
    assert len(GRACE_WARNINGS) == 3


# ── Test: TrialInfo Dataclass ───────────────────────────────────


def test_trial_info_defaults():
    trial = TrialInfo(user_id="test")
    assert trial.is_active is True
    assert trial.is_in_grace is False
    assert trial.days_remaining == TRIAL_DAYS
    assert trial.converted_to_paid is False
    assert trial.warnings_sent == []


# ── Test: No Trial Found ────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_trial_active_no_trial(manager):
    assert await manager.is_trial_active("nonexistent") is False


@pytest.mark.asyncio
async def test_is_trial_expired_no_trial(manager):
    assert await manager.is_trial_expired("nonexistent") is True


@pytest.mark.asyncio
async def test_get_days_remaining_no_trial(manager):
    assert await manager.get_days_remaining("nonexistent") == 0
