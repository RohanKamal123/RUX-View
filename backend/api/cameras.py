"""
cameras.py — Camera API for Vision OS (Hybrid Backend).

CRUD operations for camera devices with 20-camera limit enforcement.
All routes are protected with Firebase Auth.
Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.config import settings
from backend.core.camera_limits import CameraLimits
from backend.core.config_store import get_max_cameras
from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

router = APIRouter(prefix="/cameras", tags=["cameras"])

# Global HybridCRUD instance (initialized in server.py)
hybrid_crud: HybridCRUD = None  # type: ignore


def _rtmp_push_url(stream_key: str) -> str:
    """Build the rtmp:// URL a DVR should be configured to push to.

    settings.rtmp_ingest_push_host currently points at a local dev
    MediaMTX instance -- see backend/core/ingest/rtmp_ingest.py's module
    docstring for the (verified, working) design and what's still needed
    to run this against a real always-on host.
    """
    return f"rtmp://{settings.rtmp_ingest_push_host}/live/{stream_key}"


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


@router.get("",
    summary="List all cameras for the authenticated user",
    description="Returns all cameras registered to the authenticated user, including their name, mode, RTSP URL, "
                "enabled status, and creation/last-seen timestamps. Use this endpoint to populate the camera management dashboard.",
    tags=["Cameras"],
    responses={
        200: {"description": "List of cameras returned successfully"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def list_cameras(
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """List all cameras for the authenticated user.

    Args:
        user: Authenticated user dict from Firebase.
        crud: HybridCRUD instance.

    Returns:
        Dict with cameras list and total count.
    """
    user_id = user.get("uid", "anonymous")
    cameras = await crud.get_user_cameras(user_id)
    return {
        "cameras": [{
            "id": c.camera_id,
            "name": c.name,
            "mode": c.mode,
            "enabled": c.is_active,
            "rtsp_url": c.rtsp_url,
            "connection_type": c.connection_type,
            "p2p_serial": c.p2p_serial,
            "p2p_username": c.p2p_username,
            "rtmp_push_url": _rtmp_push_url(c.rtmp_stream_key) if c.rtmp_stream_key else None,
            "created_at": c.created_at,
            "last_seen_at": c.last_seen_at,
        } for c in cameras],
        "total": len(cameras),
    }


@router.post("", status_code=201,
    summary="Register a new camera",
    description="Adds a new camera device for the authenticated user. Enforces a 20-camera limit based on the user's subscription tier. "
                "Requires a camera name; RTSP URL and mode are optional (defaults to 'indoor'). "
                "Returns the created camera ID and updated quota information.",
    tags=["Cameras"],
    responses={
        201: {"description": "Camera created successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        403: {"description": "Camera limit exceeded for current tier"},
        422: {"description": "Validation error — camera name is required"},
        500: {"description": "Storage error"},
    },
)
async def add_camera(
    camera_data: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Add a new camera with 20-camera limit enforcement.

    Args:
        camera_data: Camera configuration dict with name, rtsp_url, mode.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with id and status.

    Raises:
        HTTPException 403: If camera limit would be exceeded.
        HTTPException 422: If validation fails.
    """
    user_id = user.get("uid", "anonymous")
    name = camera_data.get("name", "Camera")
    rtsp_url = camera_data.get("rtsp_url", "")
    mode = camera_data.get("mode", "indoor")
    connection_type = camera_data.get("connection_type", "rtsp")
    p2p_serial = camera_data.get("p2p_serial", "")
    p2p_username = camera_data.get("p2p_username", "")
    p2p_password = camera_data.get("p2p_password", "")

    if not name:
        raise HTTPException(status_code=422, detail={
            "error": "Camera name is required", "code": "VALIDATION_ERROR",
        })

    if connection_type not in ("rtsp", "dahua_p2p", "rtmp_push"):
        raise HTTPException(status_code=422, detail={
            "error": "connection_type must be 'rtsp', 'rtmp_push', or 'dahua_p2p'", "code": "VALIDATION_ERROR",
        })
    # Connection details (rtsp_url, or p2p_serial/username/password) are
    # intentionally NOT required here -- a camera can be created as a bare
    # placeholder (name only) and have connection details filled in later,
    # matching pre-existing behavior where rtsp_url was always optional.

    try:
        # Check the limit BEFORE creating — create_camera() itself has no
        # quota check, so without this the "20-camera limit" this endpoint
        # advertises was never actually enforced (a camera would be created
        # unconditionally, and the limit only showed up after the fact in
        # the quota numbers returned alongside a 201).
        existing = await crud.get_user_cameras(user_id)
        tier = user.get("tier", "free")
        max_cameras = await get_max_cameras()
        validation = CameraLimits.validate_camera_count(
            user_id=user_id,
            current_count=len(existing),
            new_count=1,
            tier=tier,
            max_cameras_override=max_cameras,
        )
        if not validation.allowed:
            raise HTTPException(status_code=403, detail={
                "error": validation.message,
                "code": "CAMERA_LIMIT_EXCEEDED",
                "upgrade_suggestion": validation.upgrade_suggestion,
            })

        camera = await crud.create_camera(
            user_id=user_id,
            name=name,
            rtsp_url=rtsp_url,
            mode=mode,
            connection_type=connection_type,
            p2p_serial=p2p_serial,
            p2p_username=p2p_username,
            p2p_password=p2p_password,
        )
        quota = await crud.get_camera_quota(user_id)
        return {
            "id": camera.camera_id,
            "status": "created",
            "connection_type": camera.connection_type,
            "rtmp_push_url": _rtmp_push_url(camera.rtmp_stream_key) if camera.rtmp_stream_key else None,
            "quota": {
                "current": quota.total_cameras,
                "max": quota.max_cameras,
                "remaining": quota.remaining,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.get("/quota",
    summary="Get camera quota information",
    description="Returns the user's current camera count, maximum allowed cameras for their tier, remaining slots, "
                "usage percentage, and subscription tier name. Use this to show quota status in the UI.",
    tags=["Cameras"],
    responses={
        200: {"description": "Quota information returned successfully"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_camera_quota(
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get camera quota information for the authenticated user.

    Args:
        user: Authenticated user dict from Firebase.

    Returns:
        QuotaInfo with total, max, remaining, usage percentage, and tier.
    """
    user_id = user.get("uid", "anonymous")
    quota = await crud.get_camera_quota(user_id)
    return {
        "total_cameras": quota.total_cameras,
        "max_cameras": quota.max_cameras,
        "remaining": quota.remaining,
        "usage_percentage": quota.usage_percentage,
        "tier": quota.tier,
    }


@router.get("/{camera_id}",
    summary="Get details for a single camera",
    description="Returns full details for a specific camera by ID, including name, mode, RTSP URL, enabled status, "
                "and timestamps. Use this to populate the camera settings or edit view.",
    tags=["Cameras"],
    responses={
        200: {"description": "Camera details returned successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        404: {"description": "Camera not found"},
    },
)
async def get_camera(
    camera_id: str,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get camera details.

    Args:
        camera_id: Camera identifier.
        user: Authenticated user dict from Firebase.

    Returns:
        Camera details dict.

    Raises:
        HTTPException 404: If camera not found.
    """
    cameras = await crud.get_user_cameras(user.get("uid", "anonymous"))
    for c in cameras:
        if c.camera_id == camera_id:
            return {
                "id": c.camera_id,
                "user_id": c.user_id,
                "name": c.name,
                "mode": c.mode,
                "enabled": c.is_active,
                "rtsp_url": c.rtsp_url,
                "connection_type": c.connection_type,
                "p2p_serial": c.p2p_serial,
                "p2p_username": c.p2p_username,
                "rtmp_push_url": _rtmp_push_url(c.rtmp_stream_key) if c.rtmp_stream_key else None,
                "created_at": c.created_at,
                "last_seen_at": c.last_seen_at,
            }
    raise HTTPException(status_code=404, detail={
        "error": f"Camera {camera_id} not found", "code": "NOT_FOUND",
    })


@router.put("/{camera_id}",
    summary="Update a camera",
    description="Updates name/mode/enabled/rtsp_url for a camera owned by the authenticated user.",
    tags=["Cameras"],
    responses={
        200: {"description": "Camera updated successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        404: {"description": "Camera not found"},
        500: {"description": "Storage error"},
    },
)
async def update_camera(
    camera_id: str,
    updates: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Update a camera owned by the authenticated user.

    Raises:
        HTTPException 404: If the camera doesn't exist or isn't owned by this user.
    """
    user_id = user.get("uid", "anonymous")
    owned = await crud.get_user_cameras(user_id)
    if not any(c.camera_id == camera_id for c in owned):
        raise HTTPException(status_code=404, detail={
            "error": f"Camera {camera_id} not found", "code": "NOT_FOUND",
        })

    try:
        camera = await crud.update_camera(camera_id, user_id, updates)
        return {
            "status": "updated",
            "camera_id": camera.camera_id,
            "name": camera.name,
            "mode": camera.mode,
            "enabled": camera.is_active,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.delete("/{camera_id}",
    summary="Delete a camera",
    description="Removes a camera owned by the authenticated user.",
    tags=["Cameras"],
    responses={
        200: {"description": "Camera deleted successfully"},
        401: {"description": "Missing or invalid Firebase token"},
        404: {"description": "Camera not found"},
        500: {"description": "Storage error"},
    },
)
async def delete_camera(
    camera_id: str,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Delete a camera owned by the authenticated user.

    Raises:
        HTTPException 404: If the camera doesn't exist or isn't owned by this user.
    """
    user_id = user.get("uid", "anonymous")
    try:
        deleted = await crud.delete_camera(camera_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })

    if not deleted:
        raise HTTPException(status_code=404, detail={
            "error": f"Camera {camera_id} not found", "code": "NOT_FOUND",
        })

    return {"status": "deleted", "camera_id": camera_id}


@router.get("/{camera_id}/events",
    summary="Get events for a specific camera",
    description="Returns events (motion and audio triggers) for a specific camera, ordered by creation time. "
                "Use this to populate a camera-specific event history view. Defaults to 50 events.",
    tags=["Cameras"],
    responses={
        200: {"description": "List of camera events returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_camera_events(
    camera_id: str,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get events for a specific camera.

    Args:
        camera_id: Camera identifier.
        limit: Maximum number of events to return.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with events list.
    """
    events = await crud.get_camera_events(camera_id, limit=limit)
    return {
        "events": [{
            "event_id": e.event_id,
            "camera_id": e.camera_id,
            "event_type": e.event_type,
            "confidence": e.confidence,
            "created_at": e.created_at,
        } for e in events],
        "total": len(events),
    }