"""

test_email_service.py — Tests for Email Notification Service (Sprint 11.3).

Tests cover:
- All email types: welcome, verification, password reset, payment receipt,
  trial warning, trial expired, weekly digest, custom
- Email history retrieval
- Email stats calculation
- Bounce handling
- Rate limiting
- HTML template rendering
"""

import pytest
pytest.importorskip("backend.notifications")  # skip if not installed

import pytest
from datetime import datetime, timedelta, timezone
from backend.notifications.email_service import (
    EmailService,
    EmailRecord,
    EmailStats,
    _reset_store,
)


@pytest.fixture
def service():
    """Create a fresh email service for each test."""
    _reset_store()
    return EmailService()


# ── Test: Send Welcome Email ──────────────────────────────────────


@pytest.mark.asyncio
async def test_send_welcome_email_returns_true(service):
    result = await service.send_welcome_email(
        user_id="user123",
        email="test@example.com",
        name="Test User",
    )
    assert result is True


# ── Test: Send Verification Email ─────────────────────────────────


@pytest.mark.asyncio
async def test_send_verification_email_contains_code(service):
    result = await service.send_verification_email(
        email="test@example.com",
        code="123456",
    )
    assert result is True

    # Check history contains the verification email
    history = await service.get_email_history("system")
    assert len(history) == 1
    assert history[0].template == "verification"
    assert history[0].to_email == "test@example.com"


# ── Test: Send Password Reset Email ───────────────────────────────


@pytest.mark.asyncio
async def test_send_password_reset_email(service):
    result = await service.send_password_reset_email(
        email="test@example.com",
        code="654321",
    )
    assert result is True


# ── Test: Send Payment Receipt ────────────────────────────────────


@pytest.mark.asyncio
async def test_send_payment_receipt(service):
    result = await service.send_payment_receipt(
        user_id="user123",
        payment_id="pay_abc123",
    )
    assert result is True


# ── Test: Send Trial Expiry Warning ───────────────────────────────


@pytest.mark.asyncio
async def test_send_trial_expiry_warning(service):
    result = await service.send_trial_expiry_warning(
        user_id="user123",
        days_remaining=7,
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_trial_expired(service):
    result = await service.send_trial_expired(user_id="user123")
    assert result is True


# ── Test: Send Weekly Digest ──────────────────────────────────────


@pytest.mark.asyncio
async def test_send_weekly_digest(service):
    digest_data = {
        "total_events": 150,
        "alerts_sent": 23,
        "persons_detected": 45,
        "active_cameras": 3,
    }
    result = await service.send_weekly_digest(
        user_id="user123",
        digest_data=digest_data,
    )
    assert result is True


# ── Test: Send Custom Email ───────────────────────────────────────


@pytest.mark.asyncio
async def test_send_custom_email(service):
    result = await service.send_custom_email(
        email="test@example.com",
        subject="Custom Subject",
        template="welcome",
        data={"name": "Test", "dashboard_url": "https://visionos.com", "help_url": "https://visionos.com/help"},
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_custom_email_unknown_template(service):
    result = await service.send_custom_email(
        email="test@example.com",
        subject="Test",
        template="nonexistent",
        data={},
    )
    assert result is False


# ── Test: Get Email History ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_email_history_returns_list(service):
    # Send a few emails
    await service.send_welcome_email("user123", "test@example.com", "Test")
    await service.send_verification_email("test@example.com", "123456")
    await service.send_password_reset_email("test@example.com", "654321")

    # Get history for system user (verification + password reset)
    history = await service.get_email_history("system")
    assert len(history) == 2

    # Get history for user123 (welcome)
    history = await service.get_email_history("user123")
    assert len(history) == 1
    assert history[0].template == "welcome"


# ── Test: Get Email Stats ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_email_stats(service):
    # Send some emails
    await service.send_welcome_email("user1", "user1@example.com", "User 1")
    await service.send_verification_email("user2@example.com", "123456")
    await service.send_password_reset_email("user3@example.com", "654321")

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    stats = await service.get_email_stats(since)

    assert stats.total_sent == 3
    assert stats.delivered == 3
    assert stats.bounced == 0
    assert stats.opened == 0
    assert stats.clicked == 0
    assert stats.delivery_rate == 100.0


# ── Test: Email Bounce Handling ───────────────────────────────────


@pytest.mark.asyncio
async def test_email_bounce_handling(service):
    # Simulate a bounce by creating a record directly
    from backend.notifications.email_service import _email_history

    record = EmailRecord(
        email_id="bounce001",
        user_id="user123",
        to_email="bounce@example.com",
        subject="Test Bounce",
        template="welcome",
        status="bounced",
        error="Invalid email address",
    )
    _email_history.append(record)

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    stats = await service.get_email_stats(since)

    assert stats.total_sent == 1
    assert stats.bounced == 1
    assert stats.delivered == 0


# ── Test: Rate Limit Enforced ─────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_enforced(service):
    # Send 100 emails (the limit)
    for i in range(100):
        result = await service.send_welcome_email(
            user_id="rate_limited_user",
            email=f"test{i}@example.com",
            name=f"User {i}",
        )
        assert result is True, f"Email {i} should succeed"

    # 101st email should fail
    result = await service.send_welcome_email(
        user_id="rate_limited_user",
        email="overflow@example.com",
        name="Overflow User",
    )
    assert result is False, "Rate limited email should fail"


# ── Test: HTML Template Renders Correctly ─────────────────────────


def test_html_template_renders_correctly(service):
    """Verify template rendering replaces variables correctly."""
    rendered = service._render_template("welcome", {
        "name": "John Doe",
        "dashboard_url": "https://visionos.com/dashboard",
        "help_url": "https://visionos.com/help",
    })

    assert "John Doe" in rendered, "Name should be rendered"
    assert "Welcome to Vision OS" in rendered, "Title should be present"
    assert "30-day free trial" in rendered, "Trial info should be present"
    assert "https://visionos.com/dashboard" in rendered, "Dashboard URL should be rendered"
    assert "https://visionos.com/help" in rendered, "Help URL should be rendered"


def test_verification_template_renders_code(service):
    """Verify verification template renders the code."""
    rendered = service._render_template("verification", {
        "code": "123456",
        "verify_url": "https://visionos.com/verify?code=123456&email=test@example.com",
    })

    assert "123456" in rendered, "Verification code should be rendered"
    assert "Verify Your Email" in rendered, "Title should be present"


def test_password_reset_template_renders(service):
    """Verify password reset template renders correctly."""
    rendered = service._render_template("password_reset", {"code": "654321"})

    assert "654321" in rendered, "Reset code should be rendered"
    assert "Reset Your Password" in rendered, "Title should be present"


def test_payment_receipt_template_renders(service):
    """Verify payment receipt template renders correctly."""
    rendered = service._render_template("payment_receipt", {
        "receipt_number": "RCP-ABC12345",
        "amount": "299",
        "payment_date": "April 30, 2026",
        "plan_name": "Household",
    })

    assert "RCP-ABC12345" in rendered, "Receipt number should be rendered"
    assert "299" in rendered, "Amount should be rendered"
    assert "Household" in rendered, "Plan name should be rendered"


def test_trial_warning_template_renders(service):
    """Verify trial warning template renders correctly."""
    rendered = service._render_template("trial_warning", {
        "days_remaining": "7",
        "upgrade_url": "https://visionos.com/payment",
    })

    assert "7" in rendered, "Days remaining should be rendered"
    assert "Your Trial Ends in 7 Days" in rendered, "Subject should be in template"


def test_trial_expired_template_renders(service):
    """Verify trial expired template renders correctly."""
    rendered = service._render_template("trial_expired", {
        "upgrade_url": "https://visionos.com/payment",
    })

    assert "Your Trial Has Ended" in rendered, "Title should be present"
    assert "7-day grace period" in rendered, "Grace period should be mentioned"


def test_weekly_digest_template_renders(service):
    """Verify weekly digest template renders correctly."""
    rendered = service._render_template("weekly_digest", {
        "total_events": "150",
        "alerts_sent": "23",
        "persons_detected": "45",
        "active_cameras": "3",
        "dashboard_url": "https://visionos.com/dashboard",
    })

    assert "150" in rendered, "Total events should be rendered"
    assert "23" in rendered, "Alerts sent should be rendered"
    assert "45" in rendered, "Persons detected should be rendered"
    assert "3" in rendered, "Active cameras should be rendered"


# ── Test: EmailRecord Dataclass ───────────────────────────────────


def test_email_record_defaults():
    record = EmailRecord(
        email_id="test001",
        user_id="user123",
        to_email="test@example.com",
        subject="Test",
        template="welcome",
    )
    assert record.status == "sent"
    assert record.delivered_at is None
    assert record.opened_at is None
    assert record.error is None


# ── Test: EmailStats Dataclass ────────────────────────────────────


def test_email_stats_defaults():
    stats = EmailStats()
    assert stats.total_sent == 0
    assert stats.delivered == 0
    assert stats.bounced == 0
    assert stats.opened == 0
    assert stats.clicked == 0
    assert stats.delivery_rate == 0.0
    assert stats.open_rate == 0.0
    assert stats.click_rate == 0.0
