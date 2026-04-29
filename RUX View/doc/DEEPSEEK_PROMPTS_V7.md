# Vision OS V7 — DeepSeek Coding Prompts
# User Onboarding & Subscription Management
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 9.1 — User Onboarding Flow
### Files: backend/core/onboarding.py, backend/dashboard/templates/onboarding.html, backend/dashboard/static/onboarding.js, backend/dashboard/static/onboarding.css
### Tests: backend/tests/unit/test_onboarding.py

```
You are building the user onboarding flow for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + FastAPI + Jinja2 + JavaScript + CSS
- Multi-step onboarding wizard for new users
- Steps: 1) Account creation, 2) Location setup, 3) Camera connection, 4) Mode selection, 5) Notification config, 6) Payment setup
- Progress indicator showing current step
- Skip-able steps (can configure later)
- Supports up to 10 cameras during onboarding
- No camera limit enforced
- Mobile-first responsive design matching dark navy theme

KEY DECISIONS:
- D012: Firebase Auth for login
- D026: All calls async
- Onboarding progress saved to database (can resume)

FUNCTIONS TO IMPLEMENT:

1. OnboardingManager class:
   - start_onboarding(user_id: str) -> OnboardingSession
   - get_onboarding_state(user_id: str) -> OnboardingSession
   - complete_step(user_id: str, step: int, data: dict) -> OnboardingSession
   - skip_step(user_id: str, step: int) -> OnboardingSession
   - go_back_step(user_id: str, step: int) -> OnboardingSession
   - complete_onboarding(user_id: str) -> dict
   - is_onboarding_complete(user_id: str) -> bool
   - get_onboarding_progress(user_id: str) -> OnboardingProgress

2. OnboardingSession dataclass:
   - user_id: str
   - current_step: int (1-6)
   - completed_steps: list[int]
   - skipped_steps: list[int]
   - step_data: dict[int, dict]  # data per step
   - started_at: datetime
   - last_activity: datetime
   - is_complete: bool

3. OnboardingProgress dataclass:
   - total_steps: int = 6
   - completed: int
   - skipped: int
   - remaining: int
   - progress_pct: float
   - current_step_name: str

4. Step names: ["Account", "Location", "Camera", "Mode", "Notifications", "Payment"]

ONBOARDING STEPS:

Step 1 - Account:
   - Email verification status
   - Name, phone number
   - Company/business name (optional)
   - Timezone (default: Asia/Dhaka)

Step 2 - Location:
   - Location name (e.g., "Home - Mirpur")
   - Address
   - Location type (home/shop/office/godown/other)
   - Business hours (if shop/office)

Step 3 - Camera:
   - Camera name
   - RTSP URL
   - Camera credentials
   - Camera type (indoor/outdoor/doorbell/PTZ)
   - Add multiple cameras (up to 10)
   - Test connection button

Step 4 - Mode:
   - Select camera mode per camera
   - Indoor / Outdoor / Parking / Mixed / Shop
   - Draw ignore zones (optional)
   - Set business hours (if applicable)

Step 5 - Notifications:
   - Telegram setup (QR code scan)
   - Alert preferences (LOW/MEDIUM/HIGH/EMERGENCY)
   - Quiet hours
   - SMS fallback (optional)

Step 6 - Payment:
   - Select tier (free trial / household / business)
   - bKash/Nagad payment info
   - Coupon code (optional)
   - Summary + confirmation

TEST CASES:
test_start_onboarding_creates_session, test_get_onboarding_state_returns_current_step, test_complete_step_advances_progress, test_skip_step_marks_as_skipped, test_go_back_step_returns_to_previous, test_complete_onboarding_marks_done, test_is_onboarding_complete_true_after_completion, test_is_onboarding_complete_false_when_incomplete, test_onboarding_progress_calculation, test_resume_onboarding_from_saved_state, test_step_data_persisted_correctly, test_concurrent_onboarding_sessions

OUTPUT: Generate onboarding.py, onboarding.html, onboarding.js, onboarding.css, and test_onboarding.py. Use async/await throughout.
```

---

## SPRINT 9.2 — Subscription Management
### Files: backend/billing/subscription_manager.py
### Tests: backend/tests/unit/test_subscription_manager.py

```
You are building the subscription management module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + PostgreSQL
- Manages user subscriptions with tier-based features
- Tiers: free (trial), household (299 BDT/camera/month), business (499 BDT/camera/month)
- No camera limit enforced (system supports up to 10 cameras)
- Per-camera billing calculation
- Trial period management (30 days free)
- Auto-renewal and expiry handling
- Grace period before data deletion
- Subscription history tracking

KEY DECISIONS:
- D014: Three pricing tiers (free/household/business)
- D026: All calls async
- Billing per camera per month (not flat rate)
- 7-day grace period after expiry

FUNCTIONS TO IMPLEMENT:

1. SubscriptionManager class:
   - create_subscription(user_id: str, tier: str, camera_count: int) -> Subscription
   - get_subscription(user_id: str) -> Subscription
   - update_subscription(user_id: str, updates: dict) -> Subscription
   - change_tier(user_id: str, new_tier: str) -> Subscription
   - cancel_subscription(user_id: str) -> Subscription
   - renew_subscription(user_id: str) -> Subscription
   - calculate_bill(user_id: str) -> BillSummary
   - get_billing_history(user_id: str, limit: int = 12) -> list[BillSummary]
   - check_trial_status(user_id: str) -> TrialStatus
   - extend_trial(user_id: str, days: int) -> Subscription
   - handle_expiry(user_id: str) -> dict
   - get_expired_subscriptions() -> list[str]
   - get_subscriptions_due_today() -> list[str]

2. Subscription dataclass:
   - user_id: str
   - tier: str (free/household/business)
   - status: str (active/trial/expired/cancelled/grace)
   - camera_count: int
   - price_per_camera: float
   - total_monthly: float
   - started_at: datetime
   - trial_ends_at: Optional[datetime]
   - current_period_start: datetime
   - current_period_end: datetime
   - cancelled_at: Optional[datetime]
   - grace_ends_at: Optional[datetime]
   - auto_renew: bool

3. BillSummary dataclass:
   - user_id: str
   - period_start: datetime
   - period_end: datetime
   - tier: str
   - camera_count: int
   - price_per_camera: float
   - subtotal: float
   - discount: float
   - total: float
   - paid: bool
   - paid_at: Optional[datetime]
   - payment_method: Optional[str]

4. TrialStatus dataclass:
   - is_trial: bool
   - days_remaining: int
   - total_trial_days: int
   - trial_ends_at: datetime
   - will_expire_soon: bool  # < 3 days remaining

TEST CASES:
test_create_subscription_free_tier, test_create_subscription_household, test_create_subscription_business, test_get_subscription_returns_data, test_update_subscription_changes_fields, test_change_tier_updates_pricing, test_cancel_subscription_sets_cancelled, test_renew_subscription_extends_period, test_calculate_bill_correct_amount, test_billing_history_returns_list, test_trial_status_days_remaining, test_extend_trial_adds_days, test_handle_expiry_enters_grace, test_get_expired_subscriptions, test_subscriptions_due_today, test_camera_count_updates_bill

OUTPUT: Generate subscription_manager.py and test_subscription_manager.py. Use async/await throughout.
```

---

## SPRINT 9.3 — Payment Integration
### Files: backend/billing/payment_processor.py
### Tests: backend/tests/unit/test_payment_processor.py

```
You are building the payment processing module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Bangladesh-focused payment methods: bKash, Nagad, Rocket
- Manual payment verification flow (admin confirms payment)
- Payment receipt generation
- Payment history tracking
- Invoice generation for business tier
- Coupon/discount code support
- Refund processing

KEY DECISIONS:
- D026: All calls async
- Manual verification for V1 (admin confirms via dashboard)
- bKash primary, Nagad secondary, Rocket tertiary
- Receipts sent via Telegram and email

FUNCTIONS TO IMPLEMENT:

1. PaymentProcessor class:
   - initiate_payment(user_id: str, amount: float, method: str) -> PaymentSession
   - verify_payment(payment_id: str, admin_id: str) -> PaymentResult
   - reject_payment(payment_id: str, admin_id: str, reason: str) -> PaymentResult
   - get_payment_status(payment_id: str) -> PaymentStatus
   - get_user_payments(user_id: str, limit: int = 20) -> list[PaymentRecord]
   - get_pending_payments() -> list[PaymentRecord]
   - generate_receipt(payment_id: str) -> Receipt
   - generate_invoice(user_id: str, period: str) -> Invoice
   - process_refund(payment_id: str, admin_id: str, reason: str) -> PaymentResult
   - validate_coupon(code: str) -> CouponResult
   - apply_coupon(user_id: str, code: str) -> DiscountResult

2. PaymentSession dataclass:
   - payment_id: str
   - user_id: str
   - amount: float
   - method: str (bkash/nagad/rocket)
   - account_number: str  # user's bKash/Nagad number
   - transaction_id: Optional[str]  # user's transaction ID
   - status: str (pending/verified/rejected/refunded)
   - created_at: datetime
   - expires_at: datetime  # 24 hours

3. PaymentRecord dataclass:
   - payment_id: str
   - user_id: str
   - user_email: str
   - amount: float
   - method: str
   - status: str
   - transaction_id: Optional[str]
   - verified_by: Optional[str]  # admin ID
   - verified_at: Optional[datetime]
   - receipt_url: Optional[str]
   - created_at: datetime

4. Receipt dataclass:
   - receipt_id: str
   - payment_id: str
   - user_id: str
   - user_email: str
   - amount: float
   - method: str
   - transaction_id: str
   - date: datetime
   - description: str
   - receipt_number: str

5. Invoice dataclass:
   - invoice_id: str
   - user_id: str
   - period: str  # "April 2026"
   - items: list[InvoiceItem]
   - subtotal: float
   - discount: float
   - total: float
   - due_date: datetime
   - status: str (unpaid/paid/overdue)

6. CouponResult dataclass:
   - valid: bool
   - code: str
   - discount_pct: float
   - discount_amount: float
   - expires_at: Optional[datetime]
   - max_uses: int
   - current_uses: int
   - message: str

TEST CASES:
test_initiate_payment_creates_session, test_verify_payment_marks_verified, test_reject_payment_with_reason, test_get_payment_status_pending, test_get_user_payments_returns_list, test_get_pending_payments, test_generate_receipt_contains_details, test_generate_invoice_for_business, test_process_refund, test_validate_coupon_valid, test_validate_coupon_expired, test_validate_coupon_max_uses_reached, test_apply_coupon_calculates_discount, test_payment_session_expires_after_24h

OUTPUT: Generate payment_processor.py and test_payment_processor.py. Use async/await throughout.
```

---

## SPRINT 9.4 — Trial Management
### Files: backend/billing/trial_manager.py
### Tests: backend/tests/unit/test_trial_manager.py

```
You are building the trial management module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- 30-day free trial for new users
- Full feature access during trial (all tiers unlocked)
- Trial expiry notifications (day 1, 5, 7, 14, 21, 28, 29, 30)
- Grace period: 7 days after trial ends before data deletion
- Warning messages via Telegram and email
- Admin can extend trial for specific users
- Trial conversion tracking

KEY DECISIONS:
- D026: All calls async
- Trial: 30 days full access
- Grace: 7 days after expiry
- Data deletion after grace period

FUNCTIONS TO IMPLEMENT:

1. TrialManager class:
   - start_trial(user_id: str) -> TrialInfo
   - get_trial_info(user_id: str) -> TrialInfo
   - get_days_remaining(user_id: str) -> int
   - is_trial_active(user_id: str) -> bool
   - is_trial_expired(user_id: str) -> bool
   - extend_trial(user_id: str, extra_days: int, admin_id: str) -> TrialInfo
   - end_trial_early(user_id: str) -> TrialInfo
   - convert_to_paid(user_id: str, tier: str) -> TrialInfo
   - get_users_near_expiry(days_threshold: int = 3) -> list[str]
   - get_expired_users() -> list[str]
   - get_trial_conversion_rate(since: datetime) -> float
   - send_expiry_warnings() -> int  # returns count sent
   - handle_grace_period(user_id: str) -> dict
   - schedule_data_deletion(user_id: str) -> dict

2. TrialInfo dataclass:
   - user_id: str
   - started_at: datetime
   - trial_ends_at: datetime
   - grace_ends_at: Optional[datetime]
   - days_remaining: int
   - is_active: bool
   - is_in_grace: bool
   - warnings_sent: list[datetime]
   - converted_to_paid: bool
   - converted_tier: Optional[str]
   - converted_at: Optional[datetime]

3. TrialWarningSchedule:
   - Day 1: "Welcome! Your 30-day free trial has started."
   - Day 5: "5 days in. Enjoying Vision OS?"
   - Day 7: "1 week remaining in your trial."
   - Day 14: "Halfway through your trial."
   - Day 21: "9 days left. Upgrade to keep your data."
   - Day 28: "2 days remaining!"
   - Day 29: "Last day of your trial tomorrow!"
   - Day 30: "Your trial ends today. Upgrade now."
   - Grace Day 1: "Your trial has ended. 7 days to upgrade."
   - Grace Day 5: "3 days until data deletion."
   - Grace Day 7: "Your data will be deleted today."

TEST CASES:
test_start_trial_creates_30_day_period, test_get_trial_info_returns_correct_data, test_days_remaining_decreases_over_time, test_is_trial_active_true_within_period, test_is_trial_expired_after_period, test_extend_trial_adds_days, test_end_trial_early, test_convert_to_paid_marks_converted, test_get_users_near_expiry, test_get_expired_users, test_trial_conversion_rate_calculation, test_send_expiry_warnings_returns_count, test_handle_grace_period, test_schedule_data_deletion, test_warning_schedule_days_match

OUTPUT: Generate trial_manager.py and test_trial_manager.py. Use async/await throughout.
```

---

## SPRINT 9.5 — Usage Tracking
### Files: backend/analytics/usage_tracker.py
### Tests: backend/tests/unit/test_usage_tracker.py

```
You are building the usage tracking module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Tracks per-user resource usage: camera count, events, AI calls, storage, bandwidth
- Usage limits based on tier (but no hard camera limit — supports up to 10)
- Usage alerts when approaching limits
- Daily usage snapshots for billing
- Usage history for trend analysis
- Admin dashboard shows usage across all users

KEY DECISIONS:
- D026: All calls async
- Usage tracked daily for billing accuracy
- Soft limits with warnings (not hard blocks)

FUNCTIONS TO IMPLEMENT:

1. UsageTracker class:
   - record_event(user_id: str, event_data: dict) -> dict
   - record_ai_call(user_id: str, model: str, tokens: int) -> dict
   - record_storage_usage(user_id: str, bytes_stored: int) -> dict
   - get_daily_usage(user_id: str, date: date) -> DailyUsage
   - get_monthly_usage(user_id: str, year: int, month: int) -> MonthlyUsage
   - get_current_usage(user_id: str) -> CurrentUsage
   - check_usage_limits(user_id: str) -> UsageAlerts
   - get_all_users_usage(date: date) -> list[UserUsageSummary]
   - get_top_users(limit: int = 10, metric: str = "events") -> list[UserUsageSummary]
   - compute_daily_snapshot() -> int  # returns users processed

2. DailyUsage dataclass:
   - user_id: str
   - date: date
   - events_generated: int
   - ai_calls: int
   - ai_tokens: int
   - storage_bytes: int
   - bandwidth_bytes: int
   - active_cameras: int
   - alerts_sent: int
   - high_threat_events: int

3. MonthlyUsage dataclass:
   - user_id: str
   - year: int
   - month: int
   - total_events: int
   - total_ai_calls: int
   - total_ai_tokens: int
   - avg_daily_storage_bytes: float
   - total_bandwidth_bytes: int
   - avg_active_cameras: float
   - peak_cameras: int
   - estimated_cost: float

4. CurrentUsage dataclass:
   - user_id: str
   - tier: str
   - camera_count: int
   - events_today: int
   - events_this_month: int
   - ai_calls_today: int
   - ai_calls_this_month: int
   - storage_used_mb: float
   - bandwidth_used_mb: float
   - estimated_monthly_cost: float

5. UsageAlerts dataclass:
   - alerts: list[UsageAlert]
   - has_warnings: bool
   - has_critical: bool

6. UsageAlert dataclass:
   - type: str (storage/bandwidth/events/ai_calls)
   - severity: str (info/warning/critical)
   - message: str
   - current_value: float
   - limit_value: float
   - usage_pct: float

7. UserUsageSummary dataclass:
   - user_id: str
   - email: str
   - tier: str
   - camera_count: int
   - events_24h: int
   - ai_calls_24h: int
   - storage_mb: float
   - estimated_daily_cost: float

TEST CASES:
test_record_event_increments_count, test_record_ai_call_tracks_tokens, test_record_storage_usage, test_get_daily_usage_returns_data, test_get_monthly_usage_aggregates, test_get_current_usage_returns_live_data, test_check_usage_limits_within_bounds, test_check_usage_limits_near_limit_warning, test_check_usage_limits_over_limit_critical, test_get_all_users_usage, test_get_top_users_by_events, test_compute_daily_snapshot_processes_all, test_usage_data_retention, test_concurrent_usage_recording

OUTPUT: Generate usage_tracker.py and test_usage_tracker.py. Use async/await throughout.
```

---

## Quick Reference: V7 File Paths

| Sprint | File Path |
|--------|-----------|
| 9.1 | `backend/core/onboarding.py` |
| 9.1 | `backend/dashboard/templates/onboarding.html` |
| 9.1 | `backend/dashboard/static/onboarding.js` |
| 9.1 | `backend/dashboard/static/onboarding.css` |
| 9.1 | `backend/tests/unit/test_onboarding.py` |
| 9.2 | `backend/billing/subscription_manager.py` |
| 9.2 | `backend/tests/unit/test_subscription_manager.py` |
| 9.3 | `backend/billing/payment_processor.py` |
| 9.3 | `backend/tests/unit/test_payment_processor.py` |
| 9.4 | `backend/billing/trial_manager.py` |
| 9.4 | `backend/tests/unit/test_trial_manager.py` |
| 9.5 | `backend/analytics/usage_tracker.py` |
| 9.5 | `backend/tests/unit/test_usage_tracker.py` |

---

*Vision OS V7 — User Onboarding & Subscription Management*

*Copy, paste, generate, test, commit. Repeat.*
