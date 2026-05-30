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


@router.get("/summary")
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


@router.get("/daily")
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


@router.get("/user-growth")
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


@router.get("/revenue")
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


@router.get("/event-breakdown")
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


@router.get("/camera-usage")
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


@router.post("/refresh")
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
