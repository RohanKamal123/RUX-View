"""
routes.py — Dashboard Routes for Vision OS (Hybrid Backend).

Provides dashboard pages that read real data from HybridCRUD
(MEGA.nz + PostgreSQL fallback). All routes are async and use
Firebase Auth for authentication.
Dark navy theme with mobile-first responsive design.

Routes:
    GET / — Landing page (public)
    GET /login — Login page (public)
    POST /login — Login form submission (sets session cookie in dev mode)
    GET /dashboard — Main dashboard (auth required)
    GET /dashboard/cameras — Camera management page
    GET /dashboard/events — Event feed page
    GET /dashboard/settings — User settings page
    GET /dashboard/billing — Billing & subscription page
    GET /dashboard/admin — Admin panel (admin only)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.dashboard.auth import (
    get_current_user,
    require_tier,
    set_session_cookie,
    verify_token,
)
from backend.config import settings
from backend.storage.hybrid_crud import HybridCRUD

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# Templates
templates = Jinja2Templates(directory="backend/dashboard/templates")

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


# ── Login Page ──────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Login page (public)."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "environment": settings.environment},
    )


@router.post("/login", include_in_schema=False)
async def login_submit(request: Request):
    """Handle login form submission.

    In development mode, accepts any email/password and sets a
    signed session cookie, then redirects to /dashboard.

    In production, this would validate against Firebase Auth.
    """
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    if not email or not password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Please enter email and password."},
            status_code=400,
        )

    # In development mode, accept any credentials
    if settings.environment == "development":
        user = await verify_token("dev-token")
        response = RedirectResponse(url="/dashboard", status_code=303)
        set_session_cookie(response, user)
        return response

    # Production: would validate against Firebase Auth here
    # For now, return error since Firebase token auth is handled client-side
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Production login not available via form. Use Firebase client SDK.",
        },
        status_code=400,
    )


# ── Landing Page ────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    """Landing page (public)."""
    return templates.TemplateResponse(
        "landing.html",
        {"request": request},
    )


# ── Main Dashboard ──────────────────────────────────────────────


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def main_dashboard(
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Main dashboard page (auth required).

    Shows camera count, recent events, online/offline status,
    storage usage, subscription info, and quick stats.
    """
    user_id = user.get("uid", "anonymous")

    try:
        cameras, recent_events, profile, events_today_count = await asyncio.gather(
            crud.get_user_cameras(user_id),
            crud.get_user_events(user_id, limit=10),
            crud.get_or_create_user(user_id=user_id),
            crud.count_user_events(user_id),
        )
        camera_count = len(cameras)
        cameras_online = sum(1 for c in cameras if c.is_active)
        cameras_offline = camera_count - cameras_online

        # Build quota from already-fetched cameras — no extra DB call
        from backend.storage.hybrid_crud import QuotaInfo
        max_cam = 20
        total = len(cameras)
        quota = QuotaInfo(
            total_cameras=total,
            max_cameras=max_cam,
            remaining=max(0, max_cam - total),
            usage_percentage=round((total / max_cam) * 100, 1),
            tier=profile.tier if profile else "free",
        )
        tier = profile.tier if profile else "free"

        alerts_sent = sum(1 for e in recent_events if e.event_type == "alert")

        # Build daily summary
        from collections import Counter
        event_types_count = Counter(e.event_type for e in recent_events)
        high_threat_count = sum(1 for e in recent_events if getattr(e, 'threat_level', 'LOW') in ('HIGH', 'CRITICAL'))
        last_alert = next((e for e in recent_events if e.alert_message), None)
        last_alert_message = last_alert.alert_message if last_alert else None
        last_alert_time = last_alert.created_at[:19].replace('T', ' ') if last_alert else None

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "cameras": cameras,
                "camera_count": camera_count,
                "cameras_online": cameras_online,
                "cameras_offline": cameras_offline,
                "recent_events": recent_events,
                "events_today_count": events_today_count,
                "alerts_sent": alerts_sent,
                "event_types_count": dict(event_types_count),
                "high_threat_count": high_threat_count,
                "last_alert_message": last_alert_message,
                "last_alert_time": last_alert_time,
                "quota": quota,
                "tier": tier,
                "active_page": "dashboard",
            },
        )
    except Exception as e:
        logger.error("Dashboard data error: %s", e)
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "cameras": [],
                "camera_count": 0,
                "cameras_online": 0,
                "cameras_offline": 0,
                "recent_events": [],
                "events_today_count": 0,
                "alerts_sent": 0,
                "quota": None,
                "tier": "free",
                "active_page": "dashboard",
                "error": "Could not load dashboard data. Storage may be unavailable.",
            },
        )


# ── Camera Management Page ──────────────────────────────────────


@router.get("/dashboard/cameras", response_class=HTMLResponse, include_in_schema=False)
async def camera_management_page(
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Camera management page (auth required)."""
    user_id = user.get("uid", "anonymous")

    try:
        cameras = await crud.get_user_cameras(user_id)

        return templates.TemplateResponse(
            "cameras.html",
            {
                "request": request,
                "user": user,
                "cameras": cameras,
                "active_page": "cameras",
            },
        )

    except Exception as e:
        logger.error("Camera page error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load cameras")


# ── Event Feed Page ─────────────────────────────────────────────


@router.get("/dashboard/events", response_class=HTMLResponse, include_in_schema=False)
async def event_feed_page(
    request: Request,
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50),
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Event feed page (auth required)."""
    user_id = user.get("uid", "anonymous")

    try:
        if camera_id:
            events = await crud.get_camera_events(camera_id, limit=limit)
        else:
            events = await crud.get_user_events(user_id, limit=limit)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        cameras = await crud.get_user_cameras(user_id)

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "user": user,
                "events": events,
                "cameras": cameras,
                "active_page": "events",
                "filter_camera_id": camera_id,
                "filter_event_type": event_type,
            },
        )
    except Exception as e:
        logger.error("Events page error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load events")


# ── Settings Page ───────────────────────────────────────────────


@router.get("/dashboard/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """User settings page (auth required)."""
    user_id = user.get("uid", "anonymous")

    try:
        profile = await crud.get_or_create_user(user_id=user_id)
        cameras = await crud.get_user_cameras(user_id)

        camera_count = len(cameras)
        max_cameras = 20
        remaining = max(0, max_cameras - camera_count)
        quota_percentage = round((camera_count / max_cameras) * 100, 1) if max_cameras > 0 else 0

        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "user": user,
                "profile": profile,
                "cameras": cameras,
                "camera_count": camera_count,
                "remaining": remaining,
                "quota_percentage": quota_percentage,
                "active_page": "settings",
            },
        )
    except Exception as e:
        logger.error("Settings page error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load settings")


# ── Billing Page ────────────────────────────────────────────────


@router.get("/dashboard/billing", response_class=HTMLResponse, include_in_schema=False)
async def billing_page(
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Billing & subscription page (auth required)."""
    user_id = user.get("uid", "anonymous")

    try:
        profile = await crud.get_or_create_user(user_id=user_id)
        quota = await crud.get_camera_quota(user_id)
        tier = profile.tier if profile else "free"
        payments = await crud.get_user_payments(user_id=user_id, limit=20)

        return templates.TemplateResponse(
            "payment.html",
            {
                "request": request,
                "user": user,
                "profile": profile,
                "payments": payments,
                "quota": quota,
                "tier": tier,
                "active_page": "billing",
            },
        )
    except Exception as e:
        logger.error("Billing page error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load billing info")


# ── Admin Panel ─────────────────────────────────────────────────


@router.get("/dashboard/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_panel(
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Admin panel page (admin only)."""
    user_tier = user.get("tier", "free")
    if user_tier != "business":
        raise HTTPException(
            status_code=403,
            detail="Admin access requires business tier",
        )

    try:
        cameras = await crud.get_user_cameras(user.get("uid", "anonymous"))
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "user": user,
                "total_users": 1,
                "users_by_tier": {"free": 1},
                "all_users": [user],
                "active_page": "admin",
            },
        )
    except Exception as e:
        logger.error("Admin page error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load admin panel")


# ── JSON API Endpoints for Dashboard ────────────────────────────


@router.get("/api/events")
async def get_events_api(
    limit: int = Query(50, description="Maximum number of events"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    threat_level: Optional[str] = Query(None, description="Filter by threat level"),
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """JSON endpoint for the event feed page (called by app.js auto-refresh).

    Supports filtering by camera_id, threat_level, and limit.
    Returns events with thumbnail URLs, person IDs, and alert messages.

    Args:
        limit: Max events to return.
        camera_id: Optional camera filter.
        threat_level: Optional threat level filter.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with events list and total count.
    """
    user_id = user.get("uid", "anonymous")

    try:
        events = await crud.get_user_events(user_id, limit=limit)

        if camera_id:
            events = [e for e in events if e.camera_id == camera_id]
        if threat_level:
            events = [e for e in events if getattr(e, 'threat_level', None) == threat_level]

        return {
            "events": [{
                "event_id": e.event_id,
                "camera_id": e.camera_id,
                "camera_name": getattr(e, 'camera_name', None) or e.camera_id,
                "event_type": e.event_type,
                "threat_level": getattr(e, 'threat_level', 'LOW'),
                "confidence": e.confidence,
                "alert_message": getattr(e, 'alert_message', 'Motion detected'),
                "timestamp_start": e.created_at,
                "timestamp_end": getattr(e, 'timestamp_end', None),
                "duration_sec": int(getattr(e, 'duration_sec', 0) or 0),
                "frame_count": (
                    int((e.details or {}).get('frame_count', 0))
                    if hasattr(e, 'details') and e.details
                    else 0
                ),
                "person_ids": getattr(e, 'person_ids', []),
                "thumbnail_url": (
                    f"/api/triggers/image/{e.event_id}"
                    if hasattr(e, 'details') and e.details and e.details.get('image_base64')
                    else "/static/placeholder.jpg"
                ),
            } for e in events],
            "total": len(events),
        }
    except Exception as exc:
        logger.error("Failed to fetch events: %s", exc)
        return {"events": [], "total": 0, "error": str(exc)}


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """JSON endpoint for dashboard real-time stats."""
    user_id = user.get("uid", "anonymous")

    try:
        cameras, events_today = await asyncio.gather(
            crud.get_user_cameras(user_id),
            crud.count_user_events(user_id),
        )
        camera_count = len(cameras)
        cameras_online = sum(1 for c in cameras if c.is_active)

        # Build stats inline — no extra quota DB call
        max_cam = 20
        total = len(cameras)
        quota_remaining = max(0, max_cam - total)
        quota_usage_pct = round((total / max_cam) * 100, 1) if max_cam > 0 else 0

        return {
            "camera_count": camera_count,
            "cameras_online": cameras_online,
            "cameras_offline": camera_count - cameras_online,
            "events_today": events_today,
            "quota_remaining": quota_remaining,
            "quota_usage_pct": quota_usage_pct,
            "tier": "free",
        }
    except Exception as e:
        logger.error("Dashboard stats error: %s", e)
        return {
            "error": str(e),
            "camera_count": 0,
            "cameras_online": 0,
            "cameras_offline": 0,
            "events_today": 0,
        }
