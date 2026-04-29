"""API endpoints for multi-location management.

Provides CRUD operations for user locations with tier enforcement,
camera topology management, and location stats.
"""

from fastapi import APIRouter, Depends, HTTPException
from datetime import date
import logging

from backend.core.location_manager import LocationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/locations", tags=["locations"])


async def get_location_manager() -> LocationManager:
    """Dependency: Get LocationManager instance."""
    # In production, this would be wired via dependency injection
    from backend.config import get_db_session_factory
    return LocationManager(get_db_session_factory())


async def get_current_user():
    """Dependency: Get current authenticated user.

    In production, this validates Firebase Auth token and returns user dict.
    """
    # Placeholder - actual implementation in backend/dashboard/auth.py
    return {"id": "user-001", "tier": "free", "email": "user@example.com"}


@router.get("/")
async def list_locations(
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """List all locations for the authenticated user.

    Returns:
        List of LocationSummary with camera counts and event stats
    """
    try:
        locations = await location_manager.get_locations(user["id"])
        return {"locations": [loc.__dict__ for loc in locations]}
    except Exception as e:
        logger.error(f"Failed to list locations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch locations")


@router.get("/{location_id}")
async def get_location(
    location_id: str,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Get location details with cameras.

    Args:
        location_id: Location UUID

    Returns:
        LocationDetail with cameras list
    """
    try:
        location = await location_manager.get_location(location_id, user["id"])
        return location.__dict__
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get location {location_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch location")


@router.post("/")
async def create_location(
    data: dict,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Create a new location.

    Checks tier limit before creating.

    Request body:
        name (str): Location name (required)
        address (str, optional): Location address
        timezone (str, optional): Timezone (default: Asia/Dhaka)

    Returns:
        Created LocationDetail
    """
    name = data.get("name")
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Location name is required")

    try:
        location = await location_manager.create_location(
            user_id=user["id"],
            name=name.strip(),
            address=data.get("address"),
            timezone=data.get("timezone", "Asia/Dhaka"),
        )
        return location.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create location: {e}")
        raise HTTPException(status_code=500, detail="Failed to create location")


@router.put("/{location_id}")
async def update_location(
    location_id: str,
    data: dict,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Update location properties.

    Args:
        location_id: Location UUID
        data: Dict with fields to update

    Returns:
        Updated LocationDetail
    """
    try:
        location = await location_manager.update_location(
            location_id=location_id,
            user_id=user["id"],
            updates=data,
        )
        return location.__dict__
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update location {location_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update location")


@router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Delete a location and all associated data.

    Cascades: cameras, events, persons, analytics

    Args:
        location_id: Location UUID

    Returns:
        {"deleted": true}
    """
    try:
        deleted = await location_manager.delete_location(location_id, user["id"])
        return {"deleted": deleted}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete location {location_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete location")


@router.get("/{location_id}/stats")
async def get_location_stats(
    location_id: str,
    date_param: str,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Get location stats for a date.

    Args:
        location_id: Location UUID
        date_param: Date string (YYYY-MM-DD)

    Returns:
        {events, high_threats, persons_seen, audio_events, alerts_sent}
    """
    try:
        stats_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )

    try:
        stats = await location_manager.get_location_stats(location_id, stats_date)
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats for location {location_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch location stats")


@router.put("/{location_id}/topology")
async def update_topology(
    location_id: str,
    topology: dict,
    user: dict = Depends(get_current_user),
    location_manager: LocationManager = Depends(get_location_manager),
):
    """Update camera topology for a location.

    Validates no cycles before saving.

    Args:
        location_id: Location UUID
        topology: Camera topology dict

    Returns:
        {"updated": true}
    """
    try:
        await location_manager.update_camera_topology(location_id, topology)
        return {"updated": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update topology for {location_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update topology")
