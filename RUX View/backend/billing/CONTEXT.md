# CONTEXT.md — Billing Module
# Module: backend/billing/
# Sprint: 5.3
# Purpose: bKash payment + subscription management

---

## What This Module Does

Single file handling all billing operations:

1. **bkash_client.py** — bKash payment API integration

---

## File: bkash_client.py

### Functions
```python
async def initiate_payment(user_id: str, amount: float, camera_count: int) -> dict
    # Returns: {payment_id, bkash_url, status}

async def verify_payment(payment_id: str) -> dict
    # Returns: {verified: bool, transaction_id, amount}

async def create_subscription(user_id: str, tier: str, camera_count: int) -> dict
    # Returns: {subscription_id, start_date, end_date}

async def cancel_subscription(user_id: str) -> bool

async def handle_webhook(payload: dict) -> dict
    # bKash payment notification webhook
    # Updates user tier + subscription status
```

### Pricing
```
Free:       0 BDT (1 month trial, then restricted)
Household:  299 BDT per camera per month
Business:   499 BDT per camera per month
```

### Trial Logic
- 1 month full trial on signup
- 7 day grace period after trial ends
- Warning messages on day 1, 5, 7 via Telegram
- Data deleted after grace period

### Key Decisions
- **D011** — bKash (NOT Stripe) — Bangladesh market
- **D021** — Per-camera pricing (not per-user)

## Dependencies
- httpx (async HTTP)
- backend/storage/database.py (user updates)

## Called By
- backend/api/billing.py
