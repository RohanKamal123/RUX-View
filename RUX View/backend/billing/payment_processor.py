"""
payment_processor.py — Payment Processing for Vision OS.

Bangladesh-focused payment methods: bKash, Nagad, Rocket.
Manual payment verification flow (admin confirms payment).
Payment receipt generation, history tracking, invoice generation,
coupon/discount code support, and refund processing.

Key decisions:
- D026: All calls async
- Manual verification for V1 (admin confirms via dashboard)
- bKash primary, Nagad secondary, Rocket tertiary
- Receipts sent via Telegram and email
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────

PAYMENT_METHODS = ["bkash", "nagad", "rocket"]
PAYMENT_STATUSES = ["pending", "verified", "rejected", "refunded"]
SESSION_EXPIRY_HOURS = 24


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class PaymentSession:
    """Represents a payment session awaiting verification."""

    payment_id: str
    user_id: str
    amount: float
    method: str  # bkash/nagad/rocket
    account_number: str  # user's bKash/Nagad number
    transaction_id: Optional[str] = None  # user's transaction ID
    status: str = "pending"  # pending/verified/rejected/refunded
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRY_HOURS)
    )


@dataclass
class PaymentRecord:
    """Record of a completed payment."""

    payment_id: str
    user_id: str
    user_email: str
    amount: float
    method: str
    status: str
    transaction_id: Optional[str] = None
    verified_by: Optional[str] = None  # admin ID
    verified_at: Optional[datetime] = None
    receipt_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Receipt:
    """Payment receipt details."""

    receipt_id: str
    payment_id: str
    user_id: str
    user_email: str
    amount: float
    method: str
    transaction_id: str
    date: datetime
    description: str
    receipt_number: str


@dataclass
class InvoiceItem:
    """Line item on an invoice."""

    description: str
    quantity: int
    unit_price: float
    total: float


@dataclass
class Invoice:
    """Invoice for business tier users."""

    invoice_id: str
    user_id: str
    period: str  # "April 2026"
    items: list[InvoiceItem]
    subtotal: float
    discount: float = 0.0
    total: float = 0.0
    due_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=15))
    status: str = "unpaid"  # unpaid/paid/overdue


@dataclass
class CouponResult:
    """Result of coupon validation."""

    valid: bool
    code: str
    discount_pct: float = 0.0
    discount_amount: float = 0.0
    expires_at: Optional[datetime] = None
    max_uses: int = 100
    current_uses: int = 0
    message: str = ""


@dataclass
class DiscountResult:
    """Result of applying a discount."""

    original_amount: float
    discount_amount: float
    final_amount: float
    coupon_code: str
    discount_pct: float


# ── In-Memory Store (replace with DB in production) ────────────

_payment_sessions: dict[str, PaymentSession] = {}
_payment_records: dict[str, list[PaymentRecord]] = {}
_coupons: dict[str, dict] = {}
_receipts: dict[str, Receipt] = {}
_invoices: dict[str, list[Invoice]] = {}
_receipt_counter: int = 1000


# ── PaymentProcessor ────────────────────────────────────────────


class PaymentProcessor:
    """Processes payments, verifications, receipts, and refunds."""

    async def initiate_payment(
        self, user_id: str, amount: float, method: str, account_number: str = ""
    ) -> PaymentSession:
        """Initiate a new payment session.

        Args:
            user_id: Unique user identifier.
            amount: Payment amount in BDT.
            method: Payment method (bkash/nagad/rocket).
            account_number: User's payment account number.

        Returns:
            PaymentSession with pending status.

        Raises:
            ValueError: If method is invalid.
        """
        if method not in PAYMENT_METHODS:
            raise ValueError(
                f"Invalid payment method: {method}. Must be one of {PAYMENT_METHODS}"
            )

        payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)

        session = PaymentSession(
            payment_id=payment_id,
            user_id=user_id,
            amount=amount,
            method=method,
            account_number=account_number,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(hours=SESSION_EXPIRY_HOURS),
        )

        _payment_sessions[payment_id] = session
        logger.info(
            "Payment initiated: %s for user: %s, amount: %.2f BDT, method: %s",
            payment_id, user_id, amount, method,
        )
        return session

    async def verify_payment(
        self, payment_id: str, admin_id: str
    ) -> PaymentSession:
        """Verify a pending payment (admin action).

        Args:
            payment_id: Payment session ID.
            admin_id: Admin user ID who verified.

        Returns:
            Updated PaymentSession with verified status.

        Raises:
            ValueError: If payment not found or not pending.
        """
        if payment_id not in _payment_sessions:
            raise ValueError(f"Payment not found: {payment_id}")

        session = _payment_sessions[payment_id]
        if session.status != "pending":
            raise ValueError(
                f"Payment {payment_id} is not pending. Current status: {session.status}"
            )

        session.status = "verified"

        # Create payment record
        record = PaymentRecord(
            payment_id=payment_id,
            user_id=session.user_id,
            user_email=f"{session.user_id}@visionos.app",  # placeholder
            amount=session.amount,
            method=session.method,
            status="verified",
            transaction_id=session.transaction_id,
            verified_by=admin_id,
            verified_at=datetime.now(timezone.utc),
        )

        if session.user_id not in _payment_records:
            _payment_records[session.user_id] = []
        _payment_records[session.user_id].append(record)

        logger.info(
            "Payment verified: %s by admin: %s", payment_id, admin_id
        )
        return session

    async def reject_payment(
        self, payment_id: str, admin_id: str, reason: str
    ) -> PaymentSession:
        """Reject a pending payment (admin action).

        Args:
            payment_id: Payment session ID.
            admin_id: Admin user ID who rejected.
            reason: Reason for rejection.

        Returns:
            Updated PaymentSession with rejected status.

        Raises:
            ValueError: If payment not found or not pending.
        """
        if payment_id not in _payment_sessions:
            raise ValueError(f"Payment not found: {payment_id}")

        session = _payment_sessions[payment_id]
        if session.status != "pending":
            raise ValueError(
                f"Payment {payment_id} is not pending. Current status: {session.status}"
            )

        session.status = "rejected"

        logger.info(
            "Payment rejected: %s by admin: %s. Reason: %s",
            payment_id, admin_id, reason,
        )
        return session

    async def get_payment_status(self, payment_id: str) -> str:
        """Get the status of a payment.

        Args:
            payment_id: Payment session ID.

        Returns:
            Status string (pending/verified/rejected/refunded).

        Raises:
            ValueError: If payment not found.
        """
        if payment_id not in _payment_sessions:
            raise ValueError(f"Payment not found: {payment_id}")
        return _payment_sessions[payment_id].status

    async def get_user_payments(
        self, user_id: str, limit: int = 20
    ) -> list[PaymentRecord]:
        """Get payment records for a user.

        Args:
            user_id: Unique user identifier.
            limit: Maximum number of records.

        Returns:
            List of PaymentRecord.
        """
        records = _payment_records.get(user_id, [])
        return records[-limit:]

    async def get_pending_payments(self) -> list[PaymentRecord]:
        """Get all pending payments awaiting admin verification.

        Returns:
            List of pending PaymentRecord.
        """
        pending = []
        for session in _payment_sessions.values():
            if session.status == "pending":
                pending.append(
                    PaymentRecord(
                        payment_id=session.payment_id,
                        user_id=session.user_id,
                        user_email=f"{session.user_id}@visionos.app",
                        amount=session.amount,
                        method=session.method,
                        status="pending",
                        transaction_id=session.transaction_id,
                        created_at=session.created_at,
                    )
                )
        return pending

    async def generate_receipt(self, payment_id: str) -> Receipt:
        """Generate a receipt for a verified payment.

        Args:
            payment_id: Payment session ID.

        Returns:
            Receipt with payment details.

        Raises:
            ValueError: If payment not found or not verified.
        """
        if payment_id not in _payment_sessions:
            raise ValueError(f"Payment not found: {payment_id}")

        session = _payment_sessions[payment_id]
        if session.status != "verified":
            raise ValueError(
                f"Cannot generate receipt. Payment {payment_id} status: {session.status}"
            )

        global _receipt_counter
        _receipt_counter += 1
        receipt_id = f"RCP-{_receipt_counter:06d}"

        receipt = Receipt(
            receipt_id=receipt_id,
            payment_id=payment_id,
            user_id=session.user_id,
            user_email=f"{session.user_id}@visionos.app",
            amount=session.amount,
            method=session.method,
            transaction_id=session.transaction_id or "N/A",
            date=datetime.now(timezone.utc),
            description=f"Vision OS {session.method.title()} Payment",
            receipt_number=receipt_id,
        )

        _receipts[receipt_id] = receipt
        logger.info("Receipt generated: %s for payment: %s", receipt_id, payment_id)
        return receipt

    async def generate_invoice(self, user_id: str, period: str) -> Invoice:
        """Generate an invoice for a business tier user.

        Args:
            user_id: Unique user identifier.
            period: Billing period (e.g. "April 2026").

        Returns:
            Invoice with line items.
        """
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"

        items = [
            InvoiceItem(
                description=f"Vision OS {period} — Camera Monitoring",
                quantity=1,
                unit_price=499.0,
                total=499.0,
            ),
            InvoiceItem(
                description=f"AI Analytics & Detection Services",
                quantity=1,
                unit_price=299.0,
                total=299.0,
            ),
        ]

        subtotal = sum(item.total for item in items)
        total = subtotal

        invoice = Invoice(
            invoice_id=invoice_id,
            user_id=user_id,
            period=period,
            items=items,
            subtotal=subtotal,
            total=total,
            status="unpaid",
        )

        if user_id not in _invoices:
            _invoices[user_id] = []
        _invoices[user_id].append(invoice)

        logger.info(
            "Invoice generated: %s for user: %s, period: %s, total: %.2f",
            invoice_id, user_id, period, total,
        )
        return invoice

    async def process_refund(
        self, payment_id: str, admin_id: str, reason: str
    ) -> PaymentSession:
        """Process a refund for a verified payment.

        Args:
            payment_id: Payment session ID.
            admin_id: Admin user ID processing the refund.
            reason: Reason for refund.

        Returns:
            Updated PaymentSession with refunded status.

        Raises:
            ValueError: If payment not found or not verified.
        """
        if payment_id not in _payment_sessions:
            raise ValueError(f"Payment not found: {payment_id}")

        session = _payment_sessions[payment_id]
        if session.status != "verified":
            raise ValueError(
                f"Cannot refund. Payment {payment_id} status: {session.status}"
            )

        session.status = "refunded"

        logger.info(
            "Payment refunded: %s by admin: %s. Reason: %s",
            payment_id, admin_id, reason,
        )
        return session

    async def validate_coupon(self, code: str) -> CouponResult:
        """Validate a coupon/discount code.

        Args:
            code: Coupon code string.

        Returns:
            CouponResult with validity and discount info.
        """
        code_upper = code.upper().strip()

        # Check if coupon exists
        coupon = _coupons.get(code_upper)
        if not coupon:
            # Default coupons for testing
            default_coupons = {
                "WELCOME10": {
                    "discount_pct": 10,
                    "discount_amount": 0,
                    "max_uses": 100,
                    "current_uses": 5,
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
                },
                "SAVE50": {
                    "discount_pct": 0,
                    "discount_amount": 50,
                    "max_uses": 50,
                    "current_uses": 10,
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=15),
                },
                "EXPIRED20": {
                    "discount_pct": 20,
                    "discount_amount": 0,
                    "max_uses": 100,
                    "current_uses": 50,
                    "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                },
                "MAXED10": {
                    "discount_pct": 10,
                    "discount_amount": 0,
                    "max_uses": 10,
                    "current_uses": 10,
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
                },
            }
            coupon = default_coupons.get(code_upper)

        if not coupon:
            return CouponResult(
                valid=False,
                code=code_upper,
                message="Invalid coupon code.",
            )

        # Check expiry
        if coupon["expires_at"] and coupon["expires_at"] < datetime.now(timezone.utc):
            return CouponResult(
                valid=False,
                code=code_upper,
                message="This coupon has expired.",
                expires_at=coupon["expires_at"],
            )

        # Check max uses
        if coupon["current_uses"] >= coupon["max_uses"]:
            return CouponResult(
                valid=False,
                code=code_upper,
                message="This coupon has reached its maximum uses.",
                max_uses=coupon["max_uses"],
                current_uses=coupon["current_uses"],
            )

        return CouponResult(
            valid=True,
            code=code_upper,
            discount_pct=coupon["discount_pct"],
            discount_amount=coupon["discount_amount"],
            expires_at=coupon["expires_at"],
            max_uses=coupon["max_uses"],
            current_uses=coupon["current_uses"],
            message="Coupon applied successfully!",
        )

    async def apply_coupon(self, user_id: str, code: str) -> DiscountResult:
        """Apply a coupon code and calculate discount.

        Args:
            user_id: Unique user identifier.
            code: Coupon code string.

        Returns:
            DiscountResult with original, discount, and final amounts.
        """
        coupon_result = await self.validate_coupon(code)

        if not coupon_result.valid:
            return DiscountResult(
                original_amount=0,
                discount_amount=0,
                final_amount=0,
                coupon_code=code,
                discount_pct=0,
            )

        # Get user's current bill amount
        try:
            from backend.billing.subscription_manager import _subscriptions
            sub = _subscriptions.get(user_id)
            original_amount = sub.total_monthly if sub else 499.0
        except Exception:
            original_amount = 499.0

        # Calculate discount
        pct_discount = original_amount * (coupon_result.discount_pct / 100)
        flat_discount = coupon_result.discount_amount
        total_discount = max(pct_discount, flat_discount)
        final_amount = max(0, original_amount - total_discount)

        return DiscountResult(
            original_amount=original_amount,
            discount_amount=total_discount,
            final_amount=final_amount,
            coupon_code=code,
            discount_pct=coupon_result.discount_pct,
        )

    async def add_coupon(
        self,
        code: str,
        discount_pct: float = 0,
        discount_amount: float = 0,
        max_uses: int = 100,
        expires_in_days: int = 30,
    ) -> dict:
        """Add a new coupon code (admin function).

        Args:
            code: Coupon code.
            discount_pct: Percentage discount.
            discount_amount: Flat discount amount.
            max_uses: Maximum number of uses.
            expires_in_days: Days until expiry.

        Returns:
            Dict with coupon details.
        """
        coupon = {
            "discount_pct": discount_pct,
            "discount_amount": discount_amount,
            "max_uses": max_uses,
            "current_uses": 0,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        }
        _coupons[code.upper().strip()] = coupon
        logger.info("Coupon added: %s", code)
        return {"code": code, **coupon, "expires_at": coupon["expires_at"].isoformat()}
