"""
server.py — Vision OS Dashboard (FastAPI + Jinja2 + Firebase Auth).

Mobile-first responsive dashboard with:
- Event feed with auto-refresh every 30s
- Per-camera event pages
- Person profile pages (household/business tier)
- Settings and payment pages
- Firebase Auth for login
- Tier-gated premium pages
"""

import logging
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

app = FastAPI(title="Vision OS Dashboard")

# Mount static files
app.mount("/static", StaticFiles(directory="backend/dashboard/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="backend/dashboard/templates")


# ── Firebase Auth Dependency ────────────────────────────────────


async def get_current_user(request: Request) -> dict:
    """Get current user from Firebase Auth token in session/cookie.

    For development/testing, returns a mock user.
    In production, validates Firebase ID token from Authorization header.

    Args:
        request: FastAPI request object.

    Returns:
        User dict with user_id, email, tier, etc.

    Raises:
        HTTPException 401 if not authenticated.
    """
    # In production, extract and verify Firebase ID token
    # For now, check session or header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # TODO: Verify Firebase token
        # firebase_user = await verify_firebase_token(token)
        pass

    # Development mock user
    user = {
        "user_id": "user_001",
        "email": "test@example.com",
        "tier": "household",
        "telegram_chat_id": "123456",
        "name": "Test User",
    }

    # Check for tier override in query params (for testing)
    tier_override = request.query_params.get("tier")
    if tier_override:
        user["tier"] = tier_override

    return user


def require_tier(min_tier: str):
    """Factory for tier requirement dependency.

    Tier hierarchy: free < household < business

    Args:
        min_tier: Minimum required tier.

    Returns:
        Dependency function that checks user tier.
    """
    tier_order = {"free": 0, "household": 1, "business": 2}
    required_tier = min_tier.lower()

    async def _check_tier(user: dict = Depends(get_current_user)) -> dict:
        """Check if user meets tier requirement.

        Args:
            user: Current user dict.

        Returns:
            User dict if authorized.

        Raises:
            HTTPException 403 if tier too low.
        """
        user_tier = user.get("tier", "free").lower()

        if tier_order.get(user_tier, 0) < tier_order.get(required_tier, 0):
            raise HTTPException(
                status_code=403,
                detail=f"This page requires {min_tier} tier or above. "
                       f"Your current tier: {user.get('tier', 'free')}",
            )
        return user

    return _check_tier


# ── Mock Data Helpers ───────────────────────────────────────────


def _get_mock_cameras() -> list[dict]:
    """Get mock camera list for development."""
    return [
        {"id": "cam_001", "name": "Front Gate", "mode": "outdoor", "status": "online"},
        {"id": "cam_002", "name": "Back Door", "mode": "outdoor", "status": "online"},
        {"id": "cam_003", "name": "Living Room", "mode": "indoor", "status": "online"},
        {"id": "cam_004", "name": "Parking Lot", "mode": "parking", "status": "offline"},
        {"id": "cam_005", "name": "Shop Floor", "mode": "shop", "status": "online"},
    ]


def _get_mock_events(camera_id: Optional[str] = None,
                     threat_level: Optional[str] = None,
                     limit: int = 50) -> list[dict]:
    """Get mock events for development."""
    all_events = [
        {
            "id": "evt_001",
            "camera_id": "cam_001",
            "camera_name": "Front Gate",
            "threat_level": "HIGH",
            "alert_message": "Unknown person at front gate after hours",
            "timestamp_start": datetime(2024, 6, 15, 22, 30, 0),
            "duration_sec": 45.0,
            "thumbnail_url": None,
            "person_ids": ["PERSON_A1B2"],
            "mode": "outdoor",
        },
        {
            "id": "evt_002",
            "camera_id": "cam_003",
            "camera_name": "Living Room",
            "threat_level": "LOW",
            "alert_message": "Motion detected in living room",
            "timestamp_start": datetime(2024, 6, 15, 18, 15, 0),
            "duration_sec": 12.0,
            "thumbnail_url": None,
            "person_ids": [],
            "mode": "indoor",
        },
        {
            "id": "evt_003",
            "camera_id": "cam_001",
            "camera_name": "Front Gate",
            "threat_level": "MEDIUM",
            "alert_message": "Vehicle stopped at gate",
            "timestamp_start": datetime(2024, 6, 15, 14, 0, 0),
            "duration_sec": 30.0,
            "thumbnail_url": None,
            "person_ids": [],
            "mode": "outdoor",
        },
        {
            "id": "evt_004",
            "camera_id": "cam_002",
            "camera_name": "Back Door",
            "threat_level": "EMERGENCY",
            "alert_message": "Forced entry detected at back door",
            "timestamp_start": datetime(2024, 6, 15, 3, 0, 0),
            "duration_sec": 60.0,
            "thumbnail_url": None,
            "person_ids": ["PERSON_C3D4", "PERSON_E5F6"],
            "mode": "outdoor",
        },
        {
            "id": "evt_005",
            "camera_id": "cam_005",
            "camera_name": "Shop Floor",
            "threat_level": "LOW",
            "alert_message": "Customer entered shop",
            "timestamp_start": datetime(2024, 6, 15, 10, 30, 0),
            "duration_sec": 180.0,
            "thumbnail_url": None,
            "person_ids": ["PERSON_G7H8"],
            "mode": "shop",
        },
        {
            "id": "evt_006",
            "camera_id": "cam_004",
            "camera_name": "Parking Lot",
            "threat_level": "MEDIUM",
            "alert_message": "Person loitering near vehicles",
            "timestamp_start": datetime(2024, 6, 15, 23, 0, 0),
            "duration_sec": 120.0,
            "thumbnail_url": None,
            "person_ids": ["PERSON_I9J0"],
            "mode": "parking",
        },
    ]

    # Filter by camera_id
    if camera_id:
        all_events = [e for e in all_events if e["camera_id"] == camera_id]

    # Filter by threat_level
    if threat_level:
        all_events = [e for e in all_events if e["threat_level"] == threat_level.upper()]

    # Sort by timestamp descending
    all_events.sort(key=lambda e: e["timestamp_start"], reverse=True)

    return all_events[:limit]


def _get_mock_person_sightings(person_uid: str) -> list[dict]:
    """Get mock person sightings for development."""
    return [
        {
            "event_id": "evt_001",
            "camera_name": "Front Gate",
            "timestamp": datetime(2024, 6, 15, 22, 30, 0),
            "threat_level": "HIGH",
            "thumbnail_url": None,
            "appearance": {
                "gender": "male",
                "clothing": "dark hoodie, jeans",
                "hand_objects": "none",
                "action": "walking",
            },
        },
        {
            "event_id": "evt_003",
            "camera_name": "Front Gate",
            "timestamp": datetime(2024, 6, 15, 14, 0, 0),
            "threat_level": "MEDIUM",
            "thumbnail_url": None,
            "appearance": {
                "gender": "male",
                "clothing": "red t-shirt, shorts",
                "hand_objects": "phone",
                "action": "standing",
            },
        },
    ]


# ── Routes ──────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page with Firebase Auth UI."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: dict = Depends(get_current_user)):
    """Main event feed page.

    Shows all events across all user's cameras.
    Filterable by camera, threat level, date range.
    Auto-refreshes every 30s via JS.
    """
    cameras = _get_mock_cameras()
    events = _get_mock_events()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "cameras": cameras,
            "events": events,
            "active_page": "index",
        },
    )


@app.get("/camera/{camera_id}", response_class=HTMLResponse)
async def camera_page(request: Request, camera_id: str,
                      user: dict = Depends(get_current_user)):
    """Per-camera event list page.

    Shows events for a single camera.
    """
    cameras = _get_mock_cameras()
    camera = next((c for c in cameras if c["id"] == camera_id), None)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    events = _get_mock_events(camera_id=camera_id)

    return templates.TemplateResponse(
        "camera.html",
        {
            "request": request,
            "user": user,
            "camera": camera,
            "events": events,
            "active_page": "camera",
        },
    )


@app.get("/person/{person_uid}", response_class=HTMLResponse)
async def person_page(request: Request, person_uid: str,
                      user: dict = Depends(require_tier("household"))):
    """Person profile page.

    Shows sightings timeline, appearance history, threat flags.
    Requires household tier or above.
    """
    sightings = _get_mock_person_sightings(person_uid)

    # Calculate threat flag
    threat_flags = [s for s in sightings if s["threat_level"] in ("HIGH", "EMERGENCY")]
    threat_flag = "HIGH" if threat_flags else "LOW"

    return templates.TemplateResponse(
        "person.html",
        {
            "request": request,
            "user": user,
            "person_uid": person_uid,
            "sightings": sightings,
            "threat_flag": threat_flag,
            "active_page": "person",
        },
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request,
                        user: dict = Depends(get_current_user)):
    """Settings page.

    Camera config, ignore zones, account settings.
    """
    cameras = _get_mock_cameras()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "cameras": cameras,
            "active_page": "settings",
        },
    )


@app.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request,
                       user: dict = Depends(get_current_user)):
    """Payment info page.

    Shows bKash/Nagad number for manual payment.
    """
    return templates.TemplateResponse(
        "payment.html",
        {
            "request": request,
            "user": user,
            "active_page": "payment",
        },
    )


# ── JSON API Endpoints ──────────────────────────────────────────


@app.get("/api/events")
async def api_events(camera_id: Optional[str] = Query(None),
                     threat_level: Optional[str] = Query(None),
                     limit: int = Query(50),
                     user: dict = Depends(get_current_user)):
    """JSON endpoint for event feed auto-refresh.

    Args:
        camera_id: Filter by camera ID (optional).
        threat_level: Filter by threat level (optional).
        limit: Max events to return (default 50).
        user: Current user (from auth).

    Returns:
        List of event dicts with ISO-formatted timestamps.
    """
    events = _get_mock_events(camera_id=camera_id, threat_level=threat_level, limit=limit)

    # Convert datetimes to ISO strings for JSON serialization
    serialized = []
    for event in events:
        e = dict(event)
        e["timestamp_start"] = e["timestamp_start"].isoformat()
        serialized.append(e)

    return {"events": serialized, "count": len(serialized)}


@app.get("/api/person/{person_uid}/sightings")
async def api_person_sightings(person_uid: str,
                               user: dict = Depends(get_current_user)):
    """JSON endpoint for person sightings timeline.

    Args:
        person_uid: Person UID to get sightings for.
        user: Current user (from auth).

    Returns:
        List of sighting dicts with ISO-formatted timestamps.
    """
    sightings = _get_mock_person_sightings(person_uid)

    serialized = []
    for sighting in sightings:
        s = dict(sighting)
        s["timestamp"] = s["timestamp"].isoformat()
        serialized.append(s)

    return {"person_uid": person_uid, "sightings": serialized, "count": len(serialized)}


# ── Health Check ────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Vision OS Dashboard"}
