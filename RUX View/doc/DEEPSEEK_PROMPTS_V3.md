# Vision OS V3 — DeepSeek Coding Prompts
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

## SPRINT 4.1 — Audio Intelligence (Audio-Visual Correlation)
### Files: backend/core/audio_correlation.py, backend/core/audio_only_incident.py
### Tests: backend/tests/unit/test_audio_intelligence.py

```
You are building the audio intelligence module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Audio triggers arrive from client agent (YAMNet classified)
- Audio-visual correlation: match audio triggers to open visual incidents within ±15s window
- Audio-only incidents: when sound is detected but no visual incident is open
- Groq Whisper-compatible API (whisper-large-v3-turbo) for Bangla transcription
- Gemini 2.0 Flash interprets the transcript for threat assessment
- Transcripts stored only 1-3 days (privacy — D020)

KEY DECISIONS:
- D003: Groq Whisper-compatible API for Bangla transcription (NOT OpenAI Whisper)
- D005: Trigger-only (not continuous streaming)
- D020: Whisper transcript stored only 1-3 days
- D026: All calls async

FUNCTIONS TO IMPLEMENT (audio_correlation.py):
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class AudioVisualMatch:
    matched: bool
    incident_id: Optional[str] = None
    camera_id: Optional[str] = None
    time_gap_seconds: Optional[float] = None
    correlation_type: str = "none"  # "visual_open" / "neighbour_visual" / "audio_only"

@dataclass
class AudioIncidentResult:
    incident_id: str
    threat_level: str  # LOW/MEDIUM/HIGH
    transcript: Optional[str] = None
    interpretation: Optional[str] = None
    has_visual_match: bool = False
    matched_camera_id: Optional[str] = None

class AudioCorrelator:
    """Correlate audio triggers with visual incidents."""

    def __init__(self, db_session_factory, ai_client):
        """Initialize audio correlator.
        Args:
            db_session_factory: SQLAlchemy async session factory
            ai_client: AI client for Gemini interpretation
        """

    async def correlate(self, camera_id: str, location_id: str,
                         timestamp: datetime,
                         yamnet_result: dict) -> AudioVisualMatch:
        """Check if audio trigger correlates with an open visual incident.
        Steps:
        1. Query open incidents on same camera within ±10s window
        2. If no match, query neighbour cameras within ±15s window
        3. If no match, return audio_only
        Returns: AudioVisualMatch with correlation result
        """

    async def process_audio_trigger(self, camera_id: str, location_id: str,
                                      user_id: str, timestamp: datetime,
                                      audio_bytes: Optional[bytes],
                                      yamnet_result: dict) -> AudioIncidentResult:
        """Process an audio trigger end-to-end.
        Steps:
        1. Correlate with visual incidents
        2. If speech detected AND (after hours OR HIGH threat): transcribe via Groq
        3. If transcript available: interpret via Gemini
        4. Save audio_event to database
        5. Return AudioIncidentResult
        Returns: AudioIncidentResult
        """

    async def _transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe audio using Groq Whisper-compatible API.
        Returns: Bangla transcript text or None if failed
        """

    async def _interpret_transcript(self, transcript: str,
                                      yamnet_result: dict,
                                      visual_context: Optional[dict]) -> str:
        """Interpret transcript using Gemini 2.0 Flash.
        Returns: English interpretation string
        """

    def _should_transcribe(self, yamnet_result: dict,
                            is_after_hours: bool) -> bool:
        """Check if audio should be transcribed based on YAMNet class + time.
        Transcribe if:
        - Speech detected AND confidence > 0.8
        - Any HIGH threat sound (glass breaking, gunshot, scream)
        - After hours AND any sound > 0.7 confidence
        """

    def _get_neighbour_cameras(self, camera_id: str,
                                topology: dict) -> list[str]:
        """Get neighbouring cameras from topology config."""
```

FUNCTIONS TO IMPLEMENT (audio_only_incident.py):
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class AudioOnlyIncident:
    incident_id: str
    camera_id: str
    location_id: str
    timestamp: datetime
    yamnet_class: str
    yamnet_confidence: float
    transcript: Optional[str] = None
    interpretation: Optional[str] = None
    threat_level: str = "MEDIUM"
    alert_sent: bool = False

class AudioOnlyHandler:
    """Handle audio triggers that have NO visual match."""

    def __init__(self, db_session_factory, alert_router):
        """Initialize audio-only handler.
        Args:
            db_session_factory: SQLAlchemy async session factory
            alert_router: AlertRouter instance for sending alerts
        """

    async def handle_audio_only(self, camera_id: str, location_id: str,
                                 user_id: str, timestamp: datetime,
                                 yamnet_result: dict,
                                 transcript: Optional[str] = None,
                                 interpretation: Optional[str] = None) -> AudioOnlyIncident:
        """Handle an audio trigger with no visual match.
        Steps:
        1. Create audio-only incident
        2. If threat is HIGH or EMERGENCY: route alert immediately
        3. If speech detected: flag as "Sound detected, no visual — possible blind spot"
        4. Save to database
        Returns: AudioOnlyIncident
        """

    async def check_blind_spot_pattern(self, camera_id: str,
                                        location_id: str,
                                        hours_back: int = 24) -> dict:
        """Check if a camera has recurring audio-only incidents.
        Pattern: 3+ audio-only incidents in same area within 24h
        Returns: {pattern_detected: bool, count: int, suggestion: str}
        """

    def _get_threat_from_yamnet(self, yamnet_result: dict) -> str:
        """Map YAMNet class to threat level.
        glass_breaking/gunshot/scream → HIGH
        shout/vehicle_alarm → MEDIUM
        speech/footsteps/engine → LOW
        """
```

TEST CASES TO WRITE (test_audio_intelligence.py):
```python
test_audio_correlates_with_open_visual_incident()
test_audio_correlates_with_neighbour_camera()
test_audio_only_when_no_visual_match()
test_groq_transcription_called_for_speech()
test_gemini_interpretation_of_transcript()
test_should_transcribe_after_hours()
test_should_not_transcribe_low_confidence()
test_blind_spot_pattern_detected()
test_audio_only_high_threat_routes_alert()
test_yamnet_threat_mapping()
```

OUTPUT: Generate audio_correlation.py and audio_only_incident.py with all classes, dataclasses, correlation logic, and test file. Use async/await throughout. Reference Groq (not OpenAI Whisper) for transcription.
```

---

## SPRINT 4.2 — Shop Analytics Mode
### File: backend/analytics/shop_analytics.py
### Tests: backend/tests/unit/test_shop_analytics.py

```
You are building the shop analytics module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Business tier only feature
- Tracks customer entries, demographics, peak hours, dwell time
- Staff filtered out via Re-ID (staff profiles) or staff entrance zone
- CRM tracking: time-based frequency analysis for repeat customers
- Data stored in shop_analytics table (hourly buckets)

KEY DECISIONS:
- D008: Five separate modes (shop mode is one of them)
- D014: Shop analytics exclusive to Business tier
- D026: All calls async

DATABASE TABLE (already exists):
```sql
CREATE TABLE shop_analytics (
  id                  SERIAL PRIMARY KEY,
  camera_id           VARCHAR(100),
  user_id             UUID NOT NULL,
  date                DATE NOT NULL,
  hour                INTEGER,
  customer_count      INTEGER DEFAULT 0,
  male_count          INTEGER DEFAULT 0,
  female_count        INTEGER DEFAULT 0,
  unknown_gender      INTEGER DEFAULT 0,
  age_teens           INTEGER DEFAULT 0,
  age_20s             INTEGER DEFAULT 0,
  age_30s             INTEGER DEFAULT 0,
  age_40s             INTEGER DEFAULT 0,
  age_50plus          INTEGER DEFAULT 0,
  avg_dwell_seconds   FLOAT,
  UNIQUE(camera_id, date, hour)
);
```

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

@dataclass
class CustomerEntry:
    person_uid: str
    camera_id: str
    timestamp: datetime
    gender: str  # male/female/unknown
    age_group: str  # teen/20s/30s/40s/50s+/unknown
    is_staff: bool = False
    dwell_seconds: Optional[float] = None
    visit_count_today: int = 1

@dataclass
class HourlyAnalytics:
    camera_id: str
    date: date
    hour: int
    customer_count: int = 0
    male_count: int = 0
    female_count: int = 0
    unknown_gender: int = 0
    age_teens: int = 0
    age_20s: int = 0
    age_30s: int = 0
    age_40s: int = 0
    age_50plus: int = 0
    avg_dwell_seconds: float = 0.0

@dataclass
class DailySummary:
    camera_id: str
    date: date
    total_customers: int = 0
    unique_customers: int = 0
    staff_count: int = 0
    gender_breakdown: dict = None
    age_breakdown: dict = None
    peak_hour: Optional[int] = None
    avg_dwell_seconds: float = 0.0
    repeat_customers: int = 0

class ShopAnalytics:
    """Shop analytics aggregation and reporting."""

    def __init__(self, db_session_factory):
        """Initialize shop analytics.
        Args:
            db_session_factory: SQLAlchemy async session factory
        """

    async def record_entry(self, camera_id: str, user_id: str,
                            timestamp: datetime,
                            gemma_result: dict,
                            person_uid: Optional[str] = None,
                            is_staff: bool = False) -> CustomerEntry:
        """Record a customer entry event.
        Steps:
        1. Extract gender + age from gemma_result
        2. Check if person is staff (Re-ID match or staff entrance)
        3. Upsert hourly analytics bucket
        4. Track repeat visits today
        Returns: CustomerEntry
        """

    async def record_exit(self, person_uid: str, camera_id: str,
                           entry_timestamp: datetime,
                           exit_timestamp: datetime) -> None:
        """Record customer exit to calculate dwell time.
        Updates avg_dwell_seconds for the relevant hour bucket.
        """

    async def get_hourly_breakdown(self, camera_id: str,
                                    analytics_date: date) -> list[HourlyAnalytics]:
        """Get hourly breakdown for a camera on a specific date.
        Returns: List of HourlyAnalytics (24 entries, 0-23)
        """

    async def get_daily_summary(self, camera_id: str,
                                 analytics_date: date) -> DailySummary:
        """Get daily summary for a camera.
        Returns: DailySummary with totals, breakdowns, peak hour
        """

    async def get_peak_hours(self, camera_id: str,
                              analytics_date: date) -> list[dict]:
        """Get peak hours sorted by customer count descending.
        Returns: [{hour: 10, count: 15}, {hour: 11, count: 12}, ...]
        """

    async def get_demographic_breakdown(self, camera_id: str,
                                         analytics_date: date) -> dict:
        """Get demographic breakdown.
        Returns: {gender: {male: 45, female: 30, unknown: 5},
                   age: {teens: 5, 20s: 30, 30s: 25, 40s: 15, 50plus: 5}}
        """

    async def get_repeat_customers(self, camera_id: str,
                                    analytics_date: date,
                                    min_visits: int = 2) -> list[dict]:
        """Get customers who visited multiple times today.
        CRM tracking: identifies repeat visitors.
        Returns: [{person_uid, visit_count, first_seen, last_seen, gender, age_group}]
        """

    async def get_weekly_report(self, camera_id: str,
                                 week_start: date) -> dict:
        """Get weekly analytics report.
        Returns: {total_customers, avg_daily, busiest_day, peak_hour,
                   gender_avg, age_avg, repeat_rate}
        """

    def _is_staff(self, person_uid: str, entrance_zone: str,
                   staff_ids: list[str],
                   staff_entrance_zones: list[str]) -> bool:
        """Check if person is staff based on Re-ID or entrance zone."""

    def _calculate_dwell(self, entry: datetime, exit: datetime) -> float:
        """Calculate dwell time in seconds. Minimum 30s to count."""
```

TEST CASES TO WRITE (test_shop_analytics.py):
```python
test_record_entry_upserts_hourly_bucket()
test_staff_not_counted_as_customer()
test_demographic_breakdown_totals()
test_peak_hours_sorted_descending()
test_daily_summary_aggregation()
test_repeat_customer_detection()
test_weekly_report_generation()
test_dwell_time_calculation()
test_get_hourly_breakdown_returns_24_entries()
test_crm_tracking_visit_count()
```

OUTPUT: Generate shop_analytics.py with ShopAnalytics class, all dataclasses, aggregation logic, and test file. Use async/await throughout.
```

---

## SPRINT 4.3 — Digest Generator
### Files: backend/analytics/digest_generator.py, backend/analytics/report_builder.py
### Tests: backend/tests/unit/test_digest_generator.py

```
You are building the digest generator for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + APScheduler (AsyncIOScheduler) + SQLAlchemy async
- Three tier variants: free (simple), household (detailed), business (detailed + analytics)
- Daily digest sent at 22:00 user local time
- Weekly digest sent Monday 08:00
- Plain text format (NO markdown — timestamp underscores break markdown)
- Free tier: max 200 words
- APScheduler handles cron scheduling (D024)

KEY DECISIONS:
- D014: Free tier gets digest (conversion hook)
- D024: APScheduler (NOT `schedule` library) — async-native
- D026: All calls async

FUNCTIONS TO IMPLEMENT (digest_generator.py):
```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

@dataclass
class DigestData:
    user_id: str
    location_id: str
    date: date
    tier: str  # free/household/business
    events_summary: dict = None
    person_stats: dict = None
    audio_summary: dict = None
    anomalies: list = None
    shop_data: Optional[dict] = None

class DigestGenerator:
    """Generate daily and weekly security digests."""

    def __init__(self, db_session_factory, ai_client, telegram_client):
        """Initialize digest generator.
        Args:
            db_session_factory: SQLAlchemy async session factory
            ai_client: AI client for Gemini digest generation
            telegram_client: TelegramClient for sending digests
        """

    async def generate_daily_digest(self, user_id: str,
                                     location_id: str,
                                     digest_date: date) -> str:
        """Generate daily digest for a user's location.
        Steps:
        1. Query events for the day
        2. Query person sightings
        3. Query audio events
        4. Query shop analytics (if business tier)
        5. Call Gemini to generate digest text
        6. Return formatted digest string
        Returns: Plain text digest (max 200 words for free tier)
        """

    async def generate_weekly_digest(self, user_id: str,
                                      location_id: str,
                                      week_start: date) -> str:
        """Generate weekly digest.
        Same as daily but aggregates 7 days of data.
        Returns: Plain text weekly digest
        """

    async def send_daily_digests(self) -> int:
        """Send daily digests to ALL users.
        Called by APScheduler cron job at 22:00.
        Steps:
        1. Query all users with active subscriptions
        2. For each user, get their locations
        3. Generate digest per location
        4. Send via Telegram
        Returns: Number of digests sent
        """

    async def send_weekly_digests(self) -> int:
        """Send weekly digests to ALL users.
        Called by APScheduler cron job Monday 08:00.
        Returns: Number of digests sent
        """

    def _format_free_digest(self, events_summary: dict,
                             person_stats: dict) -> str:
        """Format free tier digest (max 200 words).
        Template:
        VisionOS Daily - {date}
        {camera}: {count} events, {high_count} HIGH
        Visitors: {total} ({familiar} familiar, {unknown} unknown)
        Audio: {audio_count} alerts
        All clear today.
        """

    def _format_household_digest(self, events_summary: dict,
                                  person_stats: dict,
                                  audio_summary: dict) -> str:
        """Format household tier digest (detailed).
        Template:
        VisionOS Daily Summary - {date}
        [Location: {name}]

        Security: {total} events total
          HIGH: {high}  MEDIUM: {medium}  LOW: {low}
        Visitors: {total_visitors} ({familiar} familiar, {unknown} unknown)
        {person_uid} seen {count}x - flagged
        Audio: {audio_count} events ({top_class} {time})
        Gate status: {gate_status}
        """

    def _format_business_digest(self, events_summary: dict,
                                 person_stats: dict,
                                 audio_summary: dict,
                                 shop_data: dict) -> str:
        """Format business tier digest (detailed + analytics).
        Includes shop analytics section.
        """

    def _get_tier_limit(self, tier: str) -> int:
        """Get word limit for tier.
        free: 200, household: 500, business: 1000
        """
```

FUNCTIONS TO IMPLEMENT (report_builder.py):
```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

@dataclass
class BusinessReport:
    location_name: str
    week_start: date
    week_end: date
    total_events: int = 0
    high_threat_events: int = 0
    unique_persons: int = 0
    repeat_offenders: list = None
    audio_events: int = 0
    shop_analytics: Optional[dict] = None
    recommendations: list = None

class ReportBuilder:
    """Build business-tier detailed reports."""

    def __init__(self, db_session_factory, ai_client):
        """Initialize report builder."""

    async def build_weekly_report(self, user_id: str,
                                   location_id: str,
                                   week_start: date) -> BusinessReport:
        """Build a comprehensive weekly business report.
        Returns: BusinessReport with all sections
        """

    async def _get_recommendations(self, report: BusinessReport) -> list[str]:
        """Generate security recommendations based on report data.
        Uses Gemini to analyse patterns and suggest improvements.
        """

    def format_report_text(self, report: BusinessReport) -> str:
        """Format report as plain text for Telegram.
        NO markdown formatting.
        """
```

TEST CASES TO WRITE (test_digest_generator.py):
```python
test_free_digest_under_200_words()
test_household_digest_includes_person_stats()
test_business_digest_includes_analytics()
test_digest_sends_to_telegram()
test_weekly_digest_aggregates_7_days()
test_format_free_digest_template()
test_format_household_digest_template()
test_format_business_digest_template()
test_report_builder_weekly_report()
test_tier_word_limits()
```

OUTPUT: Generate digest_generator.py and report_builder.py with all classes, formatting logic, and test file. Use async/await throughout. Plain text only (NO markdown).
```

---

## SPRINT 5.1 — Dashboard Core (UI/UX Design)
### Files: backend/dashboard/server.py, backend/dashboard/templates/base.html, index.html, camera.html, person.html, settings.html, backend/dashboard/static/app.js, style.css
### Tests: backend/tests/unit/test_dashboard.py

```
You are building the web dashboard for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + Jinja2 templates + vanilla JS + CSS
- Mobile-first responsive design (users check on phone)
- Firebase Auth for login (D012)
- All pages require authentication
- Premium pages gated by tier
- Auto-refresh event feed every 30s
- Color-coded threat badges
- Clean, modern UI — professional security dashboard feel

KEY DECISIONS:
- D012: Firebase Auth (NOT custom auth)
- D014: Three pricing tiers (free/household/business)
- D026: All calls async

UI/UX DESIGN GUIDELINES:
- Color palette: Dark navy (#0f172a) sidebar, white (#ffffff) content area
- Threat colors: LOW = green (#22c55e), MEDIUM = yellow (#eab308), HIGH = orange (#f97316), EMERGENCY = red (#ef4444)
- Font: system-ui, -apple-system, sans-serif
- Mobile-first: sidebar collapses to hamburger on < 768px
- Cards for events (not tables) — thumbnail left, details right
- Smooth transitions, subtle shadows, rounded corners (8px)
- Loading skeleton states (not spinners)
- Empty states with helpful messages

FUNCTIONS TO IMPLEMENT (server.py):
```python
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

app = FastAPI(title="Vision OS Dashboard")

# Mount static files
app.mount("/static", StaticFiles(directory="backend/dashboard/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="backend/dashboard/templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: dict = Depends(get_current_user)):
    """Main event feed page.
    Shows all events across all user's cameras.
    Filterable by camera, threat level, date range.
    Auto-refreshes every 30s via JS.
    """

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page with Firebase Auth UI."""

@app.get("/camera/{camera_id}", response_class=HTMLResponse)
async def camera_page(request: Request, camera_id: str,
                       user: dict = Depends(get_current_user)):
    """Per-camera event list page.
    Shows events for a single camera.
    """

@app.get("/person/{person_uid}", response_class=HTMLResponse)
async def person_page(request: Request, person_uid: str,
                       user: dict = Depends(get_current_user)):
    """Person profile page.
    Shows sightings timeline, appearance history, threat flags.
    Requires household tier or above.
    """

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request,
                         user: dict = Depends(get_current_user)):
    """Settings page.
    Camera config, ignore zones, account settings.
    """

@app.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request,
                        user: dict = Depends(get_current_user)):
    """Payment info page.
    Shows bKash/Nagad number for manual payment.
    """

@app.get("/api/events")
async def api_events(camera_id: Optional[str] = None,
                      threat_level: Optional[str] = None,
                      limit: int = 50,
                      user: dict = Depends(get_current_user)):
    """JSON endpoint for event feed auto-refresh."""

@app.get("/api/person/{person_uid}/sightings")
async def api_person_sightings(person_uid: str,
                                user: dict = Depends(get_current_user)):
    """JSON endpoint for person sightings timeline."""
```

TEMPLATES TO CREATE:

base.html:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vision OS — {% block title %}Dashboard{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
  {% block head %}{% endblock %}
</head>
<body>
  <!-- Sidebar navigation -->
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <h1 class="logo">Vision OS</h1>
      <button class="sidebar-toggle" onclick="toggleSidebar()">☰</button>
    </div>
    <ul class="nav-links">
      <li><a href="/" class="nav-link {% if active_page == 'index' %}active{% endif %}">📹 Events</a></li>
      <li><a href="/settings" class="nav-link {% if active_page == 'settings' %}active{% endif %}">⚙️ Settings</a></li>
      <li><a href="/payment" class="nav-link {% if active_page == 'payment' %}active{% endif %}">💳 Payment</a></li>
    </ul>
    <div class="sidebar-footer">
      <span class="tier-badge tier-{{ user.tier }}">{{ user.tier }}</span>
      <button onclick="logout()" class="logout-btn">Logout</button>
    </div>
  </nav>

  <!-- Main content -->
  <main class="content" id="content">
    {% block content %}{% endblock %}
  </main>

  <script src="/static/app.js"></script>
</body>
</html>
```

index.html:
```html
{% extends "base.html" %}
{% block title %}Event Feed{% endblock %}
{% block content %}
<div class="page-header">
  <h2>Event Feed</h2>
  <div class="filters">
    <select id="camera-filter" onchange="applyFilters()">
      <option value="">All Cameras</option>
      {% for cam in cameras %}
      <option value="{{ cam.id }}">{{ cam.name }}</option>
      {% endfor %}
    </select>
    <select id="threat-filter" onchange="applyFilters()">
      <option value="">All Threats</option>
      <option value="EMERGENCY">Emergency</option>
      <option value="HIGH">High</option>
      <option value="MEDIUM">Medium</option>
      <option value="LOW">Low</option>
    </select>
  </div>
</div>

<div class="event-feed" id="event-feed">
  {% for event in events %}
  <div class="event-card threat-{{ event.threat_level.lower() }}">
    <div class="event-thumbnail">
      <img src="{{ event.thumbnail_url or '/static/placeholder.jpg' }}" alt="Event thumbnail">
    </div>
    <div class="event-details">
      <div class="event-header">
        <span class="threat-badge {{ event.threat_level.lower() }}">{{ event.threat_level }}</span>
        <span class="event-camera">{{ event.camera_name }}</span>
        <span class="event-time">{{ event.timestamp_start.strftime('%H:%M:%S') }}</span>
      </div>
      <p class="event-description">{{ event.alert_message or 'Motion detected' }}</p>
      <div class="event-meta">
        <span>Duration: {{ event.duration_sec }}s</span>
        {% if event.person_ids %}
        <span>Persons: {{ event.person_ids|join(', ') }}</span>
        {% endif %}
      </div>
    </div>
  </div>
  {% else %}
  <div class="empty-state">
    <p>No events yet. Your cameras are quiet.</p>
    <p>When motion is detected, events will appear here.</p>
  </div>
  {% endfor %}
</div>
{% endblock %}
```

camera.html — Per-camera event list with camera name, mode badge, event cards filtered to that camera.

person.html — Person profile with sightings timeline, appearance history cards, threat flag indicator, label/edit button.

settings.html — Camera list with edit buttons, add camera form, account settings section, ignore zones editor (placeholder).

STATIC FILES:

style.css — Complete responsive CSS with:
- CSS custom properties for colors
- Dark sidebar, light content layout
- Event cards with thumbnail + details
- Threat badges (colored dots/pills)
- Filter bar styling
- Mobile responsive (sidebar collapse, stacked cards)
- Loading skeleton animation
- Empty state styling
- Form inputs, buttons, selects styled
- Smooth transitions

app.js — Frontend JavaScript with:
- toggleSidebar() — hamburger menu for mobile
- applyFilters() — filter events by camera/threat
- autoRefresh() — fetch /api/events every 30s, update feed
- logout() — Firebase sign out + redirect
- Firebase Auth UI initialization
- Event card click → navigate to detail

TEST CASES TO WRITE (test_dashboard.py):
```python
test_dashboard_requires_auth()
test_event_feed_returns_correct_user_events()
test_camera_page_shows_filtered_events()
test_person_page_requires_household_tier()
test_free_tier_blocked_from_person_page()
test_settings_page_loads()
test_payment_page_shows_info()
test_api_events_json_endpoint()
test_api_person_sightings_json()
test_empty_state_shown_when_no_events()
```

OUTPUT: Generate server.py with all routes, all 6 HTML templates (base, index, camera, person, settings, payment), style.css, and app.js. Mobile-first responsive design. Use async/await throughout. Include test file.
```

---

## SPRINT 5.2 — NL Query Engine
### File: backend/ai/query_engine.py
### Tests: backend/tests/unit/test_query_engine.py

```
You are building the natural language query engine for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + Gemini 2.0 Flash
- Users type questions in natural language about their security events
- Query flow: NL → intent parsing → SQL filter → fetch events → Gemini synthesis → answer
- Household/Business tier only (D014)
- Queries can search appearance, objects, behaviour, scene state, cross-camera, timeline

KEY DECISIONS:
- D001: Gemini 2.0 Flash unified (handles both intent parsing + answer synthesis)
- D014: NL Queries exclusive to Household/Business tier
- D026: All calls async

QUERY TYPES:
```
APPEARANCE: "who wore red shirts today?"
OBJECT: "what was person 7 holding?"
SCENE_STATE: "are all gates locked?"
BEHAVIOUR: "did anyone run today?"
CROSS_CAMERA: "track person 7 across all cameras"
TIMELINE: "what happened while I was away 2pm to 6pm?"
```

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
from enum import Enum

class QueryIntent(Enum):
    APPEARANCE = "appearance"
    OBJECT = "object"
    SCENE_STATE = "scene_state"
    BEHAVIOUR = "behaviour"
    CROSS_CAMERA = "cross_camera"
    TIMELINE = "timeline"
    UNKNOWN = "unknown"

@dataclass
class ParsedQuery:
    intent: QueryIntent
    original_question: str
    filters: dict = None  # SQL WHERE clause params
    person_uid: Optional[str] = None
    time_range: Optional[dict] = None  # {start, end} or "today"
    cameras: Optional[list[str]] = None

@dataclass
class QueryResult:
    answer: str
    matching_events: list[dict] = None
    thumbnails: list[str] = None
    error: Optional[str] = None

class QueryEngine:
    """Natural language query engine for security events."""

    def __init__(self, db_session_factory, ai_client):
        """Initialize query engine.
        Args:
            db_session_factory: SQLAlchemy async session factory
            ai_client: AI client for Gemini intent parsing + answer synthesis
        """

    async def process_query(self, question: str, user_id: str,
                             tier: str,
                             cameras: Optional[list[str]] = None,
                             time_range: Optional[str] = None) -> QueryResult:
        """Process a natural language query end-to-end.
        Steps:
        1. Parse intent with Gemini
        2. Build SQL filters from parsed intent
        3. Fetch matching events from database
        4. Retrieve stored vision analysis JSON for matches
        5. If not stored, re-analyse thumbnail via Gemini
        6. Synthesise final answer with Gemini
        7. Return QueryResult with answer + thumbnails
        Returns: QueryResult
        """

    async def _parse_intent(self, question: str) -> ParsedQuery:
        """Parse user question to extract intent + filters.
        Uses Gemini 2.0 Flash to classify and extract parameters.
        Returns: ParsedQuery with intent and filter params
        """

    async def _build_sql_filter(self, parsed: ParsedQuery,
                                 user_id: str) -> dict:
        """Build SQL filter dict from parsed query.
        Maps intent to appropriate table columns and conditions.
        Returns: {where_clauses: list, joins: list, order: str, limit: int}
        """

    async def _fetch_matching_events(self, sql_filter: dict) -> list[dict]:
        """Fetch matching events from database using SQL filter.
        Returns: List of event dicts with id, timestamp, camera_id, thumbnail_url
        """

    async def _get_vision_analyses(self, events: list[dict]) -> list[dict]:
        """Get stored vision analysis JSON for matching events.
        If not stored, re-analyse thumbnail via Gemini.
        Returns: List of analysis dicts
        """

    async def _synthesise_answer(self, question: str,
                                   events: list[dict],
                                   analyses: list[dict]) -> str:
        """Synthesise final answer using Gemini 2.0 Flash.
        Returns: Plain text answer with person IDs and timestamps
        """

    def _get_query_prompt(self, parsed: ParsedQuery) -> str:
        """Get the appropriate Gemini prompt template for the query intent."""

    def _build_appearance_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for appearance queries (clothing, colors, accessories)."""

    def _build_object_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for object-in-hand queries."""

    def _build_behaviour_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for behaviour queries (running, climbing, etc)."""

    def _build_scene_state_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for scene state queries (gates, doors, vehicles)."""

    def _build_cross_camera_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for cross-camera person tracking queries."""

    def _build_timeline_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for timeline queries (time range)."""
```

TEST CASES TO WRITE (test_query_engine.py):
```python
test_appearance_query_finds_red_shirt()
test_object_query_finds_phone()
test_behaviour_query_finds_running()
test_scene_state_query_returns_gate_status()
test_cross_camera_query_tracks_person()
test_timeline_query_returns_ordered_events()
test_free_tier_blocked_from_queries()
test_unknown_intent_returns_helpful_message()
test_empty_results_returns_no_match_message()
test_parse_intent_correctly_classifies()
```

OUTPUT: Generate query_engine.py with QueryEngine class, all helper functions, intent parsing, SQL building, and test file. Use async/await throughout.
```

---

## SPRINT 5.3 — Manual Payment Info
### File: backend/billing/payment_info.py
### Tests: backend/tests/unit/test_payment_info.py

```
You are building the payment info module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Pure Python dataclasses + JSON config
- NO bKash API integration — just display payment info
- Users manually send money to a bKash/Nagad number
- Admin verifies payment manually and upgrades tier
- Payment info page shows: number, instructions, pricing table
- Simple, transparent, no webhooks

KEY DECISIONS:
- D011: bKash for billing (but manual, not API)
- D014: Three pricing tiers

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class PaymentMethod:
    provider: str  # "bKash" / "Nagad"
    number: str
    account_holder: str

@dataclass
class PricingTier:
    name: str  # free / household / business
    price_bdt: float
    price_usd: float
    cameras: str
    features: list[str]

@dataclass
class PaymentInfo:
    methods: list[PaymentMethod]
    tiers: list[PricingTier]
    instructions: str
    admin_contact: str  # phone number for verification

class PaymentConfig:
    """Payment configuration and info provider."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize payment config.
        Args:
            config_path: Path to JSON config file (optional)
        """

    def get_payment_info(self) -> PaymentInfo:
        """Get all payment information.
        Returns: PaymentInfo with methods, tiers, instructions
        """

    def get_tiers(self) -> list[PricingTier]:
        """Get pricing tiers.
        Returns: List of PricingTier with features
        """

    def get_methods(self) -> list[PaymentMethod]:
        """Get available payment methods.
        Returns: List of PaymentMethod (bKash, Nagad)
        """

    def get_instructions(self) -> str:
        """Get payment instructions text.
        Template:
        To upgrade your Vision OS subscription:
        1. Send {price} BDT to {provider} number: {number}
        2. Send a screenshot to {admin_contact} via WhatsApp
        3. Your tier will be upgraded within 24 hours
        """

    def load_from_file(self, config_path: str) -> None:
        """Load payment config from JSON file."""

    def save_to_file(self, config_path: str) -> None:
        """Save payment config to JSON file."""

# Default configuration
DEFAULT_PAYMENT_INFO = PaymentInfo(
    methods=[
        PaymentMethod(provider="bKash", number="017XXXXXXXX", account_holder="Vision OS"),
        PaymentMethod(provider="Nagad", number="017XXXXXXXX", account_holder="Vision OS"),
    ],
    tiers=[
        PricingTier(
            name="free",
            price_bdt=0,
            price_usd=0,
            cameras="1-2",
            features=["7 day history", "Indoor only", "Telegram alerts (20/day cap)", "Daily digest"]
        ),
        PricingTier(
            name="household",
            price_bdt=299,
            price_usd=2.72,
            cameras="1-5",
            features=["30 day history", "All modes", "Unlimited Telegram", "Re-ID", "Cross-camera", "Ghost detection", "NL Queries", "Emergency voice notes"]
        ),
        PricingTier(
            name="business",
            price_bdt=499,
            price_usd=4.54,
            cameras="1-5",
            features=["90 day history", "All modes + Shop analytics", "Unlimited Telegram", "Re-ID + Staff filter", "Cross-camera + Ghost", "NL Queries", "Emergency voice notes", "SMS fallback", "Weekly reports"]
        ),
    ],
    instructions="To upgrade your Vision OS subscription:\n1. Send the amount to the bKash or Nagad number above\n2. Send a screenshot to the admin contact via WhatsApp\n3. Your tier will be upgraded within 24 hours",
    admin_contact="017XXXXXXXX"
)
```

TEST CASES TO WRITE (test_payment_info.py):
```python
test_get_payment_info_returns_methods()
test_get_tiers_returns_three_tiers()
test_free_tier_price_is_zero()
test_household_tier_price_is_299()
test_business_tier_price_is_499()
test_get_instructions_contains_number()
test_load_from_file()
test_save_to_file()
test_default_config_has_bkash_and_nagad()
test_tier_features_are_correct()
```

OUTPUT: Generate payment_info.py with PaymentConfig class, all dataclasses, default configuration, and test file.
```

---

## SPRINT 5.4 — Data Retention + Cleanup
### File: backend/storage/cleanup.py
### Tests: backend/tests/unit/test_cleanup.py

```
You are building the data retention and cleanup module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + APScheduler
- Retention periods by tier: Free = 7 days, Household = 30 days, Business = 90 days
- Audio transcripts deleted after 1-3 days (privacy — D020)
- Thumbnails deleted with events
- Runs daily at 03:00 via APScheduler cron job
- Logs all deletions for audit

KEY DECISIONS:
- D020: Whisper transcript stored only 1-3 days
- D024: APScheduler (NOT `schedule` library)
- D026: All calls async

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

@dataclass
class CleanupResult:
    events_deleted: int = 0
    transcripts_deleted: int = 0
    thumbnails_deleted: int = 0
    persons_merged: int = 0
    errors: list[str] = None

class DataCleanup:
    """Data retention and cleanup jobs."""

    def __init__(self, db_session_factory, storage_path: str = "./storage"):
        """Initialize data cleanup.
        Args:
            db_session_factory: SQLAlchemy async session factory
            storage_path: Path to thumbnail storage directory
        """

    async def run_daily_cleanup(self) -> CleanupResult:
        """Run all cleanup jobs.
        Called by APScheduler cron job at 03:00 daily.
        Steps:
        1. Delete expired events by tier
        2. Delete expired transcripts (1-3 days)
        3. Delete orphaned thumbnails
        4. Log all deletions
        Returns: CleanupResult with counts
        """

    async def delete_expired_events(self) -> int:
        """Delete events older than retention period for each tier.
        Free: 7 days
        Household: 30 days
        Business: 90 days
        Returns: Number of events deleted
        """

    async def delete_expired_transcripts(self, retention_days: int = 3) -> int:
        """Delete audio transcripts older than retention period.
        Args:
            retention_days: Days to keep transcripts (default 3)
        Returns: Number of transcripts deleted
        """

    async def delete_orphaned_thumbnails(self) -> int:
        """Delete thumbnail files not referenced by any event.
        Returns: Number of files deleted
        """

    async def get_retention_period(self, tier: str) -> int:
        """Get retention period in days for a tier.
        free: 7, household: 30, business: 90
        """

    def _get_cutoff_date(self, days: int) -> datetime:
        """Get cutoff datetime for retention period."""

    async def log_cleanup(self, result: CleanupResult) -> None:
        """Log cleanup results to audit table.
        Creates cleanup_log entry with timestamp and counts.
        """

    async def estimate_cleanup(self) -> dict:
        """Estimate how many records would be deleted without actually deleting.
        Returns: {events: count, transcripts: count, thumbnails: count}
        Useful for dashboard display: "Next cleanup will remove X old events"
        """

    async def cleanup_single_user(self, user_id: str) -> CleanupResult:
        """Run cleanup for a single user (useful for manual trigger).
        Returns: CleanupResult for that user
        """
```

TEST CASES TO WRITE (test_cleanup.py):
```python
test_free_events_deleted_after_7_days()
test_household_events_kept_30_days()
test_business_events_kept_90_days()
test_transcripts_deleted_after_3_days()
test_cleanup_doesnt_delete_wrong_user()
test_orphaned_thumbnails_deleted()
test_estimate_cleanup_returns_counts()
test_cleanup_logs_results()
test_retention_period_by_tier()
test_cleanup_single_user()
```

OUTPUT: Generate cleanup.py with DataCleanup class, all retention logic, APScheduler integration, and test file. Use async/await throughout.
```

---

## Quick Reference: V3 File Paths

| Sprint | File Path |
|--------|-----------|
| 4.1 | `backend/core/audio_correlation.py` |
| 4.1 | `backend/core/audio_only_incident.py` |
| 4.1 | `backend/tests/unit/test_audio_intelligence.py` |
| 4.2 | `backend/analytics/shop_analytics.py` |
| 4.2 | `backend/tests/unit/test_shop_analytics.py` |
| 4.3 | `backend/analytics/digest_generator.py` |
| 4.3 | `backend/analytics/report_builder.py` |
| 4.3 | `backend/tests/unit/test_digest_generator.py` |
| 5.1 | `backend/dashboard/server.py` |
| 5.1 | `backend/dashboard/templates/base.html` |
| 5.1 | `backend/dashboard/templates/index.html` |
| 5.1 | `backend/dashboard/templates/camera.html` |
| 5.1 | `backend/dashboard/templates/person.html` |
| 5.1 | `backend/dashboard/templates/settings.html` |
| 5.1 | `backend/dashboard/templates/payment.html` |
| 5.1 | `backend/dashboard/static/style.css` |
| 5.1 | `backend/dashboard/static/app.js` |
| 5.1 | `backend/tests/unit/test_dashboard.py` |
| 5.2 | `backend/ai/query_engine.py` |
| 5.2 | `backend/tests/unit/test_query_engine.py` |
| 5.3 | `backend/billing/payment_info.py` |
| 5.3 | `backend/tests/unit/test_payment_info.py` |
| 5.4 | `backend/storage/cleanup.py` |
| 5.4 | `backend/tests/unit/test_cleanup.py` |

---

*Vision OS V3 — DeepSeek Coding Prompts*

*Copy, paste, generate, test, commit. Repeat.*


