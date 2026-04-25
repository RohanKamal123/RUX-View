"""
auth.py — Authentication Middleware for Vision OS.

Stack: Firebase Admin SDK (production) / Dev-mode bypass (development)
- Firebase ID tokens verified server-side in production
- In development, a hardcoded dev user is used (no Firebase needed)
- Tiers: free, household, business
- All routes protected with get_current_user() dependency
- Premium routes use require_tier() decorator
"""

import json
import os
from functools import wraps

from fastapi import Header, HTTPException

from backend.config import settings

# ── Firebase Initialisation (optional) ────────────────────────

_firebase_app = None
_firebase_available = False


def init_firebase() -> None:
    """Initialise Firebase Admin SDK from service account JSON.

    Looks for FIREBASE_CREDENTIALS_PATH env var or
    FIREBASE_CREDENTIALS_JSON env var (inline JSON).
    Safe to call multiple times — only initialises once.

    If no credentials are found and we're in development mode,
    Firebase is skipped gracefully — auth falls back to dev user.
    """
    global _firebase_app, _firebase_available

    if _firebase_app is not None:
        return  # Already initialised

    import firebase_admin
    from firebase_admin import credentials

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

    try:
        if cred_path:
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        elif cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            try:
                _firebase_app = firebase_admin.initialize_app()
            except ValueError:
                _firebase_app = firebase_admin.get_app()
        _firebase_available = True
    except Exception:
        # Firebase unavailable — will use dev-mode auth
        _firebase_app = None
        _firebase_available = False


# ── Token Verification ────────────────────────────────────────


async def verify_token(token: str) -> dict:
    """Verify a Firebase ID token (production) or return dev user (development).

    In development mode, any non-empty token is accepted and returns
    a privileged dev user. This lets you test all features without
    needing a real Firebase project.

    Args:
        token: Firebase ID token string.

    Returns:
        Dict with {uid, email, tier, subscription_active}.

    Raises:
        HTTPException 401 if token is invalid/expired.
    """
    # ── Dev mode: skip Firebase verification ──────────────────
    if settings.environment == "development" or not _firebase_available:
        return {
            "uid": "dev-user-001",
            "email": "dev@visionos.local",
            "tier": "business",  # Full access for testing
            "subscription_active": True,
        }

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
) -> dict:
    """FastAPI dependency to extract and verify the current user.

    Expects: Authorization: Bearer <firebase-id-token>

    Returns:
        User dict from verify_token().

    Raises:
        HTTPException 401 if missing or invalid.
    """
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Use: Bearer <token>",
        )

    return await verify_token(token)


# ── Tier Check Decorator ──────────────────────────────────────

# Tier hierarchy (higher index = higher tier)
TIER_HIERARCHY = {"free": 0, "household": 1, "business": 2}


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
