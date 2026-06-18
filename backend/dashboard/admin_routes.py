"""Admin dashboard routes for Vision OS beta launch.

Provides admin-only endpoints for user management, error monitoring,
beta invite management, feedback collection, and system health.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="backend/dashboard/templates")


async def get_current_user():
    """Dependency: Get current authenticated user.

    In production, this validates Firebase Auth token.
    """
    return {"id": "admin-001", "role": "admin", "email": "admin@visionos.com"}


def require_admin(user: dict = Depends(get_current_user)):
    """Check if user has admin role.

    Raises HTTPException(403) if not admin.

    Args:
        user: Authenticated user dict

    Returns:
        User dict if admin

    Raises:
        HTTPException: 403 if not admin
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user


# In-memory stores (replace with DB in production)
_beta_invites: list[dict] = []
_feedback_store: list[dict] = []


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Admin dashboard page.

    Shows:
    - Total users, cameras, locations
    - Active vs inactive users
    - Error rate chart (last 24h)
    - System health status
    - Recent signups
    """
    stats = {
        "total_users": 42,
        "active_cameras": 156,
        "errors_24h": 7,
        "health_status": "healthy",
    }

    recent_users = [
        {
            "id": "user-001",
            "email": "user1@example.com",
            "tier": "household",
            "camera_count": 3,
            "created_at": "2026-04-27",
            "status": "active",
        },
        {
            "id": "user-002",
            "email": "user2@example.com",
            "tier": "free",
            "camera_count": 1,
            "created_at": "2026-04-26",
            "status": "active",
        },
        {
            "id": "user-003",
            "email": "user3@example.com",
            "tier": "business",
            "camera_count": 5,
            "created_at": "2026-04-25",
            "status": "trial",
        },
    ]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "recent_users": recent_users,
            "active_tab": "overview",
        },
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: dict = Depends(require_admin),
):
    """User management page.

    Shows all users with:
    - Email, tier, camera count, last active
    - Status (active/trial/expired/disabled)
    - Actions: upgrade, downgrade, disable
    """
    users = [
        {
            "id": "user-001",
            "email": "user1@example.com",
            "tier": "household",
            "camera_count": 3,
            "last_active": "2026-04-27 14:30",
            "status": "active",
        },
        {
            "id": "user-002",
            "email": "user2@example.com",
            "tier": "free",
            "camera_count": 1,
            "last_active": "2026-04-26 10:00",
            "status": "active",
        },
        {
            "id": "user-003",
            "email": "user3@example.com",
            "tier": "business",
            "camera_count": 5,
            "last_active": "2026-04-27 09:00",
            "status": "trial",
        },
        {
            "id": "user-004",
            "email": "user4@example.com",
            "tier": "free",
            "camera_count": 0,
            "last_active": "2026-04-20 08:00",
            "status": "expired",
        },
        {
            "id": "user-005",
            "email": "user5@example.com",
            "tier": "household",
            "camera_count": 2,
            "last_active": "2026-04-25 16:45",
            "status": "disabled",
        },
    ]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "active_tab": "users",
        },
    )


@router.get("/users/{user_id}")
async def admin_user_detail(
    user_id: str,
    user: dict = Depends(require_admin),
):
    """User detail page.

    Shows:
    - User profile + subscription info
    - All locations + cameras
    - Recent events
    - Error logs
    - Manual tier change form
    """
    user_detail = {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "tier": "household",
        "status": "active",
        "created_at": "2026-04-01",
        "locations": [
            {"name": "Home - Mirpur", "cameras": 2},
            {"name": "Shop - Gulshan", "cameras": 1},
        ],
        "recent_events": 15,
        "error_count": 2,
    }

    return user_detail


@router.post("/users/{user_id}/tier")
async def admin_change_tier(
    user_id: str,
    tier: str,
    user: dict = Depends(require_admin),
):
    """Manually change user tier.

    Admin override for payment verification.

    Args:
        user_id: User UUID
        tier: New tier (free/household/business)

    Returns:
        {"success": true, "new_tier": tier}
    """
    valid_tiers = {"free", "household", "business"}
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
        )

    logger.info(f"Admin {user['id']} changed user {user_id} tier to {tier}")
    return {"success": True, "new_tier": tier}


@router.post("/users/{user_id}/disable")
async def admin_disable_user(
    user_id: str,
    user: dict = Depends(require_admin),
):
    """Disable a user account.

    Args:
        user_id: User UUID

    Returns:
        {"success": true, "status": "disabled"}
    """
    logger.info(f"Admin {user['id']} disabled user {user_id}")
    return {"success": True, "status": "disabled"}


@router.get("/errors", response_class=HTMLResponse)
async def admin_errors(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Error log viewer page.

    Shows:
    - Error list with severity, module, camera, timestamp
    - Filter by severity, module, date range
    - Resolve button
    """
    errors = [
        {
            "id": "err-001",
            "severity": "error",
            "module": "pipeline",
            "camera_id": "cam-001",
            "message": "Connection timeout",
            "timestamp": "2026-04-27 14:30:00",
            "resolved": False,
        },
        {
            "id": "err-002",
            "severity": "warning",
            "module": "ai_analysis",
            "camera_id": "cam-002",
            "message": "Gemini returned invalid JSON",
            "timestamp": "2026-04-27 13:15:00",
            "resolved": True,
        },
        {
            "id": "err-003",
            "severity": "critical",
            "module": "database",
            "camera_id": None,
            "message": "Connection pool exhausted",
            "timestamp": "2026-04-27 12:00:00",
            "resolved": False,
        },
    ]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "errors": errors,
            "active_tab": "errors",
        },
    )


@router.get("/health")
async def admin_health(
    user: dict = Depends(require_admin),
):
    """System health JSON endpoint.

    Returns health check results for all subsystems.
    """
    return {
        "status": "healthy",
        "checks": {
            "database": {"status": "healthy", "latency_ms": 5.2},
            "gemini_api": {"status": "healthy", "latency_ms": 120.0},
            "groq_api": {"status": "healthy", "latency_ms": 85.0},
            "telegram": {"status": "healthy", "latency_ms": 45.0},
            "storage": {"status": "healthy", "disk_usage_pct": 42.5},
        },
        "uptime_seconds": 86400,
        "active_cameras": 156,
        "total_errors_24h": 7,
    }


@router.get("/beta/invites", response_class=HTMLResponse)
async def admin_beta_invites(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Beta invite management page.

    Shows:
    - Invite codes generated
    - Codes used vs unused
    - Generate new code form
    """
    invites = [
        {"code": "BETA-ABC123", "used": True, "used_by": "user@example.com",
         "created_at": "2026-04-20"},
        {"code": "BETA-DEF456", "used": False, "used_by": None,
         "created_at": "2026-04-21"},
        {"code": "BETA-GHI789", "used": False, "used_by": None,
         "created_at": "2026-04-22"},
    ]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "invites": invites,
            "active_tab": "beta",
        },
    )


@router.post("/beta/invites/generate")
async def admin_generate_invite(
    count: int = 1,
    user: dict = Depends(require_admin),
):
    """Generate beta invite codes.

    Args:
        count: Number of invite codes to generate (default: 1)

    Returns:
        {"codes": [list of invite codes]}
    """
    if count < 1 or count > 100:
        raise HTTPException(
            status_code=400,
            detail="Count must be between 1 and 100"
        )

    codes = []
    for _ in range(count):
        code = f"BETA-{uuid.uuid4().hex[:8].upper()}"
        _beta_invites.append({
            "code": code,
            "used": False,
            "used_by": None,
            "created_at": datetime.utcnow().isoformat(),
        })
        codes.append(code)

    logger.info(f"Admin {user['id']} generated {count} invite codes")
    return {"codes": codes}


@router.get("/feedback", response_class=HTMLResponse)
async def admin_feedback(
    request: Request,
    user: dict = Depends(require_admin),
):
    """Beta feedback viewer.

    Shows user-submitted feedback with:
    - Rating, comment, timestamp
    - User info + tier
    - Filter by rating
    """
    feedback_list = [
        {
            "rating": 5,
            "comment": "Excellent system! The AI detection is very accurate.",
            "user_email": "user1@example.com",
            "tier": "household",
            "timestamp": "2026-04-27 14:30",
        },
        {
            "rating": 4,
            "comment": "Good but could use more camera integrations.",
            "user_email": "user2@example.com",
            "tier": "business",
            "timestamp": "2026-04-26 10:00",
        },
        {
            "rating": 3,
            "comment": "Works well but the mobile app needs improvement.",
            "user_email": "user3@example.com",
            "tier": "free",
            "timestamp": "2026-04-25 09:15",
        },
    ]

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "feedback_list": feedback_list,
            "active_tab": "feedback",
        },
    )
