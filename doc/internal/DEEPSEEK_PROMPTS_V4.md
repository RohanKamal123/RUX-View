# Vision OS V4 — DeepSeek Coding Prompts
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 6.1 — Android Viewer App (Kotlin)
### Files: android/app/src/main/java/com/visionos/app/... (multiple files)
### Tests: android/app/src/test/java/com/visionos/app/... (unit tests)

```
You are building the Android viewer app for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Kotlin + Jetpack Compose + Retrofit + Firebase Auth + FCM + Glide
- Thin client ONLY — no processing, no AI, no audio capture
- All intelligence runs on backend — this is a viewer/notification app
- Users receive push notifications for HIGH/EMERGENCY alerts
- Tap notification → opens event detail in app
- Firebase Auth for login (same as dashboard — D012)
- Mobile-first: designed for BD smartphone users (mid-range Android)

KEY DECISIONS:
- D012: Firebase Auth (NOT custom auth)
- D014: Three pricing tiers (free/household/business)
- Android only for V4 (iOS deferred to V5)

SCREENS TO BUILD:

1. LoginScreen.kt:
```kotlin
@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    auth: FirebaseAuth = FirebaseAuth.getInstance()
)
// Firebase Auth UI with Google Sign-in button
// Auto-login if token valid
// Shows app logo + tagline: "Vision OS — Your AI Security"
```

2. CameraListScreen.kt:
```kotlin
data class CameraSummary(
    val id: String,
    val name: String,
    val locationName: String,
    val mode: String,
    val status: String,  // online/offline/error
    val lastEventTime: String?,
    val unreadAlertCount: Int = 0
)

@Composable
fun CameraListScreen(
    cameras: List<CameraSummary>,
    onCameraTap: (String) -> Unit,
    onRefresh: () -> Unit
)
// Card-based list with camera name, location, status indicator
// Pull-to-refresh
// Badge for unread alerts
// Green/yellow/red status dot
```

3. EventFeedScreen.kt:
```kotlin
data class EventItem(
    val id: Int,
    val cameraName: String,
    val threatLevel: String,  // LOW/MEDIUM/HIGH/EMERGENCY
    val timestamp: String,
    val thumbnailUrl: String?,
    val description: String?,
    val durationSec: Float?,
    val personIds: List<String>?
)

@Composable
fun EventFeedScreen(
    cameraId: String?,
    events: List<EventItem>,
    onEventTap: (Int) -> Unit,
    onRefresh: () -> Unit,
    onLoadMore: () -> Unit
)
// Paginated event list (20 per page)
// Thumbnail left, details right
// Color-coded threat badges
// Pull-to-refresh + infinite scroll
// Filter by threat level (chips at top)
// Empty state: "No events. Your cameras are quiet."
```

4. EventDetailScreen.kt:
```kotlin
data class EventDetail(
    val id: Int,
    val cameraName: String,
    val cameraId: String,
    val threatLevel: String,
    val timestampStart: String,
    val timestampEnd: String?,
    val durationSec: Float?,
    val thumbnailUrl: String?,
    val description: String?,
    val gemmaAnalysis: String?,  // JSON string of vision analysis
    val geminiDecision: String?, // JSON string of incident decision
    val personIds: List<String>?,
    val audioTranscript: String?,
    val audioInterpretation: String?
)

@Composable
fun EventDetailScreen(
    eventId: Int,
    event: EventDetail?,
    onPersonTap: (String) -> Unit,
    onBack: () -> Unit
)
// Full-screen thumbnail at top
// Threat badge + timestamp
// Description section
// Person list (tappable → person profile)
// Audio transcript section (if available)
// Loading skeleton state
```

5. PersonProfileScreen.kt:
```kotlin
data class PersonProfile(
    val personUid: String,
    val firstSeen: String?,
    val lastSeen: String?,
    val sightingCount: Int,
    val threatFlags: Int,
    val isStaff: Boolean,
    val userLabel: String?,
    val camerasSeen: List<String>,
    val sightings: List<SightingItem>
)

data class SightingItem(
    val eventId: Int,
    val cameraName: String,
    val timestamp: String,
    val thumbnailUrl: String?,
    val clothingDescription: String?
)

@Composable
fun PersonProfileScreen(
    personUid: String,
    profile: PersonProfile?,
    onSightingTap: (Int) -> Unit,
    onLabelEdit: (String) -> Unit,
    onBack: () -> Unit
)
// Person header: UID, label, threat flags
// Sighting timeline (reverse chronological)
// Each sighting: thumbnail + camera + time + clothing
// Label/edit button (opens dialog)
// Tier gate: Household+ only
```

6. SettingsScreen.kt:
```kotlin
data class AppSettings(
    val notificationsEnabled: Boolean,
    val highAlertVibration: Boolean,
    val emergencyAlertSound: Boolean,
    val digestTime: String,  // "22:00"
    val theme: String  // "system" / "light" / "dark"
)

@Composable
fun SettingsScreen(
    settings: AppSettings,
    onSettingChange: (String, Any) -> Unit,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit
)
// Notification preferences
// Digest time picker
// Theme selector
// Account info section
// Logout button
// Delete account (with confirmation)
```

7. FCM Service (FirebaseMessagingService.kt):
```kotlin
class VisionOSMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        // Send token to backend
    }

    override fun onMessageReceived(message: RemoteMessage) {
        // Parse notification payload
        // Show notification with:
        //   - Title: "VisionOS HIGH - Front Gate"
        //   - Body: "Unknown person at front gate"
        //   - Tap action: open EventDetailScreen
        //   - Priority: HIGH for EMERGENCY
        //   - Notification channel: "emergency" / "alerts" / "digest"
    }
}
```

API SERVICE (Retrofit):
```kotlin
interface VisionOSApi {
    @GET("api/events")
    suspend fun getEvents(
        @Query("camera_id") cameraId: String? = null,
        @Query("threat_level") threatLevel: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("offset") offset: Int = 0
    ): List<EventItem>

    @GET("api/events/{id}")
    suspend fun getEventDetail(@Path("id") eventId: Int): EventDetail

    @GET("api/cameras")
    suspend fun getCameras(): List<CameraSummary>

    @GET("api/persons/{uid}")
    suspend fun getPersonProfile(@Path("uid") personUid: String): PersonProfile

    @PUT("api/persons/{uid}/label")
    suspend fun updatePersonLabel(
        @Path("uid") personUid: String,
        @Body label: Map<String, String>
    )

    @GET("api/settings")
    suspend fun getSettings(): AppSettings

    @PUT("api/settings")
    suspend fun updateSettings(@Body settings: AppSettings)
}
```

NAVIGATION:
```kotlin
// Jetpack Navigation with bottom nav:
// - Cameras (icon: videocam)
// - Events (icon: list)
// - Settings (icon: settings)
//
// Stack navigation from events:
// EventFeed → EventDetail → PersonProfile
```

TEST CASES TO WRITE:
```kotlin
test_login_screen_shows_google_signin_button()
test_camera_list_displays_cameras()
test_event_feed_loads_paginated()
test_event_detail_shows_thumbnail()
test_person_profile_requires_household_tier()
test_free_tier_blocked_from_person_profile()
test_fcm_notification_opens_correct_event()
test_settings_persist_locally()
test_offline_shows_cached_events()
test_pull_to_refresh_updates_feed()
```

OUTPUT: Generate all Kotlin files for the Android app: LoginScreen, CameraListScreen, EventFeedScreen, EventDetailScreen, PersonProfileScreen, SettingsScreen, FCM service, API service interface, Navigation setup, and test file. Use Jetpack Compose throughout.
```

---

## SPRINT 6.2 — Multi-Location Support
### Files: backend/core/location_manager.py, backend/api/locations.py
### Tests: backend/tests/unit/test_location_manager.py

```
You are building the multi-location management module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Users can have multiple locations (home, shop, godown)
- Each location has its own cameras, topology, and settings
- Cross-camera Re-ID NEVER crosses location boundary (HARD RULE)
- Digest generated per location, aggregated for user
- Dashboard shows unified view across all locations
- Location config includes: name, address, timezone, business hours

KEY DECISIONS:
- D014: Three pricing tiers (free=1 location, household=3, business=5)
- D026: All calls async

DATABASE TABLE (already exists):
```sql
CREATE TABLE locations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL,
  name                VARCHAR(200) NOT NULL,
  address             TEXT,
  timezone            VARCHAR(50) DEFAULT 'Asia/Dhaka',
  business_hours_open TIME,
  business_hours_close TIME,
  camera_topology     JSONB,  -- neighbour relationships
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

FUNCTIONS TO IMPLEMENT (location_manager.py):
```python
from dataclasses import dataclass, field
from datetime import date, time, datetime
from typing import Optional

@dataclass
class LocationSummary:
    id: str
    name: str
    address: Optional[str]
    timezone: str
    camera_count: int = 0
    online_cameras: int = 0
    events_today: int = 0
    high_threats_today: int = 0

@dataclass
class LocationDetail:
    id: str
    user_id: str
    name: str
    address: Optional[str]
    timezone: str
    business_hours_open: Optional[time]
    business_hours_close: Optional[time]
    camera_topology: dict = field(default_factory=dict)
    cameras: list = field(default_factory=list)
    created_at: datetime

class LocationManager:
    """Manage user locations and enforce location boundaries."""

    def __init__(self, db_session_factory):
        """Initialize location manager.
        Args:
            db_session_factory: SQLAlchemy async session factory
        """

    async def get_locations(self, user_id: str) -> list[LocationSummary]:
        """Get all locations for a user with summary stats.
        Returns: List of LocationSummary with camera counts and event stats
        """

    async def get_location(self, location_id: str, user_id: str) -> LocationDetail:
        """Get full location details including cameras.
        Returns: LocationDetail
        """

    async def create_location(self, user_id: str, name: str,
                               address: Optional[str] = None,
                               timezone: str = "Asia/Dhaka") -> LocationDetail:
        """Create a new location.
        Checks tier limit: free=1, household=3, business=5
        Returns: Created LocationDetail
        """

    async def update_location(self, location_id: str, user_id: str,
                               updates: dict) -> LocationDetail:
        """Update location properties.
        Args:
            updates: Dict with fields to update (name, address, timezone, etc.)
        Returns: Updated LocationDetail
        """

    async def delete_location(self, location_id: str, user_id: str) -> bool:
        """Delete a location and all associated data.
        Cascades: cameras, events, persons, analytics
        Returns: True if deleted
        """

    async def get_location_limit(self, tier: str) -> int:
        """Get max locations for a tier.
        free: 1, household: 3, business: 5
        """

    async def get_camera_topology(self, location_id: str) -> dict:
        """Get camera neighbour topology for a location.
        Returns: {camera_id: {neighbours: [...], min_transit_time: int}}
        """

    async def update_camera_topology(self, location_id: str,
                                      topology: dict) -> None:
        """Update camera neighbour topology.
        Validates no cycles before saving.
        """

    async def get_unified_digest(self, user_id: str,
                                  digest_date: date) -> str:
        """Generate a unified digest across all user locations.
        Aggregates per-location digests into one summary.
        Returns: Plain text digest
        """

    def _validate_topology(self, topology: dict) -> bool:
        """Validate camera topology has no cycles.
        Uses DFS cycle detection.
        Returns: True if valid
        """

    def _get_tier_location_limit(self, tier: str) -> int:
        """Get location limit by tier.
        free: 1, household: 3, business: 5
        """

    async def get_location_stats(self, location_id: str,
                                   stats_date: date) -> dict:
        """Get aggregate stats for a location on a given date.
        Returns: {events: int, high_threats: int, persons_seen: int,
                   audio_events: int, alerts_sent: int}
        """
```

API ENDPOINTS (locations.py):
```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/locations", tags=["locations"])

@router.get("/")
async def list_locations(user: dict = Depends(get_current_user)):
    """List all locations for the authenticated user."""

@router.get("/{location_id}")
async def get_location(location_id: str,
                       user: dict = Depends(get_current_user)):
    """Get location details with cameras."""

@router.post("/")
async def create_location(data: dict,
                          user: dict = Depends(get_current_user)):
    """Create a new location."""

@router.put("/{location_id}")
async def update_location(location_id: str, data: dict,
                          user: dict = Depends(get_current_user)):
    """Update location."""

@router.delete("/{location_id}")
async def delete_location(location_id: str,
                          user: dict = Depends(get_current_user)):
    """Delete location and all associated data."""

@router.get("/{location_id}/stats")
async def get_location_stats(location_id: str, date: str,
                             user: dict = Depends(get_current_user)):
    """Get location stats for a date."""

@router.put("/{location_id}/topology")
async def update_topology(location_id: str, topology: dict,
                          user: dict = Depends(get_current_user)):
    """Update camera topology for a location."""
```

TEST CASES TO WRITE (test_location_manager.py):
```python
test_create_location_within_tier_limit()
test_create_location_exceeds_tier_limit_raises_error()
test_get_locations_returns_user_locations()
test_delete_location_cascades_to_cameras()
test_cross_camera_never_crosses_location_boundary()
test_unified_digest_aggregates_all_locations()
test_topology_cycle_detection_rejects_cycles()
test_update_topology_validates_before_save()
test_free_tier_limited_to_one_location()
test_business_tier_allows_five_locations()
```

OUTPUT: Generate location_manager.py with LocationManager class, all dataclasses, topology validation, tier enforcement, and test file. Generate locations.py with all API endpoints. Use async/await throughout.
```

---

## SPRINT 6.3 — Edge Case Hardening + Error Recovery
### Files: backend/core/error_handler.py, backend/core/retry_manager.py, backend/core/health_checker.py
### Tests: backend/tests/unit/test_error_handler.py

```
You are building the error handling, retry management, and health checking modules for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + httpx
- Production hardening: handle every failure mode gracefully
- Retry with exponential backoff + jitter for transient failures
- Health check endpoint aggregates all subsystem status
- Graceful degradation: one camera failure doesn't affect others
- All errors logged with structured logging (JSON)

KEY DECISIONS:
- D026: All calls async
- Graceful degradation over crash

FUNCTIONS TO IMPLEMENT (error_handler.py):
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any
from enum import Enum

class ErrorSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    NETWORK = "network"           # Connection timeouts, DNS failures
    API = "api"                   # Gemini/Whisper API errors
    DATABASE = "database"         # Connection pool, query failures
    AUTH = "auth"                 # Token expiry, invalid credentials
    VALIDATION = "validation"     # Invalid input data
    INTERNAL = "internal"         # Unexpected bugs
    RESOURCE = "resource"         # Memory, disk, rate limits

@dataclass
class ErrorRecord:
    timestamp: datetime
    camera_id: Optional[str]
    module: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[str] = None
    context: dict = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None

class ErrorHandler:
    """Centralized error handling with structured logging."""

    def __init__(self, logger=None):
        """Initialize error handler.
        Args:
            logger: Optional structured logger instance
        """

    async def handle_error(self, camera_id: Optional[str],
                            module: str, category: ErrorCategory,
                            severity: ErrorSeverity,
                            message: str,
                            exception: Optional[Exception] = None,
                            context: Optional[dict] = None) -> ErrorRecord:
        """Handle an error with structured logging.
        Steps:
        1. Create ErrorRecord with full context
        2. Log with appropriate severity
        3. If CRITICAL: trigger alert to admin
        4. If camera-specific: mark camera as degraded
        5. Return ErrorRecord for tracking
        Returns: ErrorRecord
        """

    async def get_camera_errors(self, camera_id: str,
                                 hours_back: int = 24) -> list[ErrorRecord]:
        """Get recent errors for a specific camera."""

    async def get_unresolved_errors(self) -> list[ErrorRecord]:
        """Get all unresolved errors across all cameras."""

    async def resolve_error(self, error_id: str) -> bool:
        """Mark an error as resolved."""

    def _log_structured(self, record: ErrorRecord) -> None:
        """Log error as structured JSON."""

    def _should_alert_admin(self, severity: ErrorSeverity) -> bool:
        """Check if error severity warrants admin alert."""

    async def _alert_admin(self, record: ErrorRecord) -> None:
        """Send admin alert for critical errors."""


class RetryManager:
    """Retry with exponential backoff + jitter for transient failures."""

    def __init__(self, max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 30.0,
                 jitter: float = 0.1):
        """Initialize retry manager.
        Args:
            max_retries: Maximum retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Random jitter fraction (0.0-1.0)
        """

    async def execute(self, func: Callable, *args,
                      retryable_exceptions: tuple = None,
                      **kwargs) -> Any:
        """Execute a function with retry logic.
        Args:
            func: Async function to execute
            retryable_exceptions: Tuple of exception types to retry on
        Returns: Function result
        Raises: Last exception after max retries
        """

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff + jitter.
        delay = min(base * 2^attempt, max_delay) * (1 + random * jitter)
        """

    def _is_retryable(self, exception: Exception,
                       retryable_exceptions: tuple) -> bool:
        """Check if exception type is retryable."""


class HealthChecker:
    """Health check aggregator for all subsystems."""

    def __init__(self, db_session_factory, ai_client, groq_client,
                 telegram_client):
        """Initialize health checker."""

    async def check_all(self) -> dict:
        """Check health of all subsystems.
        Returns: {
            status: "healthy" / "degraded" / "unhealthy",
            checks: {
                database: {status, latency_ms, error},
                gemini_api: {status, latency_ms, error},
                groq_api: {status, latency_ms, error},
                telegram: {status, latency_ms, error},
                storage: {status, disk_usage_pct, error}
            },
            uptime_seconds: float,
            active_cameras: int,
            total_errors_24h: int
        }
        """

    async def check_database(self) -> dict:
        """Check database connectivity with simple query."""

    async def check_gemini_api(self) -> dict:
        """Check Gemini API with minimal test call."""

    async def check_groq_api(self) -> dict:
        """Check Groq Whisper API availability."""

    async def check_telegram(self) -> dict:
        """Check Telegram Bot API connectivity."""

    async def check_storage(self) -> dict:
        """Check disk usage for thumbnail storage."""

    def _get_status(self, checks: list[dict]) -> str:
        """Aggregate status from all checks.
        All healthy → "healthy"
        Any degraded → "degraded"
        Any unhealthy → "unhealthy"
        """
```

KNOWN EDGE CASES TO HANDLE:
```python
# Camera goes offline mid-incident
# → Pipeline should handle gracefully, close incident, log error
# → Resume normal operation when camera reconnects

# Gemini returns invalid JSON
# → Parse with fallback, log error, use default values
# → Retry once, then degrade gracefully

# Re-ID bbox outside frame bounds
# → Validate bbox before crop, return None if invalid
# → Log validation error, skip Re-ID for this frame

# Whisper returns empty transcript
# → Handle None/empty gracefully, don't pass to Gemini
# → Log as info, not error

# Cross-camera topology has cycle
# → Detect cycle on save, reject with clear error message
# → Existing topology continues working

# User deletes camera with active incident
# → Close incident immediately, save partial timeline
# → Log as info

# New user with no cameras hits dashboard
# → Show onboarding wizard, not empty error page
# → "Connect your first camera to get started"

# Trial expires during active incident
# → Complete current incident, then disable
# → Send Telegram: "Your trial has ended. Upgrade to continue."

# 500 events in buffer, more arrive
# → Drop oldest event, log warning
# → Never crash from buffer overflow

# Telegram bot rate limited
# → Queue messages, retry with backoff
# → Log rate limit warning

# Postgres connection pool exhausted
# → Wait with timeout, log critical error
# → Degrade to read-only mode if possible
```

TEST CASES TO WRITE (test_error_handler.py):
```python
test_error_record_created_with_context()
test_retry_succeeds_on_third_attempt()
test_retry_exhausts_max_attempts()
test_health_check_all_subsystems_healthy()
test_health_check_database_failure_reported()
test_camera_error_doesnt_affect_other_cameras()
test_invalid_gemini_json_handled_gracefully()
test_empty_whisper_transcript_handled()
test_topology_cycle_rejected()
test_camera_deleted_mid_incident_closes_gracefully()
```

OUTPUT: Generate error_handler.py, retry_manager.py, and health_checker.py with all classes, edge case handling, and test file. Use async/await throughout.
```

---

## SPRINT 6.4 — Beta Onboarding + Admin Dashboard
### Files: backend/dashboard/templates/admin.html, backend/dashboard/admin_routes.py, backend/dashboard/templates/onboarding.html
### Tests: backend/tests/unit/test_admin.py

```
You are building the admin dashboard and onboarding flow for Vision OS beta launch.

CONTEXT:
- Stack: FastAPI + Jinja2 templates + vanilla JS + CSS
- Admin dashboard for monitoring all users, cameras, errors
- Onboarding wizard for new users (first camera setup)
- Beta user management: invite codes, usage limits, feedback collection
- Admin routes protected by admin role check

KEY DECISIONS:
- D012: Firebase Auth (admin role via custom claims)
- D014: Three pricing tiers

FUNCTIONS TO IMPLEMENT (admin_routes.py):
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(user: dict = Depends(get_current_user)):
    """Check if user has admin role.
    Raises HTTPException(403) if not admin.
    """

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request,
                          user: dict = Depends(require_admin)):
    """Admin dashboard page.
    Shows:
    - Total users, cameras, locations
    - Active vs inactive users
    - Error rate chart (last 24h)
    - System health status
    - Recent signups
    """

@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request,
                      user: dict = Depends(require_admin)):
    """User management page.
    Shows all users with:
    - Email, tier, camera count, last active
    - Status (active/trial/expired/disabled)
    - Actions: upgrade, downgrade, disable
    """

@router.get("/users/{user_id}")
async def admin_user_detail(user_id: str,
                            user: dict = Depends(require_admin)):
    """User detail page.
    Shows:
    - User profile + subscription info
    - All locations + cameras
    - Recent events
    - Error logs
    - Manual tier change form
    """

@router.post("/users/{user_id}/tier")
async def admin_change_tier(user_id: str, tier: str,
                            user: dict = Depends(require_admin)):
    """Manually change user tier.
    Admin override for payment verification.
    """

@router.post("/users/{user_id}/disable")
async def admin_disable_user(user_id: str,
                             user: dict = Depends(require_admin)):
    """Disable a user account."""

@router.get("/errors", response_class=HTMLResponse)
async def admin_errors(request: Request,
                       user: dict = Depends(require_admin)):
    """Error log viewer page.
    Shows:
    - Error list with severity, module, camera, timestamp
    - Filter by severity, module, date range
    - Resolve button
    """

@router.get("/health")
async def admin_health(user: dict = Depends(require_admin)):
    """System health JSON endpoint.
    Returns health check results for all subsystems.
    """

@router.get("/beta/invites", response_class=HTMLResponse)
async def admin_beta_invites(request: Request,
                             user: dict = Depends(require_admin)):
    """Beta invite management page.
    Shows:
    - Invite codes generated
    - Codes used vs unused
    - Generate new code form
    """

@router.post("/beta/invites/generate")
async def admin_generate_invite(count: int = 1,
                                user: dict = Depends(require_admin)):
    """Generate beta invite codes.
    Returns: List of invite codes
    """

@router.get("/feedback", response_class=HTMLResponse)
async def admin_feedback(request: Request,
                         user: dict = Depends(require_admin)):
    """Beta feedback viewer.
    Shows user-submitted feedback with:
    - Rating, comment, timestamp
    - User info + tier
    - Filter by rating
    """
```

ONBOARDING FLOW (onboarding.html):
```html
{% extends "base.html" %}
{% block title %}Welcome to Vision OS{% endblock %}
{% block content %}
<div class="onboarding-container">
  <div class="onboarding-step" id="step-1">
    <h2>Welcome to Vision OS</h2>
    <p>Your AI-powered security intelligence platform.</p>
    <p>Let's get your first camera connected in 3 steps.</p>
    <button onclick="nextStep(2)">Get Started</button>
  </div>

  <div class="onboarding-step" id="step-2" style="display:none">
    <h2>Step 1: Name Your Location</h2>
    <p>Where is this camera located?</p>
    <input type="text" id="location-name" placeholder="e.g. Home - Mirpur" />
    <input type="text" id="location-address" placeholder="Address (optional)" />
    <button onclick="saveLocation()">Next</button>
  </div>

  <div class="onboarding-step" id="step-3" style="display:none">
    <h2>Step 2: Download Vision OS Connect</h2>
    <p>Install the client agent on your Windows PC to connect your cameras.</p>
    <div class="download-section">
      <a href="/download/connect.exe" class="download-btn">Download for Windows</a>
      <p class="hint">Or scan the QR code to download on another device</p>
      <div id="qr-code"></div>
    </div>
    <button onclick="nextStep(4)">I've installed it. Next →</button>
  </div>

  <div class="onboarding-step" id="step-4" style="display:none">
    <h2>Step 3: Connect Your Camera</h2>
    <p>Open Vision OS Connect and enter:</p>
    <div class="api-key-display">
      <label>Your API Key:</label>
      <code id="api-key">{{ api_key }}</code>
      <button onclick="copyApiKey()">Copy</button>
    </div>
    <ol class="instructions">
      <li>Open Vision OS Connect on your PC</li>
      <li>Paste the API key above</li>
      <li>Enter your camera's RTSP URL</li>
      <li>Name your camera and select its mode</li>
      <li>Click Connect</li>
    </ol>
    <button onclick="checkConnection()">Check Connection</button>
    <div id="connection-status"></div>
  </div>

  <div class="onboarding-step" id="step-5" style="display:none">
    <h2>You're All Set!</h2>
    <p>Your first camera is connected and Vision OS is watching.</p>
    <p>You'll receive your first alert when motion is detected.</p>
    <div class="next-steps">
      <h3>What's Next?</h3>
      <ul>
        <li>📹 <a href="/">View your event feed</a></li>
        <li>⚙️ <a href="/settings">Add more cameras</a></li>
        <li>💳 <a href="/payment">Upgrade your plan</a></li>
      </ul>
    </div>
    <button onclick="finishOnboarding()">Go to Dashboard</button>
  </div>
</div>

<script>
let currentStep = 1;

function nextStep(step) {
  document.getElementById(`step-${currentStep}`).style.display = 'none';
  document.getElementById(`step-${step}`).style.display = 'block';
  currentStep = step;
}

async function saveLocation() {
  const name = document.getElementById('location-name').value;
  if (!name) { alert('Please enter a location name'); return; }
  await fetch('/api/locations', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, address: document.getElementById('location-address').value})
  });
  nextStep(3);
}

function copyApiKey() {
  navigator.clipboard.writeText(document.getElementById('api-key').textContent);
}

async function checkConnection() {
  const status = document.getElementById('connection-status');
  status.innerHTML = '<div class="loading-skeleton">Checking...</div>';
  // Poll for first event
  let attempts = 0;
  const check = setInterval(async () => {
    attempts++;
    const res = await fetch('/api/events?limit=1');
    const events = await res.json();
    if (events.length > 0) {
      clearInterval(check);
      status.innerHTML = '<div class="success">✅ Camera connected! First event received.</div>';
      setTimeout(() => nextStep(5), 1500);
    } else if (attempts > 12) {
      clearInterval(check);
      status.innerHTML = '<div class="warning">⏳ Still waiting... Make sure your camera is configured correctly.</div>';
    }
  }, 5000);
}

function finishOnboarding() {
  window.location.href = '/';
}
</script>
{% endblock %}
```

ADMIN TEMPLATE (admin.html):
```html
{% extends "base.html" %}
{% block title %}Admin Dashboard{% endblock %}
{% block content %}
<div class="admin-dashboard">
  <div class="admin-header">
    <h2>Admin Dashboard</h2>
    <nav class="admin-nav">
      <a href="/admin" class="{% if active_tab == 'overview' %}active{% endif %}">Overview</a>
      <a href="/admin/users" class="{% if active_tab == 'users' %}active{% endif %}">Users</a>
      <a href="/admin/errors" class="{% if active_tab == 'errors' %}active{% endif %}">Errors</a>
      <a href="/admin/beta/invites" class="{% if active_tab == 'beta' %}active{% endif %}">Beta</a>
      <a href="/admin/feedback" class="{% if active_tab == 'feedback' %}active{% endif %}">Feedback</a>
    </nav>
  </div>

  <div class="admin-stats-grid">
    <div class="stat-card">
      <h3>Total Users</h3>
      <p class="stat-number">{{ stats.total_users }}</p>
    </div>
    <div class="stat-card">
      <h3>Active Cameras</h3>
      <p class="stat-number">{{ stats.active_cameras }}</p>
    </div>
    <div class="stat-card">
      <h3>Errors (24h)</h3>
      <p class="stat-number error-count">{{ stats.errors_24h }}</p>
    </div>
    <div class="stat-card">
      <h3>System Health</h3>
      <p class="stat-status {{ stats.health_status }}">{{ stats.health_status }}</p>
    </div>
  </div>

  <div class="admin-section">
    <h3>Recent Signups</h3>
    <table class="admin-table">
      <thead>
        <tr>
          <th>Email</th>
          <th>Tier</th>
          <th>Cameras</th>
          <th>Signed Up</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {% for user in recent_users %}
        <tr>
          <td><a href="/admin/users/{{ user.id }}">{{ user.email }}</a></td>
          <td><span class="tier-badge tier-{{ user.tier }}">{{ user.tier }}</span></td>
          <td>{{ user.camera_count }}</td>
          <td>{{ user.created_at }}</td>
          <td><span class="status-{{ user.status }}">{{ user.status }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

TEST CASES TO WRITE (test_admin.py):
```python
test_admin_dashboard_requires_admin_role()
test_non_admin_gets_403()
test_admin_users_lists_all_users()
test_admin_change_tier_updates_user()
test_admin_disable_user_prevents_login()
test_admin_health_endpoint_returns_json()
test_beta_invite_generation_creates_codes()
test_beta_invite_code_used_once()
test_onboarding_wizard_shows_for_new_users()
test_feedback_submission_and_viewing()
```

OUTPUT: Generate admin_routes.py with all admin endpoints, admin.html template with stats grid and user table, onboarding.html with 5-step wizard, and test file. Use async/await throughout. Plain text only (NO markdown).
```

---

## Quick Reference: V4 File Paths

| Sprint | File Path |
|--------|-----------|
| 6.1 | `android/app/src/main/java/com/visionos/app/LoginScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/CameraListScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/EventFeedScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/EventDetailScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/PersonProfileScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/SettingsScreen.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/VisionOSMessagingService.kt` |
| 6.1 | `android/app/src/main/java/com/visionos/app/VisionOSApi.kt` |
| 6.1 | `android/app/src/test/java/com/visionos/app/TestApp.kt` |
| 6.2 | `backend/core/location_manager.py` |
| 6.2 | `backend/api/locations.py` |
| 6.2 | `backend/tests/unit/test_location_manager.py` |
| 6.3 | `backend/core/error_handler.py` |
| 6.3 | `backend/core/retry_manager.py` |
| 6.3 | `backend/core/health_checker.py` |
| 6.3 | `backend/tests/unit/test_error_handler.py` |
| 6.4 | `backend/dashboard/admin_routes.py` |
| 6.4 | `backend/dashboard/templates/admin.html` |
| 6.4 | `backend/dashboard/templates/onboarding.html` |
| 6.4 | `backend/tests/unit/test_admin.py` |

---

*Vision OS V4 — DeepSeek Coding Prompts*

*Copy, paste, generate, test, commit. Repeat.*
