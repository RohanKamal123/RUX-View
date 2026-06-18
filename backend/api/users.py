"""
users.py — User API for Vision OS (Hybrid Backend).

User profile management, account deletion (GDPR), statistics, and
Telegram integration. All routes are protected with Firebase Auth.
Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

router = APIRouter(prefix="/users", tags=["users"])

# Global HybridCRUD instance (initialized in server.py)
hybrid_crud: HybridCRUD = None  # type: ignore


def get_crud() -> HybridCRUD:
    """Dependency to get the HybridCRUD instance.

    Returns:
        HybridCRUD instance.

    Raises:
        HTTPException 503: If no storage backend is available.
    """
    if hybrid_crud is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Storage not initialized", "code": "STORAGE_UNAVAILABLE"},
        )
    return hybrid_crud


@router.get("/me",
    summary="Get the authenticated user's profile",
    description="Returns the user's profile including email, display name, subscription tier, account creation date, "
                "and Telegram chat ID. Use this to populate the user settings and profile pages.",
    tags=["Users"],
    responses={
        200: {"description": "User profile returned successfully"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_user_profile(
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get the authenticated user's profile.

    Args:
        user: Authenticated user dict from Firebase.
        crud: HybridCRUD instance.

    Returns:
        User profile dict.
    """
    user_id = user.get("uid", "anonymous")
    email = user.get("email", "")
    name = user.get("name", "")
    profile = await crud.get_or_create_user(
        user_id=user_id, email=email, name=name
    )
    return {
        "user_id": profile.user_id,
        "email": profile.email,
        "name": profile.name,
        "tier": profile.tier,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "is_active": profile.is_active,
        "telegram_chat_id": profile.telegram_chat_id,
    }


@router.put("/me",
    summary="Update the authenticated user's profile",
    description="Updates profile fields for the authenticated user. Currently supports updating display name "
                "and Telegram chat ID. Returns the updated profile name.",
    tags=["Users"],
    responses={
        200: {"description": "Profile updated successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        422: {"description": "Validation error — invalid update data"},
        500: {"description": "Storage error"},
    },
)
async def update_user_profile(
    updates: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Update the authenticated user's profile.

    Args:
        updates: Dict of fields to update (name, telegram_chat_id).
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status.
    """
    user_id = user.get("uid", "anonymous")
    try:
        profile = await crud.update_user(user_id, updates)
        return {
            "status": "updated",
            "user_id": user_id,
            "name": profile.name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.get("/me/stats",
    summary="Get usage statistics for the authenticated user",
    description="Returns aggregated statistics including camera count (with quota usage), total event count, "
                "tier information, and usage percentage. Use this to populate the dashboard summary cards.",
    tags=["Users"],
    responses={
        200: {"description": "User statistics returned successfully"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_user_stats(
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get statistics for the authenticated user.

    Returns counts of cameras, events, and quota information.

    Args:
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with user statistics.
    """
    user_id = user.get("uid", "anonymous")
    cameras = await crud.get_user_cameras(user_id)
    event_count = await crud.count_user_events(user_id)
    quota = await crud.get_camera_quota(user_id)

    return {
        "user_id": user_id,
        "cameras": {
            "total": len(cameras),
            "max": quota.max_cameras,
            "remaining": quota.remaining,
        },
        "events": {
            "total": event_count,
        },
        "quota": {
            "usage_percentage": quota.usage_percentage,
            "tier": quota.tier,
        },
    }


@router.post("/me/telegram",
    summary="Connect a Telegram chat ID for alerts",
    description="Associates a Telegram chat ID with the user's account so that alert notifications "
                "can be delivered via Telegram bot. Requires a valid Telegram chat ID (numeric). "
                "Returns connection status.",
    tags=["Users"],
    responses={
        200: {"description": "Telegram chat ID connected successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        422: {"description": "Validation error — telegram_chat_id is required"},
        500: {"description": "Storage error"},
    },
)
async def connect_telegram(
    telegram_data: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Connect a Telegram chat ID to the user's account.

    Args:
        telegram_data: Dict with telegram_chat_id.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status.

    Raises:
        HTTPException 422: If telegram_chat_id is missing.
    """
    user_id = user.get("uid", "anonymous")
    chat_id = telegram_data.get("telegram_chat_id")
    if not chat_id:
        raise HTTPException(status_code=422, detail={
            "error": "telegram_chat_id is required", "code": "VALIDATION_ERROR",
        })

    try:
        await crud.update_user(user_id, {"telegram_chat_id": str(chat_id)})
        return {
            "status": "connected",
            "telegram_chat_id": str(chat_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })