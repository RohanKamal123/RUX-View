# CONTEXT.md — API Module
# Module: backend/api/
# Current state: trigger/camera/user routes are active; analytics, clips, and public signup contain explicit stubs
# Purpose: REST API endpoints

---

## What This Module Does

The API package contains the active trigger, dashboard, query, camera, user,
billing, location, authentication, analytics, and clip routes. Analytics,
clip storage/playback, and public signup/reset are not production-backed.

1. **triggers.py** — Receive triggers from Vision OS Connect client
2. **dashboard.py** — Dashboard routes (event feed, stats)
3. **queries.py** — NL query endpoints
4. **cameras.py** — Camera CRUD management
5. **users.py** — User management + profile
6. **billing.py** — bKash payment endpoints
7. **locations.py** — Location CRUD
8. **analytics.py / clips.py / public_signup.py** — explicitly incomplete endpoints

---

## Endpoints

### triggers.py
```
POST /triggers/frame  → Receive JPEG + motion_result from Connect client
POST /triggers/audio  → Receive audio chunk + YAMNet classification
```

### dashboard.py
```
GET  /                → Main dashboard page (HTML)
GET  /api/events      → Event list (JSON, filterable)
GET  /api/stats       → Dashboard statistics
```

### queries.py
```
POST /queries         → Submit NL query (Household/Business only)
```

### cameras.py
```
GET  /cameras         → List user's cameras
POST /cameras         → Add camera
PUT  /cameras/{id}    → Update camera config
DELETE /cameras/{id}  → Remove camera
```

### users.py
```
GET  /users/me        → Current user info + tier
PUT  /users/me        → Update profile
```

### billing.py
```
POST /billing/subscribe     → Start subscription
POST /billing/cancel        → Cancel subscription
POST /billing/webhook       → bKash payment webhook
```

## Auth
- All routes protected with `get_current_user()` dependency
- Premium routes use `require_tier("household")` or `require_tier("business")`
- Public signup/reset is not a Firebase-backed account lifecycle.
- Event writes are created and updated through `HybridCRUD`; the pipeline does not insert a second event.

## Key Decisions
- **D005** — Trigger-only (not continuous streaming)
- **D012** — Firebase Auth (not custom auth)

## Dependencies
- backend/dashboard/auth.py
- backend/storage/database.py
- backend/core/pipeline.py (triggers)
- backend/ai/query_engine.py (queries)
- backend/billing/bkash_client.py (billing)
