"""
test_public_signup.py — Tests for Self-Service Signup (Sprint 11.2).

Tests cover:
- Signup creates Firebase user and database record
- Signup starts trial
- Signup sends verification email
- Email verification flow
- Password reset flow
- Validation (email, password, name, phone)
- Rate limiting
- Signup stats
- Duplicate email handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from backend.api.public_signup import (
    PublicSignupHandler,
    SignupResult,
    SignupStats,
    _reset_store,
)


@pytest.fixture
def handler():
    """Create a fresh handler for each test."""
    _reset_store()
    return PublicSignupHandler()


@pytest.fixture
def sample_signup_data():
    return {
        "email": "test@example.com",
        "password": "TestPass123",
        "name": "Test User",
        "phone": "01712345678",
    }


# ── Test: Signup Creates Firebase User ────────────────────────────


@pytest.mark.asyncio
async def test_signup_creates_firebase_user(handler, sample_signup_data):
    result = await handler.signup(**sample_signup_data)

    assert result.firebase_uid.startswith("fb_"), "Firebase UID should start with fb_"
    assert len(result.firebase_uid) > 5, "Firebase UID too short"
    assert result.email == sample_signup_data["email"].lower()


@pytest.mark.asyncio
async def test_signup_creates_database_record(handler, sample_signup_data):
    result = await handler.signup(**sample_signup_data)

    assert result.user_id is not None
    assert len(result.user_id) > 0
    assert result.name == sample_signup_data["name"]
    assert result.email == sample_signup_data["email"].lower()


# ── Test: Signup Starts Trial ─────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_starts_trial(handler, sample_signup_data):
    result = await handler.signup(**sample_signup_data)

    assert result.tier == "free"
    assert result.trial_ends_at is not None
    assert result.trial_ends_at > datetime.now(timezone.utc)

    # Trial should be ~30 days
    trial_duration = result.trial_ends_at - result.created_at
    assert 29 <= trial_duration.days <= 31, f"Trial should be ~30 days, got {trial_duration.days}"


# ── Test: Signup Sends Verification Email ─────────────────────────


@pytest.mark.asyncio
async def test_signup_sends_verification_email(handler, sample_signup_data):
    result = await handler.signup(**sample_signup_data)

    assert result.email_verified is False
    assert "verify" in result.message.lower()


# ── Test: Verify Email ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_email_marks_verified(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)

    # We need to get the verification code - it's stored internally
    # The test verifies the flow works by calling verify_email
    from backend.api.public_signup import _verification_codes
    email_key = sample_signup_data["email"].lower()
    code = _verification_codes.get(email_key)
    assert code is not None, "Verification code should exist"

    result = await handler.verify_email(sample_signup_data["email"], code)
    assert result["status"] == "verified"

    # Verify email is now marked as verified
    available = await handler.check_email_available(sample_signup_data["email"])
    assert available is False, "Email should still be registered"


# ── Test: Resend Verification ─────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_verification_returns_success(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)

    result = await handler.resend_verification(sample_signup_data["email"])
    assert result["status"] == "sent"


# ── Test: Check Email Available ───────────────────────────────────


@pytest.mark.asyncio
async def test_check_email_available_true(handler):
    result = await handler.check_email_available("new@example.com")
    assert result is True


@pytest.mark.asyncio
async def test_check_email_available_false(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)
    result = await handler.check_email_available(sample_signup_data["email"])
    assert result is False


# ── Test: Initiate Password Reset ─────────────────────────────────


@pytest.mark.asyncio
async def test_initiate_password_reset(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)

    result = await handler.initiate_password_reset(sample_signup_data["email"])
    assert result["status"] == "reset_initiated"


# ── Test: Reset Password ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_with_valid_code(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)
    await handler.initiate_password_reset(sample_signup_data["email"])

    from backend.api.public_signup import _reset_codes
    email_key = sample_signup_data["email"].lower()
    code = _reset_codes.get(email_key)
    assert code is not None, "Reset code should exist"

    result = await handler.reset_password(code, "NewPass123")
    assert result["status"] == "password_reset"


# ── Test: Invalid Email ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_invalid_email_returns_error(handler):
    with pytest.raises(ValueError, match="Invalid email format"):
        await handler.signup(
            email="not-an-email",
            password="TestPass123",
            name="Test User",
            phone="",
        )


# ── Test: Weak Password ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_weak_password_returns_error(handler):
    with pytest.raises(ValueError, match="Password must be at least 8 characters"):
        await handler.signup(
            email="test@example.com",
            password="Ab1",
            name="Test User",
            phone="",
        )

    with pytest.raises(ValueError, match="at least one uppercase"):
        await handler.signup(
            email="test@example.com",
            password="alllowercase1",
            name="Test User",
            phone="",
        )

    with pytest.raises(ValueError, match="at least one number"):
        await handler.signup(
            email="test@example.com",
            password="NoNumbersHere",
            name="Test User",
            phone="",
        )


# ── Test: Rate Limit ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_rate_limit_exceeded(handler):
    # Sign up 5 times (the limit)
    for i in range(5):
        await handler.signup(
            email=f"user{i}@example.com",
            password="TestPass123",
            name=f"User {i}",
            phone="",
            ip_address="192.168.1.1",
        )

    # 6th signup should fail
    with pytest.raises(ValueError, match="Rate limit exceeded"):
        await handler.signup(
            email="overflow@example.com",
            password="TestPass123",
            name="Overflow User",
            phone="",
            ip_address="192.168.1.1",
        )


# ── Test: Get Signup Stats ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_signup_stats(handler):
    # Create some users
    await handler.signup(
        email="user1@example.com",
        password="TestPass123",
        name="User One",
        phone="",
    )
    await handler.signup(
        email="user2@example.com",
        password="TestPass123",
        name="User Two",
        phone="",
    )

    # Verify one email
    from backend.api.public_signup import _verification_codes
    code = _verification_codes.get("user1@example.com")
    await handler.verify_email("user1@example.com", code)

    since = datetime.now(timezone.utc) - timedelta(days=1)
    stats = await handler.get_signup_stats(since)

    assert stats.total_signups == 2
    assert stats.verified_emails == 1
    assert stats.unverified_emails == 1
    assert stats.trial_active == 2
    assert stats.signups_today >= 2


# ── Test: Duplicate Email ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_email_returns_error(handler, sample_signup_data):
    await handler.signup(**sample_signup_data)

    with pytest.raises(ValueError, match="Email already registered"):
        await handler.signup(**sample_signup_data)


# ── Test: Invalid Name ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_invalid_name_returns_error(handler):
    with pytest.raises(ValueError, match="Name must be at least 2 characters"):
        await handler.signup(
            email="test@example.com",
            password="TestPass123",
            name="A",
            phone="",
        )


# ── Test: Invalid Phone ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_signup_invalid_phone_returns_error(handler):
    with pytest.raises(ValueError, match="Invalid Bangladesh phone number"):
        await handler.signup(
            email="test@example.com",
            password="TestPass123",
            name="Test User",
            phone="12345",
        )


# ── Test: SignupResult Dataclass ──────────────────────────────────


def test_signup_result_defaults():
    result = SignupResult(
        user_id="test123",
        email="test@example.com",
        name="Test",
        firebase_uid="fb_test123",
    )
    assert result.tier == "free"
    assert result.email_verified is False
    assert result.message == ""


# ── Test: SignupStats Dataclass ───────────────────────────────────


def test_signup_stats_defaults():
    stats = SignupStats()
    assert stats.total_signups == 0
    assert stats.verified_emails == 0
    assert stats.unverified_emails == 0
    assert stats.trial_active == 0
    assert stats.trial_converted == 0
    assert stats.signups_today == 0
    assert stats.signups_this_week == 0
    assert stats.signups_this_month == 0
