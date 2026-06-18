"""
test_payment_processor.py — Tests for Payment Processing.
"""

import pytest
from datetime import datetime, timedelta, timezone
from backend.billing.payment_processor import (
    PaymentProcessor,
    PaymentSession,
    PaymentRecord,
    Receipt,
    Invoice,
    InvoiceItem,
    CouponResult,
    DiscountResult,
    SESSION_EXPIRY_HOURS,
)


@pytest.fixture
def processor():
    """Create a fresh PaymentProcessor for each test."""
    from backend.billing.payment_processor import (
        _payment_sessions, _payment_records, _coupons, _receipts, _invoices,
    )
    _payment_sessions.clear()
    _payment_records.clear()
    _coupons.clear()
    _receipts.clear()
    _invoices.clear()
    return PaymentProcessor()


@pytest.fixture
def sample_user():
    return "test_user_pay"


@pytest.fixture
def sample_admin():
    return "admin_001"


# ── Test: Initiate Payment ──────────────────────────────────────


@pytest.mark.asyncio
async def test_initiate_payment_creates_session(processor, sample_user):
    session = await processor.initiate_payment(
        sample_user, 299.0, "bkash", "017XXXXXXXX"
    )

    assert session.payment_id.startswith("PAY-")
    assert session.user_id == sample_user
    assert session.amount == 299.0
    assert session.method == "bkash"
    assert session.account_number == "017XXXXXXXX"
    assert session.status == "pending"
    assert session.expires_at > session.created_at


@pytest.mark.asyncio
async def test_initiate_payment_invalid_method(processor, sample_user):
    with pytest.raises(ValueError, match="Invalid payment method"):
        await processor.initiate_payment(sample_user, 100, "stripe", "")


# ── Test: Verify Payment ────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_payment_marks_verified(processor, sample_user, sample_admin):
    session = await processor.initiate_payment(sample_user, 299, "bkash", "017XXX")
    session.transaction_id = "TRX123456"

    result = await processor.verify_payment(session.payment_id, sample_admin)

    assert result.status == "verified"

    # Check record was created
    records = await processor.get_user_payments(sample_user)
    assert len(records) == 1
    assert records[0].verified_by == sample_admin


@pytest.mark.asyncio
async def test_verify_payment_not_found(processor, sample_admin):
    with pytest.raises(ValueError, match="Payment not found"):
        await processor.verify_payment("PAY-NONEXISTENT", sample_admin)


# ── Test: Reject Payment ────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_payment_with_reason(processor, sample_user, sample_admin):
    session = await processor.initiate_payment(sample_user, 299, "nagad", "017XXX")

    result = await processor.reject_payment(
        session.payment_id, sample_admin, "Incorrect amount"
    )

    assert result.status == "rejected"


# ── Test: Get Payment Status ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_payment_status_pending(processor, sample_user):
    session = await processor.initiate_payment(sample_user, 100, "bkash", "017XXX")

    status = await processor.get_payment_status(session.payment_id)
    assert status == "pending"


# ── Test: Get User Payments ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_payments_returns_list(processor, sample_user, sample_admin):
    s1 = await processor.initiate_payment(sample_user, 299, "bkash", "017XXX")
    s2 = await processor.initiate_payment(sample_user, 499, "nagad", "017XXX")

    await processor.verify_payment(s1.payment_id, sample_admin)
    await processor.verify_payment(s2.payment_id, sample_admin)

    records = await processor.get_user_payments(sample_user)
    assert len(records) == 2


# ── Test: Get Pending Payments ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_pending_payments(processor, sample_user):
    await processor.initiate_payment(sample_user, 299, "bkash", "017XXX")
    await processor.initiate_payment("user2", 499, "rocket", "018XXX")

    pending = await processor.get_pending_payments()
    assert len(pending) == 2


# ── Test: Generate Receipt ──────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_receipt_contains_details(
    processor, sample_user, sample_admin
):
    session = await processor.initiate_payment(
        sample_user, 299, "bkash", "017XXXXXXXXX"
    )
    session.transaction_id = "TRX999"
    await processor.verify_payment(session.payment_id, sample_admin)

    receipt = await processor.generate_receipt(session.payment_id)

    assert receipt.receipt_id.startswith("RCP-")
    assert receipt.payment_id == session.payment_id
    assert receipt.amount == 299.0
    assert receipt.method == "bkash"
    assert receipt.transaction_id == "TRX999"


# ── Test: Generate Invoice ──────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_invoice_for_business(processor, sample_user):
    invoice = await processor.generate_invoice(sample_user, "April 2026")

    assert invoice.invoice_id.startswith("INV-")
    assert invoice.period == "April 2026"
    assert len(invoice.items) > 0
    assert invoice.subtotal > 0
    assert invoice.total > 0
    assert invoice.status == "unpaid"


# ── Test: Process Refund ────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_refund(processor, sample_user, sample_admin):
    session = await processor.initiate_payment(sample_user, 299, "bkash", "017XXX")
    await processor.verify_payment(session.payment_id, sample_admin)

    result = await processor.process_refund(
        session.payment_id, sample_admin, "Customer request"
    )

    assert result.status == "refunded"


# ── Test: Validate Coupon ───────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_coupon_valid(processor):
    result = await processor.validate_coupon("WELCOME10")

    assert result.valid is True
    assert result.code == "WELCOME10"
    assert result.discount_pct == 10
    assert "successfully" in result.message


@pytest.mark.asyncio
async def test_validate_coupon_expired(processor):
    result = await processor.validate_coupon("EXPIRED20")

    assert result.valid is False
    assert "expired" in result.message


@pytest.mark.asyncio
async def test_validate_coupon_max_uses_reached(processor):
    result = await processor.validate_coupon("MAXED10")

    assert result.valid is False
    assert "maximum uses" in result.message


@pytest.mark.asyncio
async def test_validate_coupon_invalid(processor):
    result = await processor.validate_coupon("INVALID123")

    assert result.valid is False
    assert "Invalid coupon" in result.message


# ── Test: Apply Coupon ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_coupon_calculates_discount(processor, sample_user):
    # Create a subscription first
    from backend.billing.subscription_manager import SubscriptionManager
    mgr = SubscriptionManager()
    await mgr.create_subscription(sample_user, "household", 2)

    result = await processor.apply_coupon(sample_user, "WELCOME10")

    assert result.original_amount > 0
    assert result.discount_amount > 0
    assert result.final_amount < result.original_amount
    assert result.coupon_code == "WELCOME10"


# ── Test: Payment Session Expiry ────────────────────────────────


@pytest.mark.asyncio
async def test_payment_session_expires_after_24h(processor, sample_user):
    session = await processor.initiate_payment(sample_user, 299, "bkash", "017XXX")

    expected_expiry = session.created_at + timedelta(hours=SESSION_EXPIRY_HOURS)
    assert abs((session.expires_at - expected_expiry).total_seconds()) < 5


# ── Test: Add Coupon ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_coupon(processor):
    result = await processor.add_coupon(
        "TEST50", discount_pct=50, max_uses=10, expires_in_days=60
    )

    assert result["code"] == "TEST50"
    assert result["discount_pct"] == 50
    assert result["max_uses"] == 10

    # Validate it
    validation = await processor.validate_coupon("TEST50")
    assert validation.valid is True
    assert validation.discount_pct == 50


# ── Test: Dataclass Defaults ────────────────────────────────────


def test_payment_session_defaults():
    now = datetime.now(timezone.utc)
    session = PaymentSession(
        payment_id="PAY-TEST",
        user_id="user1",
        amount=299.0,
        method="bkash",
        account_number="017XXX",
    )
    assert session.status == "pending"
    assert session.expires_at > session.created_at


def test_invoice_item():
    item = InvoiceItem(
        description="Camera Monitoring",
        quantity=3,
        unit_price=299.0,
        total=897.0,
    )
    assert item.total == 897.0
