# Vision OS V6 — DeepSeek Coding Prompts
# Multi-Camera Management & Admin Panel
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

## SPRINT 8.1 — Camera Health Monitoring
### Files: backend/core/camera_health.py
### Tests: backend/tests/unit/test_camera_health.py

```
You are building the camera health monitoring module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + PostgreSQL
- Each camera sends periodic heartbeats (every 30s via WebSocket)
- Health monitoring tracks: online/offline status, uptime, error count, last heartbeat
- Supports up to 10 cameras per user with no hard limit
- Admin panel shows real-time health status for all cameras
- Health history stored for 30 days for trend analysis
- Auto-detects camera disconnection and triggers alerts

KEY DECISIONS:
- D026: All calls async
- No camera limit enforced in code (system supports up to 10 cameras)
- Health data retained for 30 days, then aggregated to daily summaries

FUNCTIONS TO IMPLEMENT:

1. CameraHealthMonitor class:
   - record_heartbeat(camera_id: str, status: str) -> dict
   - get_camera_health(camera_id: str) -> CameraHealth
   - get_all_cameras_health(user_id: str) -> list[CameraHealth]
   - get_offline_cameras(threshold_minutes: int = 5) -> list[str]
   - get_camera_uptime(camera_id: str, since: datetime) -> float
   - get_camera_error_count(camera_id: str, since: datetime) -> int
   - get_health_history(camera_id: str, days: int = 7) -> list[HealthSnapshot]
   - mark_camera_offline(camera_id: str, reason: str) -> dict
   - mark_camera_online(camera_id: str) -> dict
   - get_health_summary(user_id: str) -> HealthSummary

2. HealthSummary dataclass:
   - total_cameras: int
   - online_cameras: int
   - offline_cameras: int
   - error_cameras: int
   - avg_uptime_pct: float
   - total_errors_24h: int
   - last_updated: datetime

3. CameraHealth dataclass:
   - camera_id: str
   - camera_name: str
   - status: str (online/offline/error)
   - last_heartbeat: Optional[datetime]
   - uptime_pct_24h: float
   - uptime_pct_7d: float
   - error_count_24h: int
   - error_count_7d: int
   - location_id: str
   - location_name: str

4. HealthSnapshot dataclass:
   - timestamp: datetime
   - status: str
   - latency_ms: float
   - error_count: int
   - frames_processed: int

TEST CASES:
test_record_heartbeat_updates_status, test_get_camera_health_returns_correct_data, test_get_all_cameras_health_returns_list, test_offline_detection_after_threshold, test_uptime_calculation_24h, test_uptime_calculation_7d, test_error_count_24h, test_health_history_returns_snapshots, test_mark_offline_sets_status, test_mark_online_clears_offline, test_health_summary_aggregates_correctly, test_concurrent_heartbeat_updates, test_health_data_retention_30_days

OUTPUT: Generate camera_health.py and test_camera_health.py. Use async/await throughout.
```

---

## SPRINT 8.2 — Camera Metrics & Analytics
### Files: backend/analytics/camera_metrics.py
### Tests: backend/tests/unit/test_camera_metrics.py

```
You are building the per-camera metrics and analytics module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + numpy (optional)
- Tracks per-camera: triggers/day, AI cost, bandwidth usage, events generated
- Daily metrics stored for 90 days
- Supports up to 10 cameras per user
- Admin dashboard shows cost breakdown per camera
- Usage-based billing calculations
- Bandwidth estimation: avg JPEG size × triggers/day

KEY DECISIONS:
- D026: All calls async
- Metrics computed daily via cron job (or on-demand)
- Cost estimates based on Gemini 2.0 Flash pricing ($0.00010/image)

FUNCTIONS TO IMPLEMENT:

1. CameraMetricsCollector class:
   - record_trigger(camera_id: str, frame_size_bytes: int) -> dict
   - record_ai_call(camera_id: str, model: str, cost: float) -> dict
   - get_daily_metrics(camera_id: str, date: date) -> DailyCameraMetrics
   - get_metrics_range(camera_id: str, start: date, end: date) -> list[DailyCameraMetrics]
   - get_all_cameras_metrics(user_id: str, date: date) -> list[DailyCameraMetrics]
   - get_cost_breakdown(camera_id: str, days: int = 30) -> CostBreakdown
   - get_bandwidth_usage(camera_id: str, days: int = 30) -> BandwidthSummary
   - get_trigger_trend(camera_id: str, days: int = 30) -> list[dict]
   - compute_daily_summary(camera_id: str, date: date) -> DailyCameraMetrics
   - get_top_triggers_cameras(user_id: str, limit: int = 10) -> list[dict]

2. DailyCameraMetrics dataclass:
   - camera_id: str
   - date: date
   - total_triggers: int
   - ai_calls: int
   - ai_cost_total: float
   - bandwidth_bytes: int
   - events_generated: int
   - high_threat_events: int
   - avg_frame_size_bytes: float
   - uptime_pct: float

3. CostBreakdown dataclass:
   - camera_id: str
   - period_days: int
   - total_ai_cost: float
   - total_storage_cost: float
   - total_bandwidth_cost: float
   - total_cost: float
   - cost_per_day: float
   - cost_per_trigger: float

4. BandwidthSummary dataclass:
   - camera_id: str
   - period_days: int
   - total_bytes: int
   - total_mb: float
   - avg_daily_mb: float
   - peak_daily_mb: float

TEST CASES:
test_record_trigger_increments_count, test_record_ai_call_tracks_cost, test_get_daily_metrics_returns_data, test_get_metrics_range_returns_list, test_get_all_cameras_metrics, test_cost_breakdown_calculates_correctly, test_bandwidth_usage_summary, test_trigger_trend_returns_daily_counts, test_compute_daily_summary_aggregates, test_top_triggers_cameras_ordered, test_metrics_retention_90_days, test_concurrent_metric_recording

OUTPUT: Generate camera_metrics.py and test_camera_metrics.py. Use async/await throughout.
```

---

## SPRINT 8.3 — Admin Camera Management API
### Files: backend/api/admin_cameras.py
### Tests: backend/tests/unit/test_admin_cameras.py

```
You are building the admin-only camera management API endpoints for Vision OS.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async
- Admin-only endpoints for managing all cameras across all users
- Supports bulk operations (enable/disable/delete multiple cameras)
- Camera health monitoring endpoints
- Camera configuration management
- No camera limit enforcement (system supports up to 10 cameras per user)
- Admin authentication via Firebase Auth with admin role check

KEY DECISIONS:
- D026: All calls async
- Admin role required for all endpoints
- Bulk operations limited to 50 cameras per request

FUNCTIONS TO IMPLEMENT:

1. AdminCameraRouter class:
   - GET /admin/cameras — List all cameras across all users (paginated)
   - GET /admin/cameras/{camera_id} — Get camera details + health
   - GET /admin/cameras/health — Get health summary for all cameras
   - GET /admin/cameras/offline — Get all offline cameras
   - GET /admin/cameras/{camera_id}/health — Get camera health history
   - GET /admin/cameras/{camera_id}/metrics — Get camera metrics
   - POST /admin/cameras/bulk — Bulk operations (enable/disable/delete)
   - POST /admin/cameras/{camera_id}/reset — Reset camera connection
   - PUT /admin/cameras/{camera_id}/config — Update camera config
   - GET /admin/cameras/stats — Aggregate camera statistics
   - GET /admin/cameras/by-user/{user_id} — List cameras for specific user

2. BulkOperationRequest dataclass:
   - camera_ids: list[str]
   - operation: str (enable/disable/delete/reset)
   - reason: Optional[str]

3. CameraStats dataclass:
   - total_cameras: int
   - online_cameras: int
   - offline_cameras: int
   - error_cameras: int
   - total_users_with_cameras: int
   - avg_cameras_per_user: float
   - total_triggers_24h: int
   - total_ai_cost_24h: float
   - cameras_by_mode: dict[str, int]

TEST CASES:
test_list_cameras_returns_paginated_results, test_get_camera_details_includes_health, test_health_summary_returns_aggregates, test_offline_cameras_returns_list, test_camera_health_history, test_camera_metrics_endpoint, test_bulk_enable_cameras, test_bulk_disable_cameras, test_bulk_delete_cameras, test_reset_camera_connection, test_update_camera_config, test_camera_stats_aggregates, test_cameras_by_user, test_non_admin_gets_403, test_bulk_operation_limit_50

OUTPUT: Generate admin_cameras.py and test_admin_cameras.py. Use async/await throughout.
```

---

## SPRINT 8.4 — Enhanced Admin Dashboard UI
### Files: backend/dashboard/templates/admin_cameras.html, backend/dashboard/static/admin_cameras.js, backend/dashboard/static/admin_cameras.css
### Tests: backend/tests/unit/test_admin_cameras_ui.py

```
You are building the enhanced admin camera management dashboard UI for Vision OS.

CONTEXT:
- Stack: Jinja2 + JavaScript + CSS (dark navy theme matching existing dashboard)
- Mobile-first responsive design
- Real-time camera status indicators (green/yellow/red)
- Camera grid view showing all cameras with health status
- Camera detail modal with health metrics and charts
- Bulk operations interface (select multiple cameras)
- Camera topology visualization (drag-and-drop layout)
- Supports up to 10 cameras per user, admin sees all

KEY DECISIONS:
- D012: Firebase Auth for login
- Dark navy theme matching existing dashboard
- Real-time updates via WebSocket (or polling every 30s)

PAGES/COMPONENTS TO BUILD:

1. admin_cameras.html — Main camera management page
   - Camera grid with status cards
   - Filter by status (online/offline/error/all)
   - Filter by user/location
   - Bulk action toolbar
   - Search by camera name or user email

2. Camera Status Card component:
   - Camera name + location
   - Status indicator (green/yellow/red dot)
   - Last heartbeat timestamp
   - Uptime percentage (24h)
   - Error count (24h)
   - Trigger count (24h)
   - Quick actions: view details, reset, disable

3. Camera Detail Modal:
   - Full health metrics
   - Uptime chart (7 days)
   - Trigger trend chart (7 days)
   - Error log table
   - Configuration panel
   - Cost breakdown

4. Bulk Operations Toolbar:
   - Select all / deselect all
   - Enable selected
   - Disable selected
   - Delete selected (with confirmation)
   - Reset selected

5. Camera Topology View:
   - Drag-and-drop camera layout
   - Connection lines between cameras
   - Camera status colors on nodes
   - Zoom and pan support

TEST CASES:
test_admin_cameras_page_loads, test_camera_grid_displays_all_cameras, test_status_filter_works, test_search_filters_cameras, test_bulk_select_all, test_bulk_disable_confirmation, test_camera_detail_modal_shows_metrics, test_uptime_chart_renders, test_topology_view_loads, test_mobile_responsive_layout, test_pagination_works, test_error_state_displayed

OUTPUT: Generate admin_cameras.html, admin_cameras.js, admin_cameras.css, and test_admin_cameras_ui.py.
```

---

## SPRINT 8.5 — Bulk Camera Operations
### Files: backend/core/bulk_operations.py
### Tests: backend/tests/unit/test_bulk_operations.py

```
You are building the bulk camera operations module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Admin can perform operations on multiple cameras simultaneously
- Operations: enable, disable, delete, reset, change mode, apply config template
- Progress tracking for long-running bulk operations
- Rollback on partial failure
- Audit logging for all bulk operations
- Supports up to 50 cameras per bulk operation

KEY DECISIONS:
- D026: All calls async
- Transactional: all-or-nothing for each operation type
- Audit trail stored in database

FUNCTIONS TO IMPLEMENT:

1. BulkOperationsManager class:
   - bulk_enable(camera_ids: list[str], admin_id: str) -> BulkOperationResult
   - bulk_disable(camera_ids: list[str], admin_id: str, reason: str = "") -> BulkOperationResult
   - bulk_delete(camera_ids: list[str], admin_id: str) -> BulkOperationResult
   - bulk_reset(camera_ids: list[str], admin_id: str) -> BulkOperationResult
   - bulk_change_mode(camera_ids: list[str], mode: str, admin_id: str) -> BulkOperationResult
   - bulk_apply_template(camera_ids: list[str], template_id: str, admin_id: str) -> BulkOperationResult
   - get_operation_status(operation_id: str) -> BulkOperationStatus
   - cancel_operation(operation_id: str) -> dict
   - get_operation_history(admin_id: str, limit: int = 50) -> list[BulkOperationResult]

2. BulkOperationResult dataclass:
   - operation_id: str
   - operation_type: str
   - total_cameras: int
   - succeeded: int
   - failed: int
   - failures: list[dict]  # [{camera_id, error}]
   - started_at: datetime
   - completed_at: Optional[datetime]
   - status: str (running/completed/failed/cancelled)
   - admin_id: str

3. BulkOperationStatus dataclass:
   - operation_id: str
   - status: str
   - progress_pct: float
   - processed: int
   - total: int
   - estimated_remaining_sec: Optional[float]

TEST CASES:
test_bulk_enable_all_succeed, test_bulk_enable_partial_failure_rollback, test_bulk_disable_all_succeed, test_bulk_delete_with_confirmation, test_bulk_reset_cameras, test_bulk_change_mode, test_bulk_apply_template, test_get_operation_status_running, test_get_operation_status_completed, test_cancel_running_operation, test_operation_history_returns_list, test_bulk_operation_audit_log, test_concurrent_bulk_operations, test_bulk_operation_limit_50

OUTPUT: Generate bulk_operations.py and test_bulk_operations.py. Use async/await throughout.
```

---

## Quick Reference: V6 File Paths

| Sprint | File Path |
|--------|-----------|
| 8.1 | `backend/core/camera_health.py` |
| 8.1 | `backend/tests/unit/test_camera_health.py` |
| 8.2 | `backend/analytics/camera_metrics.py` |
| 8.2 | `backend/tests/unit/test_camera_metrics.py` |
| 8.3 | `backend/api/admin_cameras.py` |
| 8.3 | `backend/tests/unit/test_admin_cameras.py` |
| 8.4 | `backend/dashboard/templates/admin_cameras.html` |
| 8.4 | `backend/dashboard/static/admin_cameras.js` |
| 8.4 | `backend/dashboard/static/admin_cameras.css` |
| 8.4 | `backend/tests/unit/test_admin_cameras_ui.py` |
| 8.5 | `backend/core/bulk_operations.py` |
| 8.5 | `backend/tests/unit/test_bulk_operations.py` |

---

*Vision OS V6 — Multi-Camera Management & Admin Panel*

*Copy, paste, generate, test, commit. Repeat.*
