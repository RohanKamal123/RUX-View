"""
auth.py — Authentication Middleware for Vision OS.

Stack: Firebase Admin SDK (production) / Dev-mode bypass (development)
- Firebase ID tokens verified server-side in production
- In development, a hardcoded dev user is used (no Firebase needed)
- Tiers: free, household, business
- All routes protected with get_current_user() dependency
- Premium routes use require_tier() decorator
- Session cookie support for browser-based login (dev mode)

Production Behavior:
  - FIREBASE_CREDENTIALS_JSON (inline) or FIREBASE_CREDENTIALS_PATH (file)
  - If Firebase is unavailable in production, returns 401
  - No silent fallback to dev user in production
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import RedirectResponse

from backend.config import settings

# ── Firebase Initialisation (optional) ────────────────────────

_firebase_app = None
_firebase_available = False


def init_firebase() -> None:
    """Initialise Firebase Admin SDK from service account JSON.

    Looks for FIREBASE_CREDENTIALS_JSON (inline JSON, production)
    or FIREBASE_CREDENTIALS_PATH env var (file path, development).
    Safe to call multiple times — only initialises once.

    In production, if no credentials are found, Firebase is NOT
    available and auth will reject all requests.
    """
    global _firebase_app, _firebase_available

    if _firebase_app is not None:
        return  # Already initialised

    import firebase_admin
    from firebase_admin import credentials

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH") or settings.firebase_credentials_path
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON") or settings.firebase_credentials_json

    try:
        if cred_json:
            # Production: inline JSON string
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
        elif cred_path:
            # Development: file path
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            try:
                _firebase_app = firebase_admin.initialize_app()
            except ValueError:
                _firebase_app = firebase_admin.get_app()
        _firebase_available = True
    except Exception as exc:
        _firebase_app = None
        _firebase_available = False
        if settings.environment == "production":
            raise RuntimeError(
                f"Firebase initialization failed in production: {exc}. "
                "Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH."
            ) from exc


# ── Session Cookie Helpers ────────────────────────────────────

SESSION_COOKIE_NAME = "visionos_session"
SESSION_MAX_AGE_SECONDS = 86400  # 24 hours


def _sign_data(data: str) -> str:
    """HMAC-SHA256 sign a string with the secret key."""
    key = settings.secret_key.encode("utf-8") if settings.secret_key else b"dev-secret-key"
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()


def encode_session_cookie(user: dict) -> str:
    """Encode a user dict into a signed session cookie value.

    The cookie contains JSON with the user fields plus an expiry
    timestamp and an HMAC signature to prevent tampering.

    Args:
        user: Dict with uid, email, tier, subscription_active.

    Returns:
        Signed cookie string.
    """
    payload = {
        "uid": user.get("uid", ""),
        "email": user.get("email", ""),
        "tier": user.get("tier", "free"),
        "subscription_active": user.get("subscription_active", False),
        "exp": (datetime.utcnow() + timedelta(seconds=SESSION_MAX_AGE_SECONDS)).isoformat(),
    }
    payload_json = json.dumps(payload, separators=(",", ":"))
    signature = _sign_data(payload_json)
    return f"{payload_json}.{signature}"


def decode_session_cookie(cookie_value: str) -> Optional[dict]:
    """Decode and verify a signed session cookie.

    Args:
        cookie_value: The raw cookie string.

    Returns:
        User dict if valid, None otherwise.
    """
    try:
        # Split payload and signature
        last_dot = cookie_value.rfind(".")
        if last_dot == -1:
            return None
        payload_json = cookie_value[:last_dot]
        signature = cookie_value[last_dot + 1:]

        # Verify signature
        expected_sig = _sign_data(payload_json)
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Parse payload
        payload = json.loads(payload_json)

        # Check expiry
        exp = datetime.fromisoformat(payload.get("exp", ""))
        if exp < datetime.utcnow():
            return None

        return {
            "uid": payload.get("uid", ""),
            "email": payload.get("email", ""),
            "tier": payload.get("tier", "free"),
            "subscription_active": payload.get("subscription_active", False),
        }
    except (ValueError, json.JSONDecodeError, KeyError):
        return None


def set_session_cookie(response: RedirectResponse, user: dict) -> None:
    """Set the session cookie on a redirect response.

    Args:
        response: The RedirectResponse to set the cookie on.
        user: User dict to encode into the cookie.
    """
    cookie_value = encode_session_cookie(user)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        # secure=True in production (requires HTTPS)
        secure=(settings.environment == "production"),
    )


def clear_session_cookie(response: RedirectResponse) -> None:
    """Clear the session cookie (for logout).

    Args:
        response: The RedirectResponse to clear the cookie on.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )


# ── Token Verification ────────────────────────────────────────


async def verify_token(token: str) -> dict:
    """Verify a Firebase ID token (production) or return dev user (development).

    In development mode, any non-empty token is accepted and returns
    a privileged dev user. This lets you test all features without
    needing a real Firebase project.

    In production mode, Firebase MUST be available. If it's not,
    all requests are rejected with 401.

    Args:
        token: Firebase ID token string.

    Returns:
        Dict with {uid, email, tier, subscription_active}.

    Raises:
        HTTPException 401 if token is invalid/expired.
    """
    # ── Dev mode: skip Firebase verification ──────────────────
    if settings.environment == "development":
        return {
            "uid": "dev-user-001",
            "email": "dev@visionos.local",
            "tier": "business",  # Full access for testing
            "subscription_active": True,
        }

    # ── Production: Firebase MUST be available ─────────────────
    if not _firebase_available:
        raise HTTPException(
            status_code=401,
            detail="Authentication service unavailable. Contact support.",
        )

    # ── Production: verify with Firebase Admin SDK ─────────────
    from firebase_admin import auth as firebase_auth

    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {exc}",
        )

    uid = decoded.get("uid", "")
    email = decoded.get("email", "")

    # Extract custom claims for tier info
    claims = decoded.get("claims", {})
    tier = claims.get("tier", "free")
    subscription_active = claims.get("subscription_active", False)

    return {
        "uid": uid,
        "email": email,
        "tier": tier,
        "subscription_active": subscription_active,
    }


# ── FastAPI Dependency ────────────────────────────────────────


async def get_current_user(
    authorization: str = Header(None),
    request: Request = None,  # type: ignore
) -> dict:
    """FastAPI dependency to extract and verify the current user.

    Checks in order:
    1. Authorization: Bearer <token> header (for API calls)
    2. Session cookie (for browser page navigation)

    Returns:
        User dict from verify_token() or session cookie.

    Raises:
        HTTPException 401 if missing or invalid.
    """
    # ── Try Authorization header first ────────────────────────
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return await verify_token(token)

    # ── Fall back to session cookie ───────────────────────────
    if request is not None:
        cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
        if cookie_value:
            user = decode_session_cookie(cookie_value)
            if user is not None:
                return user

    raise HTTPException(
        status_code=401,
        detail="Missing Authorization header or valid session cookie",
    )


# ── Tier Check Decorator ──────────────────────────────────────

# Tier hierarchy (higher index = higher tier)
TIER_HIERARCHY = {"free": 0, "guard": 1, "guard_pro": 2}


def require_tier(required_tier: str):
    """Decorator for routes requiring a specific subscription tier.

    Tier hierarchy: free < household < business

    Usage:
        @router.get("/premium")
        @require_tier("household")
        async def premium_route(user: dict = Depends(get_current_user)):
            ...

    Raises:
        HTTPException 403 if user's tier is insufficient.
    """
    if required_tier not in TIER_HIERARCHY:
        raise ValueError(f"Unknown tier: {required_tier}")

    required_level = TIER_HIERARCHY[required_tier]

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by Depends)
            user = kwargs.get("user")
            if user is None:
                # Try to find it in positional args
                for arg in args:
                    if isinstance(arg, dict) and "uid" in arg:
                        user = arg
                        break

            if user is None:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )

            user_tier = user.get("tier", "free")
            user_level = TIER_HIERARCHY.get(user_tier, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Premium feature. Required tier: {required_tier}, "
                        f"your tier: {user_tier}. "
                        f"Upgrade at https://visionos.app/upgrade"
                    ),
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
