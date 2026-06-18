"""
payments.py — Payment API Endpoints for Vision OS.

Handles bKash/Nagad manual payment submission and verification.
All endpoints require authentication.

Endpoints:
    POST /api/payments/submit — Submit a transaction ID for manual verification
    GET /api/payments/history — Get payment history for the current user
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])

# Global HybridCRUD instance (initialized in server.py)
hybrid_crud: HybridCRUD = None  # type: ignore


def get_crud() -> HybridCRUD:
    """Dependency to get the HybridCRUD instance."""
    if hybrid_crud is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Storage not initialized", "code": "STORAGE_UNAVAILABLE"},
        )
    return hybrid_crud


# ── Pricing ────────────────────────────────────────────────────

TIER_PRICES = {
    "guard": 400,
    "guard_pro": 800,
}


# ── Submit Transaction ID ──────────────────────────────────────


@router.post("/api/payments/submit")
async def submit_payment(
    tier: str,
    amount_bdt: int,
    transaction_id: str,
    payment_method: str = "bkash",
    notes: Optional[str] = None,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Submit a bKash/Nagad transaction ID for manual verification.

    The transaction will be recorded with status 'pending' and an
    admin will verify it manually. On verification, the user's tier
    will be upgraded.

    Args:
        tier: Target tier ('guard' or 'guard_pro').
        amount_bdt: Amount paid in BDT.
        transaction_id: The bKash/Nagad transaction ID.
        payment_method: 'bkash' or 'nagad'.
        notes: Optional notes.

    Returns:
        Dict with payment ID and status.
    """
    user_id = user.get("uid", "anonymous")

    # Validate tier
    if tier not in TIER_PRICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier '{tier}'. Valid tiers: {', '.join(TIER_PRICES.keys())}",
        )

    # Validate amount
    expected_amount = TIER_PRICES[tier]
    if amount_bdt != expected_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect amount for {tier}. Expected BDT {expected_amount}, got BDT {amount_bdt}.",
        )

    # Validate transaction ID
    if not transaction_id or len(transaction_id.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Transaction ID must be at least 5 characters.",
        )

    # Validate payment method
    if payment_method not in ("bkash", "nagad"):
        raise HTTPException(
            status_code=400,
            detail="Payment method must be 'bkash' or 'nagad'.",
        )

    try:
        payment = await crud.create_payment(
            user_id=user_id,
            tier=tier,
            amount_bdt=amount_bdt,
            transaction_id=transaction_id.strip(),
            payment_method=payment_method,
            notes=notes,
        )

        logger.info(
            "Payment submitted: user=%s tier=%s trx=%s method=%s",
            user_id, tier, transaction_id, payment_method,
        )

        return {
            "id": payment.id,
            "status": payment.status,
            "message": "Transaction ID submitted successfully. We will verify and upgrade your tier within 24 hours.",
        }
    except Exception as e:
        logger.error("Payment submission failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to record payment. Please try again later.",
        )


# ── Payment History ────────────────────────────────────────────


@router.get("/api/payments/history")
async def payment_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get payment history for the current user.

    Args:
        limit: Max number of records to return.
        offset: Pagination offset.

    Returns:
        Dict with list of payments.
    """
    user_id = user.get("uid", "anonymous")

    try:
        payments = await crud.get_user_payments(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        return {
            "payments": [
                {
                    "id": p.id,
                    "tier": p.tier,
                    "amount_bdt": p.amount_bdt,
                    "transaction_id": p.transaction_id,
                    "payment_method": p.payment_method,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "verified_at": p.verified_at.isoformat() if p.verified_at else None,
                }
                for p in payments
            ],
            "total": len(payments),
        }
    except Exception as e:
        logger.error("Payment history error: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to load payment history.",
        )
