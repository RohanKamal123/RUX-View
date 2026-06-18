# CONTEXT.md — Dashboard Module
# Module: backend/dashboard/
# Sprint: 1.3 (auth.py), 5.1 (server.py + templates)
# Purpose: Web dashboard + authentication

---

## What This Module Does

Two main files:

1. **auth.py** — Firebase Auth middleware (Sprint 1.3)
2. **server.py** — FastAPI app + Jinja2 templates (Sprint 5.1)

Plus templates/ and static/ directories for the web UI.

---

## File: auth.py (Sprint 1.3)

### Functions
```python
async def verify_token(token: str) -> dict | None
    # Validates Firebase ID token
    # Returns: {uid, email, tier, subscription_active} or None

async def get_current_user(authorization: str = Header(None)) -> dict
    # FastAPI dependency
    # Extracts Bearer token from Authorization header
    # Raises HTTPException 401 if invalid

def require_tier(required_tier: str):
    # Decorator for routes
    # Checks user.tier >= required_tier
    # Raises HTTPException 403 if insufficient
```

### Stack
```python
import firebase_admin
from firebase_admin import auth as firebase_auth
```

### Key Decisions
- **D012** — Firebase Auth (NOT custom auth)

---

## File: server.py (Sprint 5.1)

### Pages
- index.html — Event feed, all cameras, filter by camera
- camera.html — Per-camera event list
- person.html — Person profile (sightings timeline)
- settings.html — Camera config, ignore zones editor
- login.html — Firebase Auth flow
- query.html — NL query interface (Household/Business only)
- analytics.html — Shop analytics (Business only)

### Features
- Cookie/JWT session after Firebase verify
- Auto-refresh event feed (30s)
- Thumbnail display per event
- Threat level badges (colour coded)
- Mobile responsive

### APScheduler Jobs (registered in lifespan)
- Daily digest: cron 22:00
- Weekly digest: cron Monday 08:00
- Transcript cleanup: cron daily 03:00

### Key Decisions
- **D024** — APScheduler (NOT `schedule` library)

## Dependencies
- firebase-admin
- fastapi
- jinja2
- apscheduler

## Called By
- uvicorn (entry point)
