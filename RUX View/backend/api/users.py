"""
users.py — User API stubs for Vision OS.

User profile management endpoints.
All routes are protected with Firebase Auth.
Real logic will be added in Phase 3.
"""

from fastapi import APIRouter, Depends

from backend.dashboard.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    """Get the authenticated user's profile and subscription info.

    Args:
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with uid, email, tier, subscription_active, cameras_count.

    TODO: query DB for full profile
    """
    return {
        "uid": user.get("uid", ""),
        "email": user.get("email", ""),
        "tier": user.get("tier", "free"),
        "subscription_active": user.get("subscription_active", False),
        "cameras_count": 1,
        "locations_count": 1,
    }


@router.put("/me")
async def update_profile(
    updates: dict,
    user: dict = Depends(get_current_user),
):
    """Update the authenticated user's profile.

    Args:
        updates: Dict of fields to update.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status.

    TODO: validate + update DB
    """
    return {
        "status": "updated",
        "uid": user.get("uid", ""),
    }
