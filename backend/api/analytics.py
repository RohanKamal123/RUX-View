"""
analytics.py — Analytics API Endpoints for Vision OS.

Provides REST API endpoints for analytics data from PostgreSQL.
MEGA.nz analytics has been removed entirely.

Endpoints:
    GET /api/analytics/summary — Get analytics summary
    GET /api/analytics/daily — Get daily stats range
    GET /api/analytics/user-growth — Get user growth trend
    GET /api/analytics/revenue — Get revenue trend
    POST /api/analytics/refresh — Trigger manual aggregation (admin only)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dashboard.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"], prefix="/api/analytics")


@router.get("/summary",
    summary="Get high-level analytics summary",
    description="Returns aggregate platform metrics including total users, cameras, events detected, "
                "revenue in BDT, and active subscription count. Currently returns placeholder data "
                "as analytics aggregation is under development.",
    tags=["Analytics"],
    responses={
        200: {"description": "Analytics summary returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_analytics_summary(
    user: dict = Depends(get_current_user),
):
    """Get a high-level analytics summary.

    Args:
        user: Authenticated user.

    Returns:
        Dict with placeholder analytics data.
    """
    return {
        "total_users": 0,
        "total_cameras": 0,
        "events_detected": 0,
        "revenue_bdt": 0,
        "active_subscriptions": 0,
        "message": "Analytics system uses PostgreSQL. MEGA.nz has been removed.",
    }


@router.get("/daily",
    summary="Get daily statistics for a date range",
    description="Returns daily event counts and platform activity for the specified date range. "
                "Requires start and end dates in YYYY-MM-DD format. "
                "Currently returns placeholder data.",
    tags=["Analytics"],
    responses={
        200: {"description": "Daily stats returned"},
        401: {"description": "Missing or invalid Firebase token"},
        422: {"description": "Validation error — invalid date format"},
    },
)
async def get_daily_stats(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    user: dict = Depends(get_current_user),
):
    """Get daily statistics for a date range.

    Args:
        start: Start date in YYYY-MM-DD format.
        end: End date in YYYY-MM-DD format.
        user: Authenticated user.

    Returns:
        List of daily stats (placeholder).
    """
    return []


@router.get("/user-growth",
    summary="Get user growth trend over a period",
    description="Returns the trend of new user registrations over the specified number of days. "
                "Use this to visualize user acquisition on the admin dashboard. "
                "Currently returns placeholder data.",
    tags=["Analytics"],
    responses={
        200: {"description": "User growth trend returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_user_growth(
    days: int = Query(30, description="Number of days to look back"),
    user: dict = Depends(get_current_user),
):
    """Get user growth trend over a period.

    Args:
        days: Number of days to look back (default: 30).
        user: Authenticated user.

    Returns:
        List of dicts with date and user count (placeholder).
    """
    return []


@router.get("/revenue",
    summary="Get revenue trend over a period",
    description="Returns revenue data (in BDT) over the specified number of days. "
                "Use this to visualize revenue on the admin analytics dashboard. "
                "Currently returns placeholder data.",
    tags=["Analytics"],
    responses={
        200: {"description": "Revenue trend returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_revenue_trend(
    days: int = Query(30, description="Number of days to look back"),
    user: dict = Depends(get_current_user),
):
    """Get revenue trend over a period.

    Args:
        days: Number of days to look back (default: 30).
        user: Authenticated user.

    Returns:
        List of dicts with date and revenue (placeholder).
    """
    return []


@router.get("/event-breakdown",
    summary="Get breakdown of events by type",
    description="Returns counts of events grouped by type (e.g. motion, audio) over the specified number of days. "
                "Use this to understand what kinds of events are being detected. "
                "Currently returns placeholder data.",
    tags=["Analytics"],
    responses={
        200: {"description": "Event breakdown returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_event_breakdown(
    days: int = Query(7, description="Number of days to look back"),
    user: dict = Depends(get_current_user),
):
    """Get breakdown of events by type.

    Args:
        days: Number of days to look back (default: 7).
        user: Authenticated user.

    Returns:
        Dict with event types as keys and counts as values (placeholder).
    """
    return {}


@router.get("/camera-usage",
    summary="Get camera usage statistics",
    description="Returns camera usage metrics including total cameras, active cameras, and inactive cameras. "
                "Use this to monitor camera health and adoption on the admin dashboard. "
                "Currently returns placeholder data.",
    tags=["Analytics"],
    responses={
        200: {"description": "Camera usage stats returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
async def get_camera_usage(
    user: dict = Depends(get_current_user),
):
    """Get camera usage statistics.

    Args:
        user: Authenticated user.

    Returns:
        Dict with camera usage metrics (placeholder).
    """
    return {
        "total_cameras": 0,
        "active_cameras": 0,
        "inactive_cameras": 0,
    }


@router.post("/refresh",
    summary="Trigger manual analytics aggregation (admin)",
    description="Triggers a manual refresh of analytics data aggregation. "
                "Requires business-tier (admin) authentication. "
                "Currently returns a success message as placeholder.",
    tags=["Analytics"],
    responses={
        200: {"description": "Analytics refresh triggered"},
        401: {"description": "Missing or invalid Firebase token"},
        403: {"description": "Admin access required — business tier needed"},
    },
)
async def refresh_analytics(
    user: dict = Depends(get_current_user),
):
    """Trigger manual analytics aggregation (admin only).

    Args:
        user: Authenticated user (must be business tier).

    Returns:
        Dict with refresh status.
    """
    if user.get("tier") != "business":
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Business tier needed.",
        )

    return {
        "status": "success",
        "message": "Analytics refresh triggered. MEGA.nz analytics has been removed.",
    }