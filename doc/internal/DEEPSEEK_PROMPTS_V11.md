# Vision OS V11 — DeepSeek Coding Prompts
# MEGA.nz Integration — Replace PostgreSQL with MEGA.nz as Backend Storage
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

## SPRINT 11.1 — MEGA.nz API Client
### Files: backend/storage/mega_client.py, backend/storage/mega_schema.py
### Tests: backend/tests/unit/test_mega_client.py

```
You are building a MEGA.nz API client for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. This replaces PostgreSQL with MEGA.nz as the backend storage layer.

CONTEXT:
- Stack: Python asyncio + mega.py (MEGA SDK) + asyncio.to_thread
- All data stored as JSON files in a structured MEGA.nz folder
- Authentication: MEGA email + password (or API key if provided)
- Folder structure:
  Vision OS Data/
  ├── users/
  │   └── {user_id}.json
  ├── cameras/
  │   └── {user_id}/
  │       └── {camera_id}.json
  ├── events/
  │   └── {user_id}/
  │       └── {YYYY-MM-DD}/
  │           └── {event_id}.json
  ├── billing/
  │   └── {user_id}.json
  ├── audit/
  │   └── audit_log.csv
  └── analytics/
      └── daily_summary.json
- Rate limiting: MEGA has bandwidth limits (~10GB/day free), not API call limits
- Retry logic: exponential backoff (1s, 2s, 4s, 8s) for connection errors
- File caching: in-memory LRU cache for frequently accessed files (TTL: 60 seconds)
- All calls async using asyncio.to_thread for MEGA API calls (which are synchronous)
- MEGA free tier: 20GB storage (sufficient for JSON data)

KEY DECISIONS:
- D026: All calls async
- Email/password authentication (stored in .env file)
- JSON files for structured data (human-readable)
- CSV for audit log (append-only, easy to analyze)
- LRU cache to reduce API calls and stay within bandwidth limits

FUNCTIONS TO IMPLEMENT:

1. MegaClient class:
   - __init__(email: str, password: str, root_folder_name: str = "Vision OS Data")
   - authenticate() -> bool
   - get_or_create_root_folder() -> str  # returns node handle
   - get_or_create_subfolder(parent_handle: str, folder_name: str) -> str
   - read_json(file_path: str) -> Optional[dict]
   - write_json(file_path: str, data: dict) -> str  # returns file handle
   - append_to_csv(file_path: str, row: list) -> str
   - read_csv(file_path: str) -> list[list]
   - list_files(folder_path: str) -> list[FileInfo]
   - delete_file(file_path: str) -> bool
   - file_exists(file_path: str) -> bool
   - get_file_url(file_path: str) -> str  # returns download URL
   - batch_read(file_paths: list[str]) -> dict[str, Optional[dict]]
   - batch_write(files: dict[str, dict]) -> dict[str, str]

2. FileInfo dataclass:
   - node_handle: str
   - name: str
   - path: str
   - mime_type: str
   - size_bytes: int
   - created_at: datetime
   - modified_at: datetime
   - download_url: Optional[str]

3. MegaCache class (internal LRU cache):
   - __init__(max_size: int = 100, ttl_seconds: int = 60)
   - get(key: str) -> Optional[Any]
   - set(key: str, value: Any) -> None
   - invalidate(key: str) -> None
   - clear() -> None
   - get_stats() -> CacheStats

4. CacheStats dataclass:
   - current_size: int
   - max_size: int
   - hits: int
   - misses: int
   - hit_ratio: float

5. MegaError classes:
   - MegaError(Exception) — base
   - AuthenticationError(MegaError) — auth failed
   - StorageLimitError(MegaError) — bandwidth/storage exceeded
   - FileNotFoundError(MegaError) — file doesn't exist
   - WriteError(MegaError) — write failed

6. Retry decorator:
   - @retry_on_error(max_retries: int = 4, base_delay: float = 1.0)
   - Handles connection errors with exponential backoff + jitter

7. PathBuilder utility:
   - user_path(user_id: str) -> str
   - camera_path(user_id: str, camera_id: str) -> str
   - event_path(user_id: str, date: str, event_id: str) -> str
   - billing_path(user_id: str) -> str
   - audit_path() -> str
   - analytics_path() -> str
   - daily_events_folder(user_id: str, date: str) -> str

TEST CASES:
test_authenticate_returns_true, test_get_or_create_root_folder_creates_if_not_exists, test_get_or_create_root_folder_returns_existing, test_get_or_create_subfolder_creates, test_write_json_creates_file, test_read_json_returns_data, test_read_json_file_not_found_returns_none, test_append_to_csv_creates_file, test_append_to_csv_appends_row, test_read_csv_returns_all_rows, test_list_files_returns_file_list, test_delete_file_removes_file, test_file_exists_returns_true, test_file_exists_returns_false, test_get_file_url_returns_link, test_batch_read_returns_all_results, test_batch_write_writes_all_files, test_cache_get_returns_cached_value, test_cache_set_stores_value, test_cache_invalidate_removes_entry, test_cache_hit_ratio_tracks_correctly, test_retry_on_error_retries_on_failure, test_retry_on_error_gives_up_after_max_retries, test_path_builder_returns_correct_paths

OUTPUT: Generate mega_client.py, mega_schema.py, and test_mega_client.py. Use async/await throughout. Include proper error handling and logging. Use mega.py library for MEGA API calls wrapped in asyncio.to_thread.
```

---

## SPRINT 11.2 — MEGA.nz CRUD Operations
### Files: backend/storage/mega_crud.py
### Tests: backend/tests/unit/test_mega_crud.py

```
You are building the CRUD (Create, Read, Update, Delete) operations layer for Vision OS using MEGA.nz as the backend storage. This replaces the SQLAlchemy database.py and crud.py.

CONTEXT:
- Stack: Python asyncio + MegaClient from mega_client.py
- All data stored as JSON files in MEGA.nz (see folder structure in Sprint 11.1)
- No SQL, no ORM — just JSON read/write operations
- Each "table" is a folder, each "row" is a JSON file
- Atomic operations: read-modify-write pattern with optimistic locking
- Indexing: in-memory index for fast lookups (rebuilt on startup)
- Supports 20 cameras per user, 100+ users
- All functions are async

KEY DECISIONS:
- D026: All calls async
- JSON files instead of database rows
- In-memory index for fast lookups (rebuilt from MEGA on startup)
- Optimistic locking via modified_at timestamp comparison

FUNCTIONS TO IMPLEMENT:

1. UserCRUD class:
   - create_user(user_id: str, email: str, name: str, tier: str = "free") -> User
   - get_user(user_id: str) -> Optional[User]
   - update_user(user_id: str, updates: dict) -> User
   - delete_user(user_id: str) -> bool
   - list_users(limit: int = 100, offset: int = 0) -> list[User]
   - get_user_by_email(email: str) -> Optional[User]
   - count_users() -> int
   - count_users_by_tier() -> dict[str, int]

2. CameraCRUD class:
   - create_camera(user_id: str, name: str, rtsp_url: str, mode: str = "indoor") -> Camera
   - get_camera(camera_id: str) -> Optional[Camera]
   - get_user_cameras(user_id: str) -> list[Camera]
   - update_camera(camera_id: str, updates: dict) -> Camera
   - delete_camera(camera_id: str) -> bool
   - count_user_cameras(user_id: str) -> int
   - get_camera_quota(user_id: str) -> QuotaInfo
   - bulk_create_cameras(user_id: str, cameras: list[dict]) -> list[Camera]
   - bulk_delete_cameras(camera_ids: list[str]) -> int

3. EventCRUD class:
   - create_event(user_id: str, camera_id: str, event_type: str, details: dict) -> Event
   - get_event(event_id: str) -> Optional[Event]
   - get_user_events(user_id: str, limit: int = 50, offset: int = 0) -> list[Event]
   - get_camera_events(camera_id: str, limit: int = 50) -> list[Event]
   - get_events_by_date(user_id: str, date: str) -> list[Event]
   - search_events(user_id: str, query: str) -> list[Event]
   - count_events(user_id: str, since: datetime = None) -> int
   - delete_old_events(before: datetime) -> int  # for data retention

4. BillingCRUD class:
   - create_payment_record(user_id: str, amount: float, method: str, status: str) -> PaymentRecord
   - get_user_payments(user_id: str, limit: int = 50) -> list[PaymentRecord]
   - update_payment_status(payment_id: str, status: str) -> PaymentRecord
   - get_revenue_by_month(year: int, month: int) -> float
   - get_total_revenue() -> float

5. AuditCRUD class:
   - append_audit_entry(entry: AuditEntry) -> bool
   - get_audit_logs(filters: AuditFilter) -> list[AuditEntry]
   - count_audit_entries(since: datetime = None) -> int

6. Data Models (dataclasses):
   - User: user_id, email, name, tier, created_at, updated_at, is_active, telegram_chat_id
   - Camera: camera_id, user_id, name, rtsp_url, mode, is_active, created_at, last_seen_at
   - Event: event_id, user_id, camera_id, event_type, confidence, details, thumbnail_url, created_at
   - PaymentRecord: payment_id, user_id, amount, currency, method, status, transaction_id, created_at
   - QuotaInfo: total_cameras, max_cameras, remaining, usage_percentage, tier
   - AuditEntry: timestamp, action, actor_id, resource_type, resource_id, details
   - AuditFilter: action, actor_id, resource_type, start_date, end_date, limit, offset

7. IndexManager class:
   - rebuild_index() -> dict  # rebuilds in-memory index from MEGA
   - get_index_stats() -> IndexStats
   - search_users(query: str) -> list[str]  # returns user_ids matching query
   - search_cameras(user_id: str, query: str) -> list[str]

8. IndexStats dataclass:
   - total_users: int
   - total_cameras: int
   - total_events: int
   - index_build_time_ms: float
   - last_rebuilt_at: datetime

TEST CASES:
test_create_user_stores_json_in_mega, test_get_user_returns_correct_data, test_update_user_modifies_json, test_delete_user_removes_json, test_list_users_returns_paginated, test_get_user_by_email_finds_user, test_count_users_returns_correct_number, test_create_camera_stores_in_user_folder, test_get_user_cameras_returns_list, test_update_camera_modifies_config, test_delete_camera_removes_file, test_count_user_cameras_returns_count, test_get_camera_quota_returns_quota_info, test_bulk_create_cameras_creates_all, test_create_event_stores_in_date_folder, test_get_user_events_returns_ordered, test_get_events_by_date_filters_correctly, test_search_events_returns_matching, test_delete_old_events_removes_expired, test_create_payment_record_stores, test_get_revenue_by_month_calculates, test_append_audit_entry_appends_to_csv, test_get_audit_logs_filters_correctly, test_rebuild_index_loads_all_data, test_index_search_returns_results

OUTPUT: Generate mega_crud.py and test_mega_crud.py. Use async/await throughout. All data models as Python dataclasses. Import MegaClient from mega_client.py.
```

---

## SPRINT 11.3 — Simplified API Layer (MEGA-Backed)
### Files: backend/api/cameras.py, backend/api/users.py, backend/api/triggers.py, backend/api/queries.py
### Tests: backend/tests/unit/test_api_mega.py

```
You are rewriting the Vision OS API layer to use MEGA.nz as the backend storage instead of SQLAlchemy. This replaces the existing API stubs.

CONTEXT:
- Stack: FastAPI + Python asyncio + MegaCRUD from mega_crud.py
- All data stored as JSON files in MEGA.nz
- Firebase Auth for authentication (unchanged)
- Same API endpoints, different backend implementation
- Rate limiting: 100 requests/min per IP (from security_middleware.py)
- Supports 20 cameras per user
- All endpoints return proper HTTP status codes and error messages

KEY DECISIONS:
- D012: Firebase Auth for authentication
- D026: All calls async
- Same API contract as before — frontend doesn't change
- Error responses consistent: {"error": "message", "code": "ERROR_CODE"}

FUNCTIONS TO IMPLEMENT:

1. Camera Endpoints (in cameras.py):
   - POST /api/cameras — Create camera (enforces 20 limit)
   - GET /api/cameras — List user's cameras
   - GET /api/cameras/{camera_id} — Get camera details
   - PUT /api/cameras/{camera_id} — Update camera
   - DELETE /api/cameras/{camera_id} — Delete camera
   - POST /api/cameras/bulk — Bulk create cameras
   - GET /api/cameras/quota — Get camera quota info
   - GET /api/cameras/{camera_id}/events — Get camera events

2. User Endpoints (in users.py):
   - GET /api/users/me — Get current user profile
   - PUT /api/users/me — Update profile
   - DELETE /api/users/me — Delete account (GDPR)
   - GET /api/users/me/stats — Get user statistics
   - POST /api/users/me/telegram — Connect Telegram

3. Trigger Endpoints (in triggers.py):
   - POST /api/triggers/frame — Receive frame trigger from client agent
   - POST /api/triggers/audio — Receive audio trigger from client agent
   - GET /api/triggers/recent — Get recent triggers

4. Query Endpoints (in queries.py):
   - POST /api/queries/natural — Natural language query
   - GET /api/queries/history — Get query history

5. Health Endpoint (in server.py):
   - GET /health — Returns {"status": "ok", "storage": "mega", "timestamp": "..."}

6. Error handling:
   - All endpoints wrapped in try/except
   - MegaError → 500 with error details
   - Firebase Auth errors → 401
   - Validation errors → 422
   - Not found → 404
   - Rate limit → 429

7. Request/Response models (Pydantic):
   - CameraCreate: name, rtsp_url, mode
   - CameraUpdate: name, mode, is_active
   - CameraResponse: all camera fields
   - UserUpdate: name, telegram_chat_id
   - UserResponse: all user fields
   - TriggerFrame: camera_id, image_base64, timestamp
   - TriggerAudio: camera_id, audio_base64, timestamp
   - QueryRequest: query, camera_id (optional)
   - QueryResponse: answer, events_found, confidence
   - ErrorResponse: error, code, details (optional)

TEST CASES:
test_create_camera_endpoint_returns_201, test_create_camera_enforces_20_limit, test_list_cameras_returns_user_cameras, test_get_camera_returns_details, test_update_camera_modifies_config, test_delete_camera_removes_it, test_bulk_create_cameras_creates_multiple, test_get_camera_quota_returns_info, test_get_user_profile_returns_data, test_update_user_profile_modifies, test_delete_user_account_removes_data, test_get_user_stats_returns_counts, test_connect_telegram_updates_chat_id, test_trigger_frame_creates_event, test_trigger_audio_creates_event, test_get_recent_triggers_returns_list, test_natural_query_returns_answer, test_health_endpoint_returns_ok, test_unauthenticated_request_returns_401, test_not_found_returns_404, test_rate_limit_exceeded_returns_429

OUTPUT: Generate cameras.py, users.py, triggers.py, queries.py, and test_api_mega.py. Use async/await throughout. Include proper Pydantic models and Firebase Auth dependency. Import MegaCRUD from mega_crud.py.
```

---

## SPRINT 11.4 — Simplified Dashboard (MEGA-Backed)
### Files: backend/dashboard/server.py, backend/dashboard/routes.py, backend/dashboard/templates/dashboard.html, backend/dashboard/templates/index.html
### Tests: backend/tests/unit/test_dashboard_mega.py

```
You are rewriting the Vision OS dashboard to use MEGA.nz as the backend storage. The dashboard reads real data from MEGA JSON files instead of mock data.

CONTEXT:
- Stack: FastAPI + Jinja2 + MegaCRUD + Firebase Auth
- Dashboard shows: camera list, recent events, user stats, billing info
- All data comes from MEGA.nz via MegaCRUD
- Templates use Jinja2 with dark navy theme
- Real-time updates via polling (every 5 seconds)
- Supports 20 cameras per user

KEY DECISIONS:
- D026: All calls async
- Dashboard reads from MEGA on every page load (no caching for real-time feel)
- Templates remain the same — only backend data source changes

FUNCTIONS TO IMPLEMENT:

1. Dashboard Routes (in routes.py):
   - GET / — Landing page (public)
   - GET /dashboard — Main dashboard (auth required)
   - GET /dashboard/cameras — Camera management page
   - GET /dashboard/events — Event feed page
   - GET /dashboard/settings — User settings page
   - GET /dashboard/billing — Billing & subscription page
   - GET /dashboard/admin — Admin panel (admin only)

2. Dashboard Data (for /dashboard):
   - Total cameras count
   - Recent events (last 10)
   - Camera online/offline status
   - Storage usage (MEGA quota)
   - Subscription info
   - Quick stats: events today, alerts sent, cameras online

3. Landing Page (index.html):
   - Hero section: "AI-Powered CCTV Intelligence for Bangladesh"
   - Features section: 6 feature cards
   - Pricing section: Free, Household (299 BDT), Business (499 BDT)
   - CTA: "Get Started Free"
   - Footer with links to privacy, terms, help

4. Dashboard Page (dashboard.html):
   - Top navbar with user info + logout
   - Sidebar with navigation
   - Stats cards row (cameras, events, alerts, storage)
   - Camera grid (shows live status)
   - Recent events feed
   - Quick actions: Add Camera, View All Events

5. Server setup (server.py):
   - Create FastAPI app
   - Add all middleware (CORS, rate limiting, security headers)
   - Mount static files
   - Include all routers
   - Startup event: initialize MegaClient + rebuild index
   - Shutdown event: cleanup

TEST CASES:
test_landing_page_returns_200, test_dashboard_requires_auth, test_dashboard_shows_camera_count, test_dashboard_shows_recent_events, test_camera_page_lists_cameras, test_events_page_shows_event_feed, test_settings_page_loads, test_billing_page_shows_subscription, test_admin_page_requires_admin, test_server_startup_initializes_mega, test_static_files_are_served

OUTPUT: Generate server.py, routes.py, dashboard.html, index.html, and test_dashboard_mega.py. Use async/await throughout. Dark navy theme matching existing design. Import MegaCRUD from mega_crud.py.
```

---

## SPRINT 11.5 — MEGA.nz Backup & Data Export
### Files: backend/storage/mega_backup.py, backend/api/data_export.py
### Tests: backend/tests/unit/test_mega_backup.py

```
You are building the backup and data export system for Vision OS using MEGA.nz as the storage backend.

CONTEXT:
- Stack: Python asyncio + MegaClient + zipfile + io
- Backups: copy entire Vision OS Data folder to a backup folder in MEGA
- Backup schedule: daily (automatic), on-demand (manual)
- Backup retention: keep last 7 daily backups
- Data export: GDPR-compliant ZIP export of a single user's data
- Export includes: profile, cameras, events, billing history
- Export format: JSON files in a ZIP archive
- All operations async

KEY DECISIONS:
- D026: All calls async
- Backups stored in same MEGA account (separate folder)
- Data export creates ZIP in memory, returns download URL

FUNCTIONS TO IMPLEMENT:

1. MegaBackup class:
   - create_backup() -> BackupResult
   - list_backups(limit: int = 10) -> list[BackupRecord]
   - restore_backup(backup_id: str) -> RestoreResult
   - delete_old_backups(retention_days: int = 7) -> int
   - get_backup_stats() -> BackupStats
   - schedule_daily_backup() -> None  # uses asyncio

2. BackupResult dataclass:
   - backup_id: str
   - status: str (success/failed)
   - total_files: int
   - total_size_bytes: int
   - duration_seconds: float
   - backup_folder_handle: str
   - error: Optional[str]

3. BackupRecord dataclass:
   - backup_id: str
   - created_at: datetime
   - total_files: int
   - total_size_bytes: int
   - status: str
   - folder_handle: str

4. RestoreResult dataclass:
   - restore_id: str
   - backup_id: str
   - status: str
   - files_restored: int
   - duration_seconds: float
   - error: Optional[str]

5. BackupStats dataclass:
   - total_backups: int
   - total_size_bytes: int
   - last_backup_at: Optional[datetime]
   - last_successful_backup_at: Optional[datetime]
   - storage_used_mb: float

6. DataExportManager class:
   - request_export(user_id: str) -> ExportRequest
   - get_export_status(request_id: str) -> ExportStatus
   - execute_export(user_id: str) -> bytes  # returns ZIP as bytes
   - download_export(request_id: str) -> Optional[bytes]
   - cleanup_old_exports(days: int = 7) -> int

7. ExportRequest dataclass:
   - request_id: str
   - user_id: str
   - status: str (pending/completed/failed)
   - requested_at: datetime
   - completed_at: Optional[datetime]
   - file_size_bytes: Optional[int]
   - error: Optional[str]

8. ExportStatus dataclass:
   - request_id: str
   - status: str
   - progress_pct: float
   - message: str

9. API Endpoints:
   - POST /api/backup — Trigger manual backup (admin only)
   - GET /api/backup — List backups (admin only)
   - POST /api/backup/restore/{backup_id} — Restore from backup (admin only)
   - POST /api/export — Request data export
   - GET /api/export/{request_id}/download — Download export
   - GET /api/export/{request_id}/status — Check export status

TEST CASES:
test_create_backup_copies_all_files, test_list_backups_returns_sorted, test_restore_backup_replaces_files, test_delete_old_backups_removes_expired, test_get_backup_stats_returns_metrics, test_schedule_daily_backup_schedules_task, test_request_export_creates_request, test_execute_export_creates_zip, test_export_zip_contains_user_data, test_export_zip_contains_profile, test_export_zip_contains_cameras, test_export_zip_contains_events, test_export_zip_contains_billing, test_download_export_returns_bytes, test_cleanup_old_exports_removes_old, test_backup_api_endpoint_requires_admin, test_export_api_endpoint_requires_auth

OUTPUT: Generate mega_backup.py, data_export.py, and test_mega_backup.py. Use async/await throughout. Import MegaClient from mega_client.py.
```

---

## SPRINT 11.6 — MEGA.nz Analytics & CSV Export
### Files: backend/analytics/mega_analytics.py, backend/api/analytics.py
### Tests: backend/tests/unit/test_mega_analytics.py

```
You are building the analytics layer for Vision OS that writes aggregated data to MEGA.nz as CSV files. These CSV files can be downloaded and imported into Google Looker Studio or Google Sheets for visualization.

CONTEXT:
- Stack: Python asyncio + MegaClient + CSV/JSON
- Analytics data written to MEGA as CSV files
- Daily aggregation: runs once per day (or on-demand)
- Metrics: signups, active cameras, events, revenue, alerts
- CSV files can be downloaded from MEGA and imported into Looker Studio via Google Sheets
- All operations async

KEY DECISIONS:
- D026: All calls async
- CSV format for compatibility with BI tools
- Daily aggregation for performance (not real-time)
- On-demand refresh available
- Visualization workflow: Download CSV from MEGA → Upload to Google Sheets → Connect Looker Studio to Sheets

FUNCTIONS TO IMPLEMENT:

1. MegaAnalytics class:
   - aggregate_daily_stats(date: str = None) -> DailyStats
   - get_daily_stats(date: str) -> Optional[DailyStats]
   - get_daily_stats_range(start_date: str, end_date: str) -> list[DailyStats]
   - generate_master_csv() -> str  # generates/updates master CSV
   - get_analytics_summary() -> AnalyticsSummary
   - get_user_growth(days: int = 30) -> list[dict]
   - get_revenue_trend(days: int = 30) -> list[dict]
   - get_event_breakdown(days: int = 7) -> dict
   - get_camera_usage_stats() -> dict

2. DailyStats dataclass:
   - date: str (YYYY-MM-DD)
   - new_users: int
   - total_users: int
   - active_cameras: int
   - total_cameras: int
   - events_detected: int
   - alerts_sent: int
   - revenue_bdt: float
   - new_subscriptions: int
   - storage_used_mb: float
   - api_requests: int

3. AnalyticsSummary dataclass:
   - total_users: int
   - total_cameras: int
   - total_events: int
   - total_revenue_bdt: float
   - active_users_today: int
   - cameras_online: int
   - avg_cameras_per_user: float
   - storage_used_mb: float
   - top_tier: str

4. CSV Files Generated:
   - analytics/daily_stats.csv — All daily stats (date, new_users, total_users, active_cameras, events, revenue, etc.)
   - analytics/user_growth.csv — User growth over time
   - analytics/revenue.csv — Revenue by day
   - analytics/events_by_type.csv — Events breakdown by type
   - analytics/camera_usage.csv — Camera usage stats

5. API Endpoints:
   - GET /api/analytics/summary — Get analytics summary
   - GET /api/analytics/daily?start=&end= — Get daily stats range
   - GET /api/analytics/user-growth?days=30 — Get user growth
   - GET /api/analytics/revenue?days=30 — Get revenue trend
   - POST /api/analytics/refresh — Trigger manual aggregation (admin only)

6. Visualization Guide (in docstring):
   - Step 1: Download CSV from MEGA (via API or MEGA web interface)
   - Step 2: Open Google Sheets → File → Import → Upload CSV
   - Step 3: Open lookerstudio.google.com
   - Step 4: Create new Data Source → Google Sheets → Select the imported sheet
   - Step 5: Configure dimensions and metrics
   - Step 6: Create charts: time series, bar charts, scorecards
   - Step 7: Share dashboard with team

TEST CASES:
test_aggregate_daily_stats_computes_correctly, test_get_daily_stats_returns_data, test_get_daily_stats_range_returns_list, test_generate_master_csv_creates_file, test_get_analytics_summary_returns_all_fields, test_get_user_growth_returns_trend, test_get_revenue_trend_returns_data, test_get_event_breakdown_returns_categories, test_get_camera_usage_stats_returns_metrics, test_csv_format_is_compatible, test_analytics_summary_api_returns_data, test_refresh_analytics_requires_admin

OUTPUT: Generate mega_analytics.py, analytics.py, and test_mega_analytics.py. Use async/await throughout. Import MegaClient from mega_client.py.
```

---

## SPRINT 11.7 — Simplified Client Agent (MEGA-Backed)
### Files: connect/camera/rtsp_reader.py, connect/camera/motion_detector.py, connect/transport/trigger_sender.py
### Tests: connect/tests/test_client_mega.py

```
You are building the simplified client agent for Vision OS that sends camera triggers to the backend API (which stores them in MEGA.nz).

CONTEXT:
- Stack: Python + OpenCV + httpx + asyncio
- Client runs on Windows PC, connects to RTSP cameras
- Detects motion, captures frames, sends to backend API
- Backend stores events in MEGA.nz
- No local database — all data sent to backend
- Offline resilience: local queue buffer if backend unreachable
- Supports 20 cameras per client

KEY DECISIONS:
- D026: All calls async
- Client sends frames to backend API (which stores in MEGA)
- Local queue for offline resilience (JSON files on disk)
- Minimal dependencies: OpenCV, httpx, numpy

FUNCTIONS TO IMPLEMENT:

1. RTSPReader class:
   - __init__(rtsp_url: str, camera_id: str, reconnect_delay: int = 5)
   - connect() -> bool
   - read_frame() -> Optional[numpy.ndarray]
   - release() -> None
   - is_connected() -> bool
   - get_stream_info() -> StreamInfo

2. StreamInfo dataclass:
   - width: int
   - height: int
   - fps: float
   - codec: str
   - is_connected: bool

3. MotionDetector class:
   - __init__(threshold: float = 0.02, min_area: int = 500)
   - detect(frame: numpy.ndarray) -> MotionResult
   - set_roi(roi: tuple) -> None  # region of interest
   - reset_background() -> None
   - get_motion_mask() -> Optional[numpy.ndarray]

4. MotionResult dataclass:
   - motion_detected: bool
   - confidence: float
   - bounding_boxes: list[tuple[int, int, int, int]]
   - motion_area_pct: float

5. TriggerSender class:
   - __init__(api_base_url: str, auth_token: str)
   - send_frame_trigger(camera_id: str, image_base64: str, timestamp: float) -> TriggerResponse
   - send_audio_trigger(camera_id: str, audio_base64: str, timestamp: float) -> TriggerResponse
   - check_health() -> bool

6. TriggerResponse dataclass:
   - success: bool
   - event_id: Optional[str]
   - message: str
   - status_code: int

7. LocalBuffer class (offline resilience):
   - __init__(buffer_dir: str = "buffer")
   - enqueue(trigger: dict) -> bool
   - dequeue_all() -> list[dict]
   - count() -> int
   - flush_to_api(sender: TriggerSender) -> int  # sends all buffered, returns count sent
   - clear() -> None

8. Main loop (in main.py):
   - Load config from connect/config.py
   - Connect to all cameras
   - For each camera: read frame → detect motion → send trigger
   - Handle reconnection on failure
   - Flush buffer when backend available

TEST CASES:
test_rtsp_reader_connects_to_stream, test_rtsp_reader_reads_frame, test_rtsp_reader_reconnects_on_failure, test_rtsp_reader_get_stream_info, test_motion_detector_detects_motion, test_motion_detector_no_motion_returns_false, test_motion_detector_roi_limits_detection, test_motion_detector_reset_background, test_trigger_sender_sends_frame, test_trigger_sender_sends_audio, test_trigger_sender_checks_health, test_local_buffer_enqueues_trigger, test_local_buffer_dequeues_all, test_local_buffer_flushes_to_api, test_local_buffer_clears_after_flush, test_main_loop_connects_cameras

OUTPUT: Generate rtsp_reader.py, motion_detector.py, trigger_sender.py, and test_client_mega.py. Use async/await throughout.
```

---

## SPRINT 11.8 — Simplified Subscription & Billing (MEGA-Backed)
### Files: backend/billing/subscription_manager.py, backend/billing/payment_processor.py, backend/billing/trial_manager.py
### Tests: backend/tests/unit/test_billing_mega.py

```
You are building the subscription and billing system for Vision OS using MEGA.nz as the backend storage.

CONTEXT:
- Stack: Python asyncio + MegaCRUD + httpx (for bKash/Nagad API)
- Subscription tiers: Free (20 cameras, 30 days), Household (299 BDT/cam/month), Business (499 BDT/cam/month)
- Payment methods: bKash, Nagad (Bangladesh)
- All data stored in MEGA.nz JSON files
- Trial management: 30-day free trial, auto-expire
- Usage tracking: camera count, event count, storage used

KEY DECISIONS:
- D026: All calls async
- Payment records stored in MEGA billing folder
- Trial expiration checked on login (not cron-based)
- bKash/Nagad API calls via httpx

FUNCTIONS TO IMPLEMENT:

1. SubscriptionManager class:
   - get_plan(tier: str) -> SubscriptionPlan
   - get_user_subscription(user_id: str) -> UserSubscription
   - create_subscription(user_id: str, tier: str, payment_method: str) -> UserSubscription
   - upgrade_subscription(user_id: str, new_tier: str) -> UserSubscription
   - downgrade_subscription(user_id: str, new_tier: str) -> UserSubscription
   - cancel_subscription(user_id: str) -> UserSubscription
   - get_available_plans() -> list[SubscriptionPlan]
   - calculate_price(tier: str, camera_count: int) -> float

2. SubscriptionPlan dataclass:
   - tier: str
   - name: str
   - price_per_camera_bdt: float
   - max_cameras: int
   - features: list[str]
   - is_popular: bool

3. UserSubscription dataclass:
   - user_id: str
   - tier: str
   - status: str (active/cancelled/expired)
   - started_at: datetime
   - expires_at: Optional[datetime]
   - cancelled_at: Optional[datetime]
   - auto_renew: bool
   - payment_method: str

4. PaymentProcessor class:
   - initiate_bkash_payment(user_id: str, amount: float, reference: str) -> PaymentInitResult
   - initiate_nagad_payment(user_id: str, amount: float, reference: str) -> PaymentInitResult
   - verify_payment(transaction_id: str, method: str) -> PaymentVerification
   - process_refund(payment_id: str, reason: str) -> RefundResult
   - get_payment_status(payment_id: str) -> str

5. PaymentInitResult dataclass:
   - success: bool
   - transaction_id: str
   - payment_url: Optional[str]  # redirect URL for user
   - merchant_number: str
   - reference: str
   - message: str

6. PaymentVerification dataclass:
   - verified: bool
   - amount: float
   - transaction_id: str
   - payer_number: str
   - status: str
   - message: str

7. RefundResult dataclass:
   - success: bool
   - refund_id: str
   - amount: float
   - message: str

8. TrialManager class:
   - start_trial(user_id: str) -> TrialInfo
   - get_trial_info(user_id: str) -> Optional[TrialInfo]
   - is_trial_active(user_id: str) -> bool
   - is_trial_expired(user_id: str) -> bool
   - get_trial_days_remaining(user_id: str) -> int
   - expire_trial(user_id: str) -> TrialInfo
   - convert_trial_to_subscription(user_id: str, tier: str, payment_method: str) -> UserSubscription

9. TrialInfo dataclass:
   - user_id: str
   - started_at: datetime
   - expires_at: datetime
   - days_remaining: int
   - is_active: bool
   - cameras_used: int
   - max_cameras: int

10. API Endpoints:
    - GET /api/subscription/plans — List available plans
    - GET /api/subscription — Get current subscription
    - POST /api/subscription/create — Create subscription
    - POST /api/subscription/upgrade — Upgrade tier
    - POST /api/subscription/downgrade — Downgrade tier
    - POST /api/subscription/cancel — Cancel subscription
    - POST /api/payment/bkash/initiate — Initiate bKash payment
    - POST /api/payment/nagad/initiate — Initiate Nagad payment
    - POST /api/payment/verify — Verify payment
    - GET /api/trial — Get trial info
    - POST /api/trial/start — Start free trial

TEST CASES:
test_get_plan_returns_correct_tier, test_create_subscription_stores_in_mega, test_upgrade_subscription_changes_tier, test_downgrade_subscription_changes_tier, test_cancel_subscription_marks_cancelled, test_calculate_price_household_1_camera, test_calculate_price_business_3_cameras, test_initiate_bkash_payment_returns_transaction_id, test_initiate_nagad_payment_returns_transaction_id, test_verify_payment_confirms_transaction, test_process_refund_returns_refund_id, test_start_trial_creates_trial, test_is_trial_active_returns_true, test_is_trial_expired_returns_false, test_get_trial_days_remaining_returns_count, test_expire_trial_marks_expired, test_convert_trial_to_subscription_creates_subscription, test_subscription_api_endpoints_require_auth, test_payment_api_endpoints_require_auth

OUTPUT: Generate subscription_manager.py, payment_processor.py, trial_manager.py, and test_billing_mega.py. Use async/await throughout. Import MegaCRUD from mega_crud.py.
```
