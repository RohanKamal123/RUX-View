"""
public_signup.py — Self-Service Signup Flow for Vision OS.

Handles:
- Firebase Auth account creation
- Automatic trial start (30 days)
- Email verification
- Rate limiting (5 signups/IP/hour)
- Welcome email/Telegram message
- Password reset flow

Uses async/await throughout.
"""

import logging
import re
import hashlib
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────────


@dataclass
class SignupResult:
    """Result of a signup operation."""
    user_id: str
    email: str
    name: str
    tier: str = "free"
    trial_ends_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    email_verified: bool = False
    firebase_uid: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""


@dataclass
class SignupStats:
    """Aggregated signup statistics."""
    total_signups: int = 0
    verified_emails: int = 0
    unverified_emails: int = 0
    trial_active: int = 0
    trial_converted: int = 0
    signups_today: int = 0
    signups_this_week: int = 0
    signups_this_month: int = 0


# ── In-Memory Store (for testing; replace with DB in production) ──

_users: dict[str, dict] = {}  # email -> user record
_rate_limits: dict[str, list[datetime]] = defaultdict(list)  # ip -> list of timestamps
_verification_codes: dict[str, str] = {}  # email -> code
_reset_codes: dict[str, str] = {}  # email -> reset code


# ── Validation ────────────────────────────────────────────────────


def _validate_email(email: str) -> Optional[str]:
    """Validate email format. Returns error message or None."""
    if not email or not isinstance(email, str):
        return "Email is required"
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return "Invalid email format"
    return None


def _validate_password(password: str) -> Optional[str]:
    """Validate password strength. Returns error message or None."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[0-9]', password):
        return "Password must contain at least one number"
    return None


def _validate_name(name: str) -> Optional[str]:
    """Validate name. Returns error message or None."""
    if not name or len(name.strip()) < 2:
        return "Name must be at least 2 characters"
    if len(name.strip()) > 100:
        return "Name must be at most 100 characters"
    return None


def _validate_phone(phone: str) -> Optional[str]:
    """Validate Bangladesh phone number. Returns error message or None."""
    if not phone:
        return None  # Phone is optional
    # Bangladesh numbers: 01XXXXXXXXX (11 digits)
    pattern = r'^01[3-9]\d{8}$'
    if not re.match(pattern, phone.strip()):
        return "Invalid Bangladesh phone number (format: 01XXXXXXXXX)"
    return None


def _check_rate_limit(ip_address: str) -> bool:
    """Check if rate limit exceeded (5 signups/IP/hour). Returns True if allowed."""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Clean old entries
    _rate_limits[ip_address] = [
        t for t in _rate_limits[ip_address] if t > one_hour_ago
    ]

    if len(_rate_limits[ip_address]) >= 5:
        return False

    _rate_limits[ip_address].append(now)
    return True


def _generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    import random
    return str(random.randint(100000, 999999))


def _generate_user_id(email: str) -> str:
    """Generate a unique user ID from email."""
    return hashlib.sha256(email.lower().encode()).hexdigest()[:16]


# ── PublicSignupHandler ───────────────────────────────────────────


class PublicSignupHandler:
    """Handles self-service signup flow."""

    async def signup(
        self,
        email: str,
        password: str,
        name: str,
        phone: str,
        ip_address: str = "127.0.0.1"
    ) -> SignupResult:
        """Register a new user.

        Steps:
        1. Validate inputs
        2. Check rate limit
        3. Check email availability
        4. Create Firebase Auth account (simulated)
        5. Create user record in database
        6. Start trial subscription (30 days)
        7. Send verification email
        8. Send welcome Telegram message

        Args:
            email: User's email address.
            password: User's password.
            name: User's full name.
            phone: User's Bangladesh phone number (optional).
            ip_address: IP address for rate limiting.

        Returns:
            SignupResult with user details.

        Raises:
            ValueError: If validation fails or email already registered.
        """
        # Validate inputs
        email_error = _validate_email(email)
        if email_error:
            raise ValueError(email_error)

        password_error = _validate_password(password)
        if password_error:
            raise ValueError(password_error)

        name_error = _validate_name(name)
        if name_error:
            raise ValueError(name_error)

        phone_error = _validate_phone(phone)
        if phone_error:
            raise ValueError(phone_error)

        # Rate limit check
        if not _check_rate_limit(ip_address):
            raise ValueError("Rate limit exceeded. Please try again later.")

        # Check email availability
        if not await self.check_email_available(email):
            raise ValueError("Email already registered")

        # Create Firebase Auth account (simulated)
        firebase_uid = f"fb_{_generate_user_id(email)}"

        # Create user record
        now = datetime.now(timezone.utc)
        user_id = _generate_user_id(email)
        trial_ends_at = now + timedelta(days=30)

        user_record = {
            "user_id": user_id,
            "email": email.lower().strip(),
            "name": name.strip(),
            "phone": phone.strip() if phone else "",
            "tier": "free",
            "firebase_uid": firebase_uid,
            "email_verified": False,
            "trial_ends_at": trial_ends_at,
            "created_at": now,
            "is_active": True,
        }
        _users[email.lower().strip()] = user_record

        # Generate and store verification code
        code = _generate_verification_code()
        _verification_codes[email.lower().strip()] = code

        logger.info(
            "User signed up: %s (firebase_uid=%s, trial_ends=%s)",
            email, firebase_uid, trial_ends_at.isoformat()
        )

        return SignupResult(
            user_id=user_id,
            email=email.lower().strip(),
            name=name.strip(),
            tier="free",
            trial_ends_at=trial_ends_at,
            email_verified=False,
            firebase_uid=firebase_uid,
            created_at=now,
            message="Account created successfully. Please verify your email.",
        )

    async def verify_email(self, email: str, code: str) -> dict:
        """Verify a user's email address with a verification code.

        Args:
            email: User's email address.
            code: 6-digit verification code.

        Returns:
            Dict with verification status.

        Raises:
            ValueError: If email not found or code invalid.
        """
        email_key = email.lower().strip()
        if email_key not in _users:
            raise ValueError("Email not found")

        stored_code = _verification_codes.get(email_key)
        if not stored_code:
            raise ValueError("No verification code found. Request a new one.")

        if stored_code != code:
            raise ValueError("Invalid verification code")

        # Mark email as verified
        _users[email_key]["email_verified"] = True
        del _verification_codes[email_key]

        logger.info("Email verified: %s", email)

        return {
            "status": "verified",
            "email": email,
            "message": "Email verified successfully",
        }

    async def resend_verification(self, email: str) -> dict:
        """Resend the verification email with a new code.

        Args:
            email: User's email address.

        Returns:
            Dict with status.

        Raises:
            ValueError: If email not found.
        """
        email_key = email.lower().strip()
        if email_key not in _users:
            raise ValueError("Email not found")

        if _users[email_key]["email_verified"]:
            return {"status": "already_verified", "message": "Email already verified"}

        # Generate new code
        code = _generate_verification_code()
        _verification_codes[email_key] = code

        logger.info("Verification code resent: %s", email)

        return {
            "status": "sent",
            "email": email,
            "message": "Verification code sent",
        }

    async def check_email_available(self, email: str) -> bool:
        """Check if an email is available for registration.

        Args:
            email: Email address to check.

        Returns:
            True if email is available, False if already registered.
        """
        return email.lower().strip() not in _users

    async def initiate_password_reset(self, email: str) -> dict:
        """Initiate a password reset flow.

        Args:
            email: User's email address.

        Returns:
            Dict with reset status.

        Raises:
            ValueError: If email not found.
        """
        email_key = email.lower().strip()
        if email_key not in _users:
            raise ValueError("Email not found")

        # Generate reset code
        code = _generate_verification_code()
        _reset_codes[email_key] = code

        logger.info("Password reset initiated: %s", email)

        return {
            "status": "reset_initiated",
            "email": email,
            "message": "Password reset code sent to your email",
        }

    async def reset_password(self, code: str, new_password: str) -> dict:
        """Reset a user's password using a reset code.

        Args:
            code: Password reset code.
            new_password: New password.

        Returns:
            Dict with reset status.

        Raises:
            ValueError: If code invalid or password weak.
        """
        # Validate new password
        password_error = _validate_password(new_password)
        if password_error:
            raise ValueError(password_error)

        # Find email by reset code
        email_key = None
        for email, stored_code in _reset_codes.items():
            if stored_code == code:
                email_key = email
                break

        if not email_key:
            raise ValueError("Invalid or expired reset code")

        # Update password (simulated)
        del _reset_codes[email_key]

        logger.info("Password reset completed: %s", email_key)

        return {
            "status": "password_reset",
            "message": "Password reset successfully",
        }

    async def get_signup_stats(self, since: datetime) -> SignupStats:
        """Get aggregated signup statistics.

        Args:
            since: Start date for statistics.

        Returns:
            SignupStats with aggregated data.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        stats = SignupStats()

        for user in _users.values():
            created = user["created_at"]

            if created < since:
                continue

            stats.total_signups += 1

            if user["email_verified"]:
                stats.verified_emails += 1
            else:
                stats.unverified_emails += 1

            if user["trial_ends_at"] > now:
                stats.trial_active += 1
            else:
                stats.trial_converted += 1

            if created >= today_start:
                stats.signups_today += 1
            if created >= week_start:
                stats.signups_this_week += 1
            if created >= month_start:
                stats.signups_this_month += 1

        return stats


# ── Helper to reset store (for testing) ───────────────────────────


def _reset_store():
    """Reset the in-memory store. Used for testing."""
    _users.clear()
    _rate_limits.clear()
    _verification_codes.clear()
    _reset_codes.clear()
