"""
trial_manager.py — Trial Management for Vision OS.

30-day free trial for new users with full feature access.
Trial expiry notifications with warning schedule.
Grace period: 7 days after trial ends before data deletion.
Admin can extend trial for specific users.
Trial conversion tracking.

Key decisions:
- D026: All calls async
- Trial: 30 days full access
- Grace: 7 days after expiry
- Data deletion after grace period
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────

TRIAL_DAYS = 30
GRACE_DAYS = 7
NEAR_EXPIRY_THRESHOLD = 3


# ── Warning Schedule ────────────────────────────────────────────

TRIAL_WARNINGS = {
    1: "Welcome! Your 30-day free trial has started.",
    5: "5 days in. Enjoying Vision OS?",
    7: "1 week remaining in your trial.",
    14: "Halfway through your trial.",
    21: "9 days left. Upgrade to keep your data.",
    28: "2 days remaining!",
    29: "Last day of your trial tomorrow!",
    30: "Your trial ends today. Upgrade now.",
}

GRACE_WARNINGS = {
    1: "Your trial has ended. 7 days to upgrade.",
    5: "3 days until data deletion.",
    7: "Your data will be deleted today.",
}


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class TrialInfo:
    """Information about a user's trial."""

    user_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trial_ends_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)
    )
    grace_ends_at: Optional[datetime] = None
    days_remaining: int = TRIAL_DAYS
    is_active: bool = True
    is_in_grace: bool = False
    warnings_sent: list[datetime] = field(default_factory=list)
    converted_to_paid: bool = False
    converted_tier: Optional[str] = None
    converted_at: Optional[datetime] = None


# ── In-Memory Store (replace with DB in production) ────────────

_trials: dict[str, TrialInfo] = {}


# ── TrialManager ────────────────────────────────────────────────


class TrialManager:
    """Manages trial periods, expiry warnings, and conversion tracking."""

    async def start_trial(self, user_id: str) -> TrialInfo:
        """Start a 30-day free trial for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            TrialInfo with trial period details.
        """
        now = datetime.now(timezone.utc)
        trial = TrialInfo(
            user_id=user_id,
            started_at=now,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
            days_remaining=TRIAL_DAYS,
            is_active=True,
            is_in_grace=False,
        )

        _trials[user_id] = trial
        logger.info("Trial started for user: %s, ends at: %s", user_id, trial.trial_ends_at)
        return trial

    async def get_trial_info(self, user_id: str) -> TrialInfo:
        """Get trial information for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            TrialInfo with current trial state.

        Raises:
            ValueError: If no trial found.
        """
        if user_id not in _trials:
            raise ValueError(f"No trial found for user: {user_id}")

        trial = _trials[user_id]
        self._refresh_trial_state(trial)
        return trial

    async def get_days_remaining(self, user_id: str) -> int:
        """Get the number of days remaining in the trial.

        Args:
            user_id: Unique user identifier.

        Returns:
            Number of days remaining (0 if expired).
        """
        try:
            trial = await self.get_trial_info(user_id)
            return trial.days_remaining
        except ValueError:
            return 0

    async def is_trial_active(self, user_id: str) -> bool:
        """Check if a user's trial is currently active.

        Args:
            user_id: Unique user identifier.

        Returns:
            True if trial is active.
        """
        try:
            trial = await self.get_trial_info(user_id)
            return trial.is_active
        except ValueError:
            return False

    async def is_trial_expired(self, user_id: str) -> bool:
        """Check if a user's trial has expired.

        Args:
            user_id: Unique user identifier.

        Returns:
            True if trial has expired.
        """
        try:
            trial = await self.get_trial_info(user_id)
            return not trial.is_active and not trial.is_in_grace
        except ValueError:
            return True

    async def extend_trial(
        self, user_id: str, extra_days: int, admin_id: str
    ) -> TrialInfo:
        """Extend a user's trial period (admin action).

        Args:
            user_id: Unique user identifier.
            extra_days: Number of extra days to add.
            admin_id: Admin user ID who authorized the extension.

        Returns:
            Updated TrialInfo.
        """
        trial = await self.get_trial_info(user_id)
        trial.trial_ends_at += timedelta(days=extra_days)
        trial.is_active = True
        trial.is_in_grace = False
        trial.grace_ends_at = None
        self._refresh_trial_state(trial)

        logger.info(
            "Trial extended by %d days for user: %s by admin: %s",
            extra_days, user_id, admin_id,
        )
        return trial

    async def end_trial_early(self, user_id: str) -> TrialInfo:
        """End a user's trial early.

        Args:
            user_id: Unique user identifier.

        Returns:
            Updated TrialInfo with trial ended.
        """
        trial = await self.get_trial_info(user_id)
        trial.trial_ends_at = datetime.now(timezone.utc)
        trial.is_active = False
        self._refresh_trial_state(trial)

        logger.info("Trial ended early for user: %s", user_id)
        return trial

    async def convert_to_paid(self, user_id: str, tier: str) -> TrialInfo:
        """Mark a trial user as converted to paid.

        Args:
            user_id: Unique user identifier.
            tier: The tier they converted to (household/business).

        Returns:
            Updated TrialInfo.
        """
        trial = await self.get_trial_info(user_id)
        trial.converted_to_paid = True
        trial.converted_tier = tier
        trial.converted_at = datetime.now(timezone.utc)
        trial.is_active = False

        logger.info(
            "User: %s converted to paid tier: %s", user_id, tier
        )
        return trial

    async def get_users_near_expiry(
        self, days_threshold: int = NEAR_EXPIRY_THRESHOLD
    ) -> list[str]:
        """Get users whose trial is near expiry.

        Args:
            days_threshold: Days threshold for "near expiry".

        Returns:
            List of user IDs near expiry.
        """
        near_expiry = []
        for user_id, trial in _trials.items():
            self._refresh_trial_state(trial)
            if trial.is_active and 0 < trial.days_remaining <= days_threshold:
                near_expiry.append(user_id)
        return near_expiry

    async def get_expired_users(self) -> list[str]:
        """Get users whose trial has expired.

        Returns:
            List of user IDs with expired trials.
        """
        expired = []
        for user_id, trial in _trials.items():
            self._refresh_trial_state(trial)
            if not trial.is_active and not trial.is_in_grace:
                expired.append(user_id)
        return expired

    async def get_trial_conversion_rate(
        self, since: datetime
    ) -> float:
        """Calculate trial-to-paid conversion rate.

        Args:
            since: Start date for the calculation period.

        Returns:
            Conversion rate as a float (0.0 to 1.0).
        """
        total_trials = 0
        converted = 0

        for trial in _trials.values():
            if trial.started_at >= since:
                total_trials += 1
                if trial.converted_to_paid:
                    converted += 1

        if total_trials == 0:
            return 0.0

        return converted / total_trials

    async def send_expiry_warnings(self) -> int:
        """Send expiry warnings to users based on the warning schedule.

        Returns:
            Number of warnings sent.
        """
        count = 0
        now = datetime.now(timezone.utc)

        for user_id, trial in _trials.items():
            self._refresh_trial_state(trial)

            if trial.is_active:
                # Check trial warnings
                days_used = TRIAL_DAYS - trial.days_remaining
                message = TRIAL_WARNINGS.get(days_used)
                if message:
                    # In production, send via Telegram/email
                    trial.warnings_sent.append(now)
                    count += 1
                    logger.info(
                        "Trial warning sent to user: %s (day %d): %s",
                        user_id, days_used, message,
                    )

            elif trial.is_in_grace:
                # Check grace warnings
                grace_days_used = (
                    now - trial.trial_ends_at
                ).days if trial.trial_ends_at else 0
                message = GRACE_WARNINGS.get(grace_days_used)
                if message:
                    trial.warnings_sent.append(now)
                    count += 1
                    logger.info(
                        "Grace warning sent to user: %s (grace day %d): %s",
                        user_id, grace_days_used, message,
                    )

        return count

    async def handle_grace_period(self, user_id: str) -> dict:
        """Move a user into the grace period after trial expiry.

        Args:
            user_id: Unique user identifier.

        Returns:
            Dict with grace period details.
        """
        trial = await self.get_trial_info(user_id)
        now = datetime.now(timezone.utc)

        trial.is_active = False
        trial.is_in_grace = True
        trial.grace_ends_at = now + timedelta(days=GRACE_DAYS)

        result = {
            "user_id": user_id,
            "grace_ends_at": trial.grace_ends_at.isoformat(),
            "days_of_grace": GRACE_DAYS,
            "message": f"Your trial has ended. You have {GRACE_DAYS} days to upgrade before data deletion.",
        }

        logger.info(
            "Grace period started for user: %s, ends at: %s",
            user_id, trial.grace_ends_at,
        )
        return result

    async def schedule_data_deletion(self, user_id: str) -> dict:
        """Schedule data deletion for a user after grace period.

        Args:
            user_id: Unique user identifier.

        Returns:
            Dict with deletion schedule details.
        """
        trial = await self.get_trial_info(user_id)
        now = datetime.now(timezone.utc)

        deletion_date = now + timedelta(days=7)

        result = {
            "user_id": user_id,
            "deletion_scheduled_at": now.isoformat(),
            "deletion_date": deletion_date.isoformat(),
            "message": "User data will be deleted after 7 days.",
        }

        logger.info(
            "Data deletion scheduled for user: %s on: %s",
            user_id, deletion_date,
        )
        return result

    def _refresh_trial_state(self, trial: TrialInfo) -> None:
        """Refresh the trial state based on current time.

        Args:
            trial: TrialInfo to refresh.
        """
        now = datetime.now(timezone.utc)

        if trial.converted_to_paid:
            trial.is_active = False
            trial.is_in_grace = False
            trial.days_remaining = 0
            return

        if trial.trial_ends_at:
            remaining = (trial.trial_ends_at - now).days
            trial.days_remaining = max(0, remaining)

            if now < trial.trial_ends_at:
                trial.is_active = True
                trial.is_in_grace = False
            elif trial.grace_ends_at and now < trial.grace_ends_at:
                trial.is_active = False
                trial.is_in_grace = True
            else:
                trial.is_active = False
                trial.is_in_grace = False
