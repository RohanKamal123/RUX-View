"""
cameras.py — Camera API stubs for Vision OS.

CRUD operations for camera devices.
All routes are protected with Firebase Auth.
Real logic will be added in Phase 3.
"""

from fastapi import APIRouter, Depends

from backend.dashboard.auth import get_current_user

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("")
async def list_cameras(user: dict = Depends(get_current_user)):
    """List all cameras for the authenticated user.

    Args:
        user: Authenticated user dict from Firebase.

    Returns:
        List of camera dicts with id, name, mode, enabled, location_id.

    TODO: query database
    """
    return {
        "cameras": [
            {
                "id": "CAM_FRONT_001",
                "name": "Front Door Camera",
                "mode": "indoor",
                "enabled": True,
                "location_id": "loc-001",
            }
        ],
        "total": 1,
    }


@router.post("")
async def add_camera(
    camera_data: dict,
    user: dict = Depends(get_current_user),
):
    """Add a new camera.

    Args:
        camera_data: Camera configuration dict.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with id and status.

    TODO: validate + save to DB
    """
    return {
        "id": camera_data.get("id", "CAM_NEW_001"),
        "status": "created",
    }


@router.put("/{camera_id}")
async def update_camera(
    camera_id: str,
    updates: dict,
    user: dict = Depends(get_current_user),
):
    """Update camera configuration.

    Args:
        camera_id: Camera identifier.
        updates: Dict of fields to update.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status.

    TODO: update DB
    """
    return {
        "status": "updated",
        "camera_id": camera_id,
    }


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: str,
    user: dict = Depends(get_current_user),
):
    """Remove a camera.

    Args:
        camera_id: Camera identifier to delete.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status.

    TODO: delete from DB + cleanup
    """
    return {
        "status": "deleted",
        "camera_id": camera_id,
    }
