# Vision OS V10 — DeepSeek Coding Prompts
# Industry-Ready SaaS: Live Launch & Global Access (10–20 Cameras)
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

## SPRINT 12.1 — Camera Capacity Upgrade (10 → 20 Cameras)
### Files: backend/core/camera_limits.py, backend/api/cameras.py, backend/billing/subscription_manager.py, backend/dashboard/templates/settings.html
### Tests: backend/tests/unit/test_camera_limits.py

```
You are upgrading Vision OS camera limits from 10 to 20 cameras per user. Vision OS is an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async + Jinja2
- Current limit: 10 cameras per user across all tiers
- New limit: 20 cameras per user across all tiers
- Must update: database constraints, API validation, billing tier tables, UI copy, subscription enforcement
- Backward compatible: existing users with 10 cameras can add 10 more
- Free trial: 20 cameras, 30 days
- Household (299 BDT/camera/month): up to 20 cameras
- Business (499 BDT/camera/month): up to 20 cameras
- All existing enforcement points must be updated

KEY DECISIONS:
- D026: All calls async
- Centralized limit constants in camera_limits.py (single source of truth)
- No migration needed — constraint is enforced in application layer, not DB schema

FUNCTIONS TO IMPLEMENT:

1. CameraLimits class (in camera_limits.py):
   - MAX_CAMERAS_PER_USER: int = 20
   - get_max_cameras(tier: str) -> int
   - validate_camera_count(user_id: str, current_count: int, new_count: int) -> ValidationResult
   - get_camera_usage_percentage(user_id: str, current_count: int) -> float
   - get_upgrade_suggestion(current_count: int) -> str
   - TIER_LIMITS: dict = {"free": 20, "household": 20, "business": 20}

2. ValidationResult dataclass:
   - allowed: bool
   - current_count: int
   - max_count: int
   - remaining: int
   - message: str
   - upgrade_suggestion: Optional[str]

3. Updated Camera CRUD (in cameras.py):
   - create_camera() — enforce max 20 before insert
   - bulk_create_cameras() — enforce total won't exceed 20
   - get_camera_quota(user_id: str) -> QuotaInfo

4. QuotaInfo dataclass:
   - total_cameras: int
   - max_cameras: int
   - remaining: int
   - usage_percentage: float
   - tier: str

5. Updated Subscription Manager (in subscription_manager.py):
   - Update tier definitions: all tiers now support 20 cameras
   - Update pricing display strings
   - Update upgrade/downgrade validation

6. Updated Settings UI (in settings.html):
   - Change "up to 10 cameras" → "up to 20 cameras" everywhere
   - Update progress bar max from 10 to 20
   - Update billing table column headers

TEST CASES:
test_max_cameras_constant_is_20, test_get_max_cameras_returns_20_for_all_tiers, test_validate_camera_count_under_limit_returns_allowed, test_validate_camera_count_at_limit_returns_allowed, test_validate_camera_count_over_limit_returns_blocked, test_get_camera_usage_percentage_calculates_correctly, test_get_upgrade_suggestion_when_near_limit, test_create_camera_enforces_20_limit, test_bulk_create_enforces_total_20, test_get_camera_quota_returns_correct_remaining, test_existing_user_with_10_cameras_can_add_10_more, test_settings_ui_displays_20_in_copy, test_subscription_tier_table_updated_to_20

OUTPUT: Generate camera_limits.py, updated cameras.py, updated subscription_manager.py, updated settings.html, and test_camera_limits.py.
```

---

## SPRINT 12.2 — Global Deployment Pipeline
### Files: infrastructure/deploy.sh, Dockerfile, .github/workflows/deploy.yml, infrastructure/secrets_setup.py
### Tests: backend/tests/unit/test_deploy_pipeline.py

```
You are building the one-command global deployment pipeline for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Google Cloud Run + Docker + GitHub Actions + Secret Manager
- One-command deploy: ./deploy.sh --env production
- Multi-stage Docker build: builder → slim runtime (< 200 MB final image)
- CI/CD: GitHub Actions → build → push to Artifact Registry → deploy to Cloud Run
- Secrets: API keys, database URLs, Firebase credentials stored in Secret Manager
- Region: asia-south1 (Mumbai) — lowest latency for Bangladesh
- Supports 20 cameras per user, 100+ concurrent users at launch
- Zero-downtime deployments with Cloud Run revision traffic splitting

KEY DECISIONS:
- D026: All calls async
- Cloud Run for serverless deployment
- Secret Manager for all secrets (never in env files)
- Multi-stage Docker build for minimal attack surface

FUNCTIONS TO IMPLEMENT:

1. deploy.sh — One-command deployment script:
   - Usage: ./deploy.sh [--env staging|production] [--tag v1.0.0]
   - Steps:
     1. Validate environment and prerequisites (gcloud, docker, python)
     2. Run test suite (pytest backend/tests/ -v)
     3. Build Docker image with git commit hash tag
     4. Push to Google Artifact Registry (asia-south1-docker.pkg.dev)
     5. Deploy to Cloud Run with revision name = git hash
     6. Run smoke test against deployed URL
     7. Rollback on failure (deploy previous revision)
   - Flags: --env, --tag, --skip-tests, --rollback

2. Dockerfile — Multi-stage build:
   - Stage 1 (builder): python:3.11-slim, install deps, compile
   - Stage 2 (runtime): python:3.11-slim-bookworm, < 200 MB
   - Copy only: app code, compiled deps, static assets
   - Health check: CMD curl -f http://localhost:8080/health
   - Non-root user: visionos (UID 1000)
   - Expose port 8080

3. .github/workflows/deploy.yml — Updated CD:
   - Trigger: push to main, or manual workflow_dispatch with tag
   - Jobs:
     - test: pytest + lint (Black, Ruff)
     - build: docker build + push to Artifact Registry
     - deploy: gcloud run deploy with revision traffic split
     - smoke: curl health endpoint, run e2e tests
   - Environment: staging (auto), production (manual approval)

4. secrets_setup.py — Secret Manager bootstrap:
   - create_secret(secret_id: str, value: str) -> str
   - update_secret(secret_id: str, value: str) -> str
   - get_secret(secret_id: str) -> str
   - list_secrets() -> list[SecretInfo]
   - delete_secret(secret_id: str) -> dict
   - sync_env_to_secrets(env_file: str) -> dict
   - Required secrets:
     - DATABASE_URL
     - FIREBASE_SERVICE_ACCOUNT_JSON
     - GEMINI_API_KEY
     - GROQ_API_KEY
     - SENDGRID_API_KEY
     - TELEGRAM_BOT_TOKEN
     - SECRET_KEY
     - BKASH_MERCHANT_ID, BKASH_API_KEY, BKASH_SECRET_KEY
     - NAGAD_MERCHANT_ID, NAGAD_API_KEY

5. SecretInfo dataclass:
   - secret_id: str
   - created_at: datetime
   - updated_at: datetime
   - version_count: int
   - labels: dict

TEST CASES:
test_deploy_script_validates_prerequisites, test_deploy_script_builds_docker, test_deploy_script_pushes_to_registry, test_deploy_script_deploys_to_cloud_run, test_deploy_script_rollback_on_failure, test_dockerfile_multi_stage_build, test_dockerfile_runs_as_non_root, test_dockerfile_health_check_configured, test_github_actions_workflow_has_test_job, test_github_actions_workflow_has_deploy_job, test_github_actions_workflow_has_smoke_job, test_secrets_setup_create_secret, test_secrets_setup_get_secret, test_secrets_setup_sync_env_to_secrets, test_secrets_setup_list_secrets

OUTPUT: Generate deploy.sh, Dockerfile, .github/workflows/deploy.yml, secrets_setup.py, and test_deploy_pipeline.py.
```

---

## SPRINT 12.3 — Public Access Hardening
### Files: backend/core/security_middleware.py, backend/core/firebase_rules.json, backend/core/api_key_manager.py
### Tests: backend/tests/unit/test_security_middleware.py

```
You are building the security hardening layer for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. This makes the app safe for public access from anywhere.

CONTEXT:
- Stack: FastAPI + Python asyncio + Firebase Auth + Google Cloud
- CORS: allow all origins (public SaaS), but restrict sensitive endpoints
- Rate limiting: 100 requests/min per IP (general), 10/min for auth endpoints
- HTTPS enforced at load balancer level (redirect HTTP → HTTPS)
- Request ID tracing for debugging
- Firebase Security Rules for Realtime Database and Cloud Storage
- API key management for third-party integrations
- Audit logging for all admin actions
- Supports 20 cameras per user, global access from any country

KEY DECISIONS:
- D012: Firebase Auth for authentication
- D026: All calls async
- Rate limiting at application layer (complementing Cloud Armor)
- Firebase Security Rules as single source of truth for DB access

FUNCTIONS TO IMPLEMENT:

1. SecurityMiddleware class (in security_middleware.py):
   - cors_middleware(app: FastAPI) -> None
   - rate_limit_middleware(app: FastAPI) -> None
   - https_redirect_middleware(app: FastAPI) -> None
   - request_id_middleware(app: FastAPI) -> None
   - security_headers_middleware(app: FastAPI) -> None
   - add_all_middleware(app: FastAPI) -> None

2. RateLimiter class:
   - __init__(max_requests: int = 100, window_seconds: int = 60)
   - check_rate_limit(ip: str, endpoint: str) -> RateLimitResult
   - get_remaining(ip: str, endpoint: str) -> int
   - get_reset_time(ip: str, endpoint: str) -> int
   - reset_limit(ip: str, endpoint: str) -> dict
   - get_rate_limit_stats() -> RateLimitStats
   - Endpoint-specific limits:
     - /api/auth/*: 10 requests/min per IP
     - /api/signup: 5 requests/min per IP
     - /api/*: 100 requests/min per IP
     - /static/*: 300 requests/min per IP

3. RateLimitResult dataclass:
   - allowed: bool
   - remaining: int
   - reset_at: int  # unix timestamp
   - retry_after: Optional[int]  # seconds

4. RateLimitStats dataclass:
   - total_requests_tracked: int
   - blocked_requests: int
   - active_ips: int
   - top_endpoints: list[tuple[str, int]]

5. Security Headers:
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - X-XSS-Protection: 1; mode=block
   - Strict-Transport-Security: max-age=31536000; includeSubDomains
   - Content-Security-Policy: restrict script sources
   - Referrer-Policy: strict-origin-when-cross-origin
   - Permissions-Policy: camera=(), microphone=()

6. Firebase Security Rules (in firebase_rules.json):
   - Realtime Database rules:
     - /users/{uid}: only authenticated owner can read/write
     - /cameras/{uid}: only authenticated owner
     - /events/{uid}: only authenticated owner
     - /admin/*: only users with admin claim
   - Cloud Storage rules:
     - /thumbnails/{uid}/{camera_id}/{event_id}.jpg: only owner
     - /clips/{uid}/{camera_id}/{event_id}.mp4: only owner + signed URL
     - /static/*: public read

7. ApiKeyManager class (in api_key_manager.py):
   - generate_api_key(user_id: str, name: str, permissions: list[str]) -> ApiKey
   - validate_api_key(api_key: str) -> Optional[ApiKey]
   - revoke_api_key(api_key_id: str) -> dict
   - list_user_api_keys(user_id: str) -> list[ApiKey]
   - rotate_api_key(api_key_id: str) -> ApiKey
   - get_api_key_usage(api_key_id: str, since: datetime) -> ApiKeyUsage
   - audit_log(action: str, admin_id: str, details: dict) -> dict

8. ApiKey dataclass:
   - key_id: str
   - user_id: str
   - name: str
   - key_prefix: str  # first 8 chars for identification
   - permissions: list[str]
   - created_at: datetime
   - expires_at: Optional[datetime]
   - last_used_at: Optional[datetime]
   - is_active: bool

9. ApiKeyUsage dataclass:
   - key_id: str
   - total_requests: int
   - last_24h_requests: int
   - endpoints_accessed: list[str]
   - last_error: Optional[str]

TEST CASES:
test_cors_middleware_allows_valid_origins, test_rate_limit_allows_normal_traffic, test_rate_limit_blocks_excessive_requests, test_rate_limit_resets_after_window, test_rate_limit_different_limits_per_endpoint, test_https_redirect_redirects_http, test_request_id_added_to_response, test_security_headers_present_in_response, test_firebase_rules_owner_only_access, test_firebase_rules_admin_access, test_firebase_rules_public_static_access, test_generate_api_key_returns_valid_key, test_validate_api_key_valid, test_validate_api_key_revoked, test_revoke_api_key_marks_inactive, test_rotate_api_key_generates_new_key, test_api_key_usage_tracking, test_audit_log_creates_entry

OUTPUT: Generate security_middleware.py, firebase_rules.json, api_key_manager.py, and test_security_middleware.py. Use async/await throughout.
```

---

## SPRINT 12.4 — End-to-End Smoke Test Suite
### Files: backend/tests/e2e/test_full_journey.py, backend/tests/e2e/test_20_cameras.py, backend/tests/e2e/conftest.py
### Tests: These ARE the tests — run against staging environment

```
You are building the end-to-end smoke test suite for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. These tests simulate a real user from signup to daily use.

CONTEXT:
- Stack: pytest + httpx (async) + Firebase Auth REST API
- Tests run against a staging environment URL (configurable via env var STAGING_URL)
- Tests simulate real user behavior, not mocks
- Must pass before any production deployment
- Tests are idempotent (clean up after themselves)
- Supports 20 cameras per user verification
- Tests cover: signup, camera management, event flow, AI query, billing, admin

KEY DECISIONS:
- D012: Firebase Auth for authentication
- D026: All calls async
- E2E tests run against staging, not local
- Test users are created and deleted in each run

FUNCTIONS/TESTS TO IMPLEMENT:

1. conftest.py — Test fixtures:
   - staging_url: str — from env var STAGING_URL or default
   - test_user: dict — creates Firebase user, returns auth token
   - test_cameras(count: int) -> list[dict] — registers N cameras
   - cleanup_test_user(user_id: str) -> None — deletes user + data
   - async_client() -> httpx.AsyncClient

2. test_full_journey.py — Complete user lifecycle:
   - test_01_health_endpoint_returns_200
   - test_02_public_landing_page_loads
   - test_03_signup_new_user
   - test_04_verify_email
   - test_05_login_returns_token
   - test_06_get_user_profile
   - test_07_add_first_camera
   - test_08_get_camera_list
   - test_09_update_camera_settings
   - test_10_trigger_test_event
   - test_11_get_event_feed
   - test_12_search_events_by_query
   - test_13_get_person_profile
   - test_14_update_subscription_tier
   - test_15_initiate_payment
   - test_16_get_billing_history
   - test_17_connect_telegram
   - test_18_update_settings
   - test_19_logout
   - test_20_re_login_and_verify_data_persists

3. test_20_cameras.py — 20-camera capacity verification:
   - test_add_20_cameras_one_by_one
   - test_add_21st_camera_returns_403
   - test_bulk_add_20_cameras
   - test_bulk_add_21st_camera_returns_error
   - test_all_20_cameras_appear_in_list
   - test_all_20_cameras_accept_events
   - test_camera_quota_shows_20_of_20
   - test_delete_one_camera_then_add_new_one
   - test_camera_health_all_20_visible
   - test_20_cameras_pagination_works

4. Test data cleanup:
   - Each test creates and tears down its own test data
   - test_cleanup fixture deletes test user and all associated data
   - On failure, test user ID is logged for manual cleanup

TEST CASES (these ARE the tests):
test_01_health_endpoint_returns_200, test_02_public_landing_page_loads, test_03_signup_new_user, test_04_verify_email, test_05_login_returns_token, test_06_get_user_profile, test_07_add_first_camera, test_08_get_camera_list, test_09_update_camera_settings, test_10_trigger_test_event, test_11_get_event_feed, test_12_search_events_by_query, test_13_get_person_profile, test_14_update_subscription_tier, test_15_initiate_payment, test_16_get_billing_history, test_17_connect_telegram, test_18_update_settings, test_19_logout, test_20_re_login_and_verify_data_persists, test_add_20_cameras_one_by_one, test_add_21st_camera_returns_403, test_bulk_add_20_cameras, test_bulk_add_21st_camera_returns_error, test_all_20_cameras_appear_in_list, test_all_20_cameras_accept_events, test_camera_quota_shows_20_of_20, test_delete_one_camera_then_add_new_one, test_camera_health_all_20_visible, test_20_cameras_pagination_works

OUTPUT: Generate conftest.py, test_full_journey.py, and test_20_cameras.py. Use async/await throughout.
```

---

## SPRINT 12.5 — Production Readiness Checklist Runner
### Files: infrastructure/readiness_check.py
### Tests: backend/tests/unit/test_readiness_check.py

```
You are building the automated production readiness checker for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. This script runs 60+ checks to verify the system is ready for public launch.

CONTEXT:
- Stack: Python asyncio + httpx + subprocess
- Runs as: python -m infrastructure.readiness_check
- Outputs: JSON report + Markdown summary
- Checks 12 categories: Infrastructure, Database, Security, AI, Billing, Monitoring, UI, Performance, Compliance, Backup/DR, Legal, Integrations
- Each check returns: pass/fail/warn with details
- Fails fast on critical checks (DB connection, auth, AI API)
- Generates readiness_report.md with pass/fail badges
- Supports 20 cameras per user verification

KEY DECISIONS:
- D026: All calls async
- Readiness check is standalone (no app dependencies)
- Report is both human-readable (Markdown) and machine-readable (JSON)

FUNCTIONS TO IMPLEMENT:

1. ReadinessChecker class:
   - run_all_checks() -> ReadinessReport
   - run_category(category: str) -> CategoryResult
   - run_single_check(check_name: str) -> CheckResult
   - generate_markdown_report(report: ReadinessReport) -> str
   - generate_json_report(report: ReadinessReport) -> dict
   - print_summary(report: ReadinessReport) -> None
   - export_report(report: ReadinessReport, path: str) -> str

2. ReadinessReport dataclass:
   - timestamp: datetime
   - environment: str
   - total_checks: int
   - passed: int
   - failed: int
   - warnings: int
   - overall_status: str (pass/fail/warn)
   - categories: list[CategoryResult]
   - duration_seconds: float

3. CategoryResult dataclass:
   - name: str
   - status: str
   - checks: list[CheckResult]
   - passed: int
   - failed: int
   - warnings: int

4. CheckResult dataclass:
   - name: str
   - status: str (pass/fail/warn)
   - message: str
   - details: Optional[str]
   - duration_ms: float
   - recommended_fix: Optional[str]

5. Check Categories (60+ checks):

   A. Infrastructure (8 checks):
      - cloud_run_service_running
      - cloud_run_min_instances_1
      - cloud_run_max_instances_10
      - load_balancer_configured
      - ssl_certificate_valid
      - cdn_enabled_for_static
      - vpc_connector_active
      - secret_manager_secrets_exist

   B. Database (6 checks):
      - database_connection_successful
      - pgvector_extension_enabled
      - connection_pool_initialized
      - migrations_up_to_date
      - read_replica_connected (if configured)
      - database_size_within_limits

   C. Security (8 checks):
      - cors_configured
      - rate_limiting_active
      - https_redirect_works
      - firebase_rules_valid
      - api_key_rotation_enabled
      - security_headers_present
      - sql_injection_protection_active
      - xss_protection_active

   D. AI Services (5 checks):
      - gemini_api_responds
      - groq_api_responds (if configured)
      - ai_response_time_under_5s
      - reid_engine_initialized
      - query_engine_responds

   E. Billing (5 checks):
      - bKash_api_responds
      - Nagad_api_responds (if configured)
      - subscription_tiers_defined
      - trial_manager_initialized
      - payment_processor_ready

   F. Monitoring (4 checks):
      - metrics_collector_running
      - alert_system_initialized
      - telegram_bot_connected
      - email_service_configured

   G. UI (4 checks):
      - landing_page_returns_200
      - login_page_returns_200
      - dashboard_returns_200_with_auth
      - help_center_returns_200

   H. Performance (4 checks):
      - api_p95_latency_under_500ms
      - database_query_time_under_100ms
      - static_assets_load_under_200ms
      - concurrent_20_camera_simulation

   I. Compliance (6 checks):
      - gdpr_data_deletion_works
      - data_retention_policies_active
      - cookie_consent_banner_present
      - privacy_policy_accessible
      - terms_of_service_accessible
      - audit_trail_active

   J. Backup & DR (5 checks):
      - automated_db_backups_enabled
      - backup_recovery_tested
      - disaster_recovery_plan_documented
      - rpo_within_1_hour
      - rto_within_4_hours

   K. Legal (3 checks):
      - privacy_policy_page_returns_200
      - terms_of_service_page_returns_200
      - cookie_consent_banner_visible

   L. Integrations (4 checks):
      - webhook_system_active
      - data_export_api_works
      - status_page_accessible
      - changelog_page_accessible

6. Recommended fixes for common failures:
   - "Cloud Run service not running" → "Run: gcloud run deploy vision-os-api"
   - "Database connection failed" → "Check DATABASE_URL secret and VPC connector"
   - "Gemini API not responding" → "Check GEMINI_API_KEY secret and quota"
   - "bKash API not responding" → "Check bKash merchant credentials"
   - "GDPR data deletion failed" → "Check data_deletion.py for errors"
   - "Automated backups not enabled" → "Enable Cloud SQL automated backups"
   - "Cookie consent banner missing" → "Add cookie_consent.html to base template"

TEST CASES:
test_run_all_checks_returns_report, test_run_category_returns_category_results, test_run_single_check_returns_check_result, test_generate_markdown_report_contains_badges, test_generate_json_report_valid_json, test_print_summary_outputs_to_console, test_export_report_writes_file, test_infrastructure_checks_have_8_items, test_database_checks_have_6_items, test_security_checks_have_8_items, test_ai_checks_have_5_items, test_billing_checks_have_5_items, test_monitoring_checks_have_4_items, test_ui_checks_have_4_items, test_performance_checks_have_4_items, test_compliance_checks_have_6_items, test_backup_dr_checks_have_5_items, test_legal_checks_have_3_items, test_integrations_checks_have_4_items, test_overall_status_fail_if_any_critical_fails, test_overall_status_pass_if_all_pass

OUTPUT: Generate readiness_check.py and test_readiness_check.py. Use async/await throughout.
```

---

## SPRINT 12.6 — Launch Day Operations Runbook
### Files: doc/LAUNCH_RUNBOOK.md
### Tests: No code tests — this is a documentation sprint

```
You are writing the Launch Day Operations Runbook for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. This runbook is the single source of truth for the team on launch day.

CONTEXT:
- Stack: Markdown document (stored in doc/LAUNCH_RUNBOOK.md)
- Audience: System administrators and on-call engineers
- Covers: pre-launch checklist, launch day timeline, monitoring, incident response, rollback
- Supports 20 cameras per user, targeting first 100 users on day 1
- Team size: 1-3 people on call

DOCUMENT SECTIONS TO WRITE:

1. Pre-Launch Checklist (24 hours before):
   - [ ] Run readiness check: `python -m infrastructure.readiness_check`
   - [ ] Verify all 60+ checks pass (or document known warnings)
   - [ ] Confirm Cloud Run min instances = 1 (no cold start)
   - [ ] Verify SSL certificate is valid (not expiring within 7 days)
   - [ ] Test payment flow: bKash, Nagad (send 1 BDT test payment)
   - [ ] Verify Firebase Auth email delivery
   - [ ] Test Telegram bot responds
   - [ ] Confirm database backups are enabled
   - [ ] Verify monitoring dashboards are receiving data
   - [ ] Alert team members: confirm on-call schedule
   - [ ] Prepare rollback tag: `git tag rollback/v1.0.0-launch`
   - [ ] Verify GDPR data deletion works
   - [ ] Test data export functionality
   - [ ] Confirm cookie consent banner is visible
   - [ ] Verify status page is accessible

2. Launch Day Timeline:
   - T-60min: Final readiness check, warm up Cloud Run instances
   - T-30min: Enable public signup (remove maintenance mode)
   - T-0: Announce on social media / Telegram group
   - T+15min: Check first signup flow end-to-end
   - T+1hr: Review monitoring dashboards, check error rates
   - T+4hr: Check database connection pool utilization
   - T+8hr: Review first-day metrics (signups, cameras, events)
   - T+24hr: Post-launch retrospective

3. Monitoring Dashboards:
   - Google Cloud Monitoring URL: [link]
   - Key metrics to watch:
     - API p95 latency: should be < 500ms
     - Error rate: should be < 1%
     - Active users: growing steadily
     - Camera connections: successful
     - AI API costs: within budget
     - SLA uptime: must be > 99.9%
   - Alert thresholds:
     - P95 latency > 1000ms → warning
     - Error rate > 5% → critical
     - Database connections > 80% → warning
     - AI cost > $50/day → warning
     - SLA breach risk → critical

4. Incident Response Playbooks:

   A. High Error Rate (>5%):
      1. Check recent deployments: `gcloud run revisions list`
      2. Rollback if recent deploy: `./deploy.sh --rollback`
      3. Check database connection pool
      4. Check AI API status (Gemini, Groq)
      5. Check Firebase Auth status

   B. Database Connection Issues:
      1. Check connection pool stats: /admin/metrics
      2. Verify VPC connector is healthy
      3. Check Cloud SQL CPU/memory
      4. Restart connection pool if needed
      5. Scale up Cloud SQL if persistent

   C. Payment Processing Failure:
      1. Check bKash/Nagad API status
      2. Verify merchant credentials in Secret Manager
      3. Check payment logs in database
      4. Manual payment processing if needed
      5. Contact bKash/Nagad support

   D. AI Service Down:
      1. Check Gemini API status dashboard
      2. Fall back to cached responses if available
      3. Disable AI features temporarily via feature flag
      4. Notify users of degraded service
      5. Monitor for recovery

   E. Security Incident:
      1. Identify affected users and scope
      2. Revoke compromised API keys
      3. Force password reset for affected users
      4. Review audit logs
      5. Contact Firebase support if needed

   F. Data Breach (GDPR/DPDP):
      1. Isolate affected systems immediately
      2. Identify scope of breach (which users, what data)
      3. Notify DPO / legal team
      4. Notify affected users within 72 hours (GDPR requirement)
      5. Document incident for regulatory reporting
      6. Implement fixes and verify

   G. SLA Breach:
      1. Calculate current uptime percentage
      2. Identify root cause from monitoring
      3. Communicate with affected users
      4. Apply service credits if applicable
      5. Post-mortem within 48 hours

5. Rollback Procedure:
   - Step 1: `gcloud run deploy vision-os-api --revision=previous-revision-name`
   - Step 2: Verify health endpoint returns 200
   - Step 3: Run smoke tests: `pytest backend/tests/e2e/ -v`
   - Step 4: If needed, rollback database: restore from backup
   - Step 5: Notify team in Telegram group
   - Step 6: Document incident in doc/INCIDENTS.md

6. Communication Templates:
   - Users affected by outage:
     "We're aware of an issue affecting Vision OS. Our team is investigating. We'll update you here. — Vision OS Team"
   - Service restored:
     "Vision OS is back to normal. We've identified and fixed the issue. Apologies for the disruption. — Vision OS Team"
   - Scheduled maintenance:
     "Vision OS will be under maintenance on [date] from [time] to [time] BDT. Some features may be unavailable. — Vision OS Team"
   - Data breach notification:
     "We are writing to inform you of a security incident affecting Vision OS. [Details]. We recommend [actions]. We apologize for this incident. — Vision OS Team"

7. On-Call Contacts:
   - Primary: [Name] — [Phone] — [Telegram]
   - Secondary: [Name] — [Phone] — [Telegram]
   - Firebase Support: 1-800-FIREBASE
   - Google Cloud Support: https://console.cloud.google.com/support
   - bKash Merchant Support: 16247
   - Nagad Merchant Support: 16767
   - DPO / Legal: [Name] — [Email]

8. Post-Launch Checklist (24 hours after):
   - [ ] Review first-day metrics
   - [ ] Check for any security incidents
   - [ ] Verify all payments processed correctly
   - [ ] Check AI API costs
   - [ ] Review user feedback
   - [ ] Schedule retrospective meeting
   - [ ] Update runbook with lessons learned
   - [ ] Verify SLA uptime for first 24 hours
   - [ ] Check GDPR deletion requests (if any)
   - [ ] Review support tickets

OUTPUT: Generate LAUNCH_RUNBOOK.md with all sections above. Use clear Markdown formatting with checkboxes, code blocks, and tables.
```

---

## SPRINT 12.7 — Data Retention, Privacy & GDPR/DPDP Compliance
### Files: backend/core/data_retention.py, backend/core/data_deletion.py, backend/core/privacy_manager.py, backend/dashboard/templates/privacy_policy.html, backend/dashboard/templates/terms_of_service.html, backend/dashboard/templates/cookie_consent.html
### Tests: backend/tests/unit/test_data_retention.py, backend/tests/unit/test_privacy.py

```
You are building the data retention, privacy, and compliance module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh. This ensures GDPR (EU) and DPDP (India/Bangladesh) compliance.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async + Jinja2
- Data retention policies: events (90 days free, 1 year business), clips (30 days free, 90 days business), thumbnails (same as events), logs (30 days), audit trail (7 years for compliance)
- GDPR rights: right to access, right to rectification, right to erasure (right to be forgotten), right to data portability, right to object
- DPDP (Digital Personal Data Protection) compliance for India/Bangladesh market
- Cookie consent: GDPR-compliant cookie banner with granular consent options
- Privacy policy and terms of service pages
- Data Processing Agreement (DPA) for business users
- Automated data deletion cron job (runs daily)
- Supports 20 cameras per user, all data must be tenant-isolated

KEY DECISIONS:
- D026: All calls async
- Data retention enforced at application layer + DB cleanup cron
- GDPR right to erasure = hard delete from all tables + Firebase Auth account deletion
- Cookie consent stored in localStorage (no server-side tracking)

FUNCTIONS TO IMPLEMENT:

1. DataRetentionManager class (in data_retention.py):
   - get_retention_policy(data_type: str, tier: str) -> RetentionPolicy
   - get_expired_records(data_type: str, batch_size: int = 1000) -> list[str]
   - delete_expired_records(data_type: str) -> DeletionResult
   - run_cleanup_all() -> dict[str, DeletionResult]
   - get_storage_usage_by_tier() -> dict
   - schedule_daily_cleanup() -> None
   - RETENTION_RULES: dict = {
       "events": {"free": 90, "household": 90, "business": 365},
       "clips": {"free": 30, "household": 30, "business": 90},
       "thumbnails": {"free": 90, "household": 90, "business": 365},
       "logs": {"free": 30, "household": 30, "business": 30},
       "audit_trail": {"free": 365, "household": 365, "business": 2555},  # 7 years
     }

2. RetentionPolicy dataclass:
   - data_type: str
   - retention_days: int
   - tier: str
   - auto_delete: bool
   - notify_before_delete: bool
   - notify_days_before: int = 7

3. DeletionResult dataclass:
   - data_type: str
   - records_deleted: int
   - storage_freed_bytes: int
   - duration_seconds: float
   - errors: list[str]

4. DataDeletionManager class (in data_deletion.py):
   - request_account_deletion(user_id: str, reason: str) -> DeletionRequest
   - confirm_account_deletion(request_id: str, confirmation_token: str) -> DeletionResult
   - cancel_deletion_request(request_id: str) -> dict
   - get_deletion_requests(status: str, limit: int = 50) -> list[DeletionRequest]
   - execute_hard_delete(user_id: str) -> DeletionResult
   - delete_user_data(user_id: str) -> dict  # deletes: cameras, events, clips, thumbnails, profile, billing
   - delete_firebase_account(uid: str) -> bool
   - export_user_data(user_id: str) -> str  # returns path to GDPR data export ZIP

5. DeletionRequest dataclass:
   - request_id: str
   - user_id: str
   - email: str
   - reason: Optional[str]
   - status: str (pending/confirmed/cancelled/completed)
   - requested_at: datetime
   - confirmed_at: Optional[datetime]
   - completed_at: Optional[datetime]
   - confirmation_token: str
   - expires_at: datetime  # 7 days to confirm

6. PrivacyManager class (in privacy_manager.py):
   - get_privacy_policy(language: str = "en") -> str
   - get_terms_of_service(language: str = "en") -> str
   - record_consent(user_id: str, consent_type: str, granted: bool) -> dict
   - get_user_consents(user_id: str) -> list[ConsentRecord]
   - withdraw_consent(user_id: str, consent_type: str) -> dict
   - generate_dpa(user_id: str, company_name: str) -> str  # Data Processing Agreement

7. ConsentRecord dataclass:
   - user_id: str
   - consent_type: str (cookies/marketing/analytics/third_party)
   - granted: bool
   - granted_at: datetime
   - ip_address: str
   - user_agent: str

8. Cookie Consent Banner (in cookie_consent.html):
   - Banner at bottom of page: "We use cookies to improve your experience."
   - Three buttons: "Accept All", "Reject All", "Customize"
   - Customize modal: toggle for Essential, Analytics, Marketing, Third-party
   - Stores consent in localStorage
   - No tracking scripts loaded unless consent given
   - GDPR-compliant: implied consent not accepted

9. Privacy Policy Page (in privacy_policy.html):
   - Sections: What data we collect, How we use it, Data retention, Your rights (GDPR), Cookies, Third-party services, Contact DPO
   - Last updated date
   - Available in English and Bengali

10. Terms of Service Page (in terms_of_service.html):
    - Sections: Service description, User obligations, Payment terms, Cancellation, Limitation of liability, SLA, Governing law (Bangladesh)
    - Last updated date

TEST CASES:
test_get_retention_policy_returns_correct_days, test_delete_expired_records_removes_old_data, test_run_cleanup_all_processes_all_types, test_request_account_deletion_creates_request, test_confirm_account_deletion_executes_hard_delete, test_cancel_deletion_request_marks_cancelled, test_execute_hard_delete_removes_all_user_data, test_delete_firebase_account_removes_auth, test_export_user_data_creates_zip, test_export_zip_contains_all_data_types, test_record_consent_stores_correctly, test_get_user_consents_returns_list, test_withdraw_consent_updates_record, test_generate_dpa_returns_document, test_cookie_consent_banner_visible_on_load, test_cookie_consent_accept_all_saves_consent, test_cookie_consent_reject_all_blocks_tracking, test_privacy_policy_page_returns_200, test_terms_of_service_page_returns_200, test_privacy_policy_available_in_bengali, test_data_retention_cron_schedules_correctly

OUTPUT: Generate data_retention.py, data_deletion.py, privacy_manager.py, privacy_policy.html, terms_of_service.html, cookie_consent.html, test_data_retention.py, and test_privacy.py. Use async/await throughout.
```

---

## SPRINT 12.8 — Backup, Disaster Recovery & SLA Monitoring
### Files: infrastructure/backup_manager.py, infrastructure/disaster_recovery.py, backend/monitoring/sla_monitor.py
### Tests: backend/tests/unit/test_backup_manager.py, backend/tests/unit/test_sla_monitor.py

```
You are building the backup, disaster recovery, and SLA monitoring system for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + Google Cloud SQL + Cloud Storage + subprocess
- Automated database backups: daily (point-in-time recovery), weekly (full), monthly (archive)
- Backup retention: daily (7 days), weekly (4 weeks), monthly (12 months)
- Disaster Recovery: RPO (Recovery Point Objective) = 1 hour, RTO (Recovery Time Objective) = 4 hours
- DR plan: multi-region failover (asia-south1 → asia-east1)
- SLA monitoring: 99.9% uptime target, monthly reporting
- SLA breach alerts: if uptime drops below 99.9% in any calendar month
- Service credits: 5% credit for <99.9%, 10% for <99.0%, 25% for <95.0%
- Supports 20 cameras per user, DR tested quarterly

KEY DECISIONS:
- D026: All calls async
- Cloud SQL automated backups + custom export to Cloud Storage
- DR tested quarterly with full failover drill
- SLA credits automatically calculated and applied

FUNCTIONS TO IMPLEMENT:

1. BackupManager class (in backup_manager.py):
   - create_daily_backup() -> BackupResult
   - create_weekly_backup() -> BackupResult
   - create_monthly_backup() -> BackupResult
   - list_backups(backup_type: str = None, limit: int = 10) -> list[BackupRecord]
   - restore_from_backup(backup_id: str, target_instance: str) -> RestoreResult
   - verify_backup_integrity(backup_id: str) -> IntegrityResult
   - delete_old_backups() -> dict  # enforces retention policy
   - get_backup_stats() -> BackupStats
   - export_to_cloud_storage(backup_id: str) -> str  # returns GCS path
   - schedule_backup_jobs() -> None

2. BackupRecord dataclass:
   - backup_id: str
   - backup_type: str (daily/weekly/monthly)
   - status: str (running/completed/failed)
   - size_bytes: int
   - database_version: str
   - created_at: datetime
   - completed_at: Optional[datetime]
   - storage_path: str
   - integrity_verified: bool
   - error: Optional[str]

3. BackupResult dataclass:
   - backup_id: str
   - status: str
   - size_bytes: int
   - duration_seconds: float
   - storage_path: str
   - message: str

4. RestoreResult dataclass:
   - restore_id: str
   - backup_id: str
   - target_instance: str
   - status: str
   - duration_seconds: float
   - data_verified: bool
   - error: Optional[str]

5. BackupStats dataclass:
   - total_backups: int
   - total_size_bytes: int
   - last_backup_at: Optional[datetime]
   - last_successful_backup_at: Optional[datetime]
   - backups_by_type: dict
   - storage_cost_estimate_monthly: float

6. DisasterRecovery class (in disaster_recovery.py):
   - run_dr_drill(drill_type: str) -> DrillResult
   - failover_to_region(region: str) -> FailoverResult
   - failback_to_primary() -> FailoverResult
   - get_dr_status() -> DRStatus
   - test_backup_restore(backup_id: str) -> RestoreResult
   - generate_dr_report() -> DRReport
   - schedule_quarterly_drill() -> None

7. DrillResult dataclass:
   - drill_id: str
   - drill_type: str (backup_restore/failover/failback/full)
   - status: str (passed/failed/in_progress)
   - steps_completed: int
   - steps_total: int
   - duration_seconds: float
   - issues_found: list[str]
   - recommendations: list[str]

8. DRStatus dataclass:
   - primary_region: str
   - secondary_region: str
   - last_drill_at: Optional[datetime]
   - last_drill_result: str
   - backup_status: str
   - rpo_achieved_minutes: int
   - rto_achieved_minutes: int
   - overall_health: str (healthy/degraded/unknown)

9. SLAMonitor class (in sla_monitor.py):
   - calculate_monthly_uptime(year: int, month: int) -> float
   - calculate_uptime_since(date: datetime) -> float
   - check_sla_breach() -> SLABreachResult
   - calculate_service_credits(user_id: str, month: str) -> CreditResult
   - apply_service_credits(user_id: str, month: str) -> dict
   - get_sla_report(year: int, month: int) -> SLAReport
   - get_user_sla_credits(user_id: str) -> list[CreditResult]
   - record_downtime(start: datetime, end: datetime, reason: str) -> dict

10. SLAReport dataclass:
    - year: int
    - month: int
    - total_minutes: int
    - downtime_minutes: int
    - uptime_percentage: float
    - sla_target: float  # 99.9
    - sla_met: bool
    - breach_events: list[dict]
    - service_credits_due: float

11. SLABreachResult dataclass:
    - is_breached: bool
    - current_uptime: float
    - sla_target: float
    - projected_uptime: float  # if month continues at current rate
    - breach_severity: str (none/warning/critical)
    - recommended_action: str

12. CreditResult dataclass:
    - user_id: str
    - month: str
    - uptime_percentage: float
    - credit_percentage: float
    - credit_amount_bdt: float
    - applied: bool
    - applied_at: Optional[datetime]

TEST CASES:
test_create_daily_backup_returns_backup_id, test_create_weekly_backup_success, test_list_backups_returns_sorted_list, test_restore_from_backup_completes, test_verify_backup_integrity_valid, test_delete_old_backups_removes_expired, test_get_backup_stats_returns_metrics, test_export_to_cloud_storage_succeeds, test_run_dr_drill_passes_all_steps, test_failover_to_region_switches_traffic, test_failback_to_primary_restores, test_get_dr_status_returns_health, test_calculate_monthly_uptime_99_9, test_check_sla_breach_no_breach, test_check_sla_breach_detects_breach, test_calculate_service_credits_correct_amount, test_apply_service_credits_updates_account, test_get_sla_report_contains_all_fields, test_record_downtime_logs_event, test_schedule_quarterly_drill_creates_calendar_event

OUTPUT: Generate backup_manager.py, disaster_recovery.py, sla_monitor.py, test_backup_manager.py, and test_sla_monitor.py. Use async/await throughout.
```

---

## SPRINT 12.9 — Tenant Isolation, Audit Trail & Feature Flags
### Files: backend/core/tenant_isolation.py, backend/core/audit_trail.py, backend/core/feature_flags.py
### Tests: backend/tests/unit/test_tenant_isolation.py, backend/tests/unit/test_audit_trail.py, backend/tests/unit/test_feature_flags.py

```
You are building tenant isolation, audit trail, and feature flag systems for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async + Redis
- Tenant isolation: strict data separation between users (no cross-tenant data access)
- Row-Level Security (RLS) enforced at database level + application level
- Audit trail: immutable log of all admin actions, user data changes, security events
- Audit log retention: 7 years (for compliance)
- Feature flags: gradual rollout, A/B testing, kill switches for AI features
- Feature flags stored in Redis (fast access) with DB fallback
- Supports 20 cameras per user, 100+ tenants

KEY DECISIONS:
- D026: All calls async
- Tenant isolation via user_id foreign key on all tables (application-level)
- Audit trail is append-only (immutable)
- Feature flags in Redis for sub-10ms lookup

FUNCTIONS TO IMPLEMENT:

1. TenantIsolationMiddleware class (in tenant_isolation.py):
   - verify_tenant_access(user_id: str, resource_owner_id: str) -> bool
   - enforce_tenant_isolation(query: Query, user_id: str) -> Query  # adds WHERE user_id=
   - get_tenant_context(request: Request) -> TenantContext
   - tenant_isolation_middleware(app: FastAPI) -> None
   - verify_bulk_tenant_access(user_id: str, owner_ids: list[str]) -> list[str]  # returns authorized IDs

2. TenantContext dataclass:
   - user_id: str
   - email: str
   - tier: str
   - is_admin: bool
   - ip_address: str
   - request_id: str

3. AuditTrail class (in audit_trail.py):
   - record_action(action: str, actor_id: str, resource_type: str, resource_id: str, details: dict) -> str
   - get_audit_logs(filters: AuditFilter) -> list[AuditEntry]
   - get_audit_log_by_id(log_id: str) -> Optional[AuditEntry]
   - export_audit_logs(filters: AuditFilter, format: str = "csv") -> str  # returns file path
   - get_audit_stats(since: datetime) -> AuditStats
   - verify_audit_integrity() -> IntegrityResult  # checks for tampering
   - archive_old_logs(before: datetime) -> int  # moves to cold storage

4. AuditEntry dataclass:
   - log_id: str
   - timestamp: datetime
   - action: str (user_signup/camera_added/event_triggered/payment_processed/admin_action/data_deletion/security_event)
   - actor_id: str
   - actor_email: str
   - resource_type: str (user/camera/event/payment/subscription/admin)
   - resource_id: str
   - details: dict  # JSON blob with before/after values
   - ip_address: str
   - user_agent: str
   - request_id: str
   - integrity_hash: str  # SHA-256 of previous entry + this entry (blockchain-style)

5. AuditFilter dataclass:
   - action: Optional[str]
   - actor_id: Optional[str]
   - resource_type: Optional[str]
   - resource_id: Optional[str]
   - start_date: Optional[datetime]
   - end_date: Optional[datetime]
   - limit: int = 100
   - offset: int = 0

6. AuditStats dataclass:
   - total_entries: int
   - entries_by_action: dict
   - entries_by_resource: dict
   - unique_actors: int
   - oldest_entry: datetime
   - newest_entry: datetime
   - integrity_verified: bool

7. FeatureFlagManager class (in feature_flags.py):
   - get_flag(flag_name: str, user_id: str = None) -> bool
   - set_flag(flag_name: str, value: bool, description: str = "") -> dict
   - set_user_override(flag_name: str, user_id: str, value: bool) -> dict
   - remove_user_override(flag_name: str, user_id: str) -> dict
   - get_all_flags() -> list[FeatureFlag]
   - get_flag_history(flag_name: str) -> list[FlagChange]
   - delete_flag(flag_name: str) -> dict
   - get_flags_for_user(user_id: str) -> dict[str, bool]

8. FeatureFlag dataclass:
   - flag_name: str
   - enabled: bool
   - description: str
   - rollout_percentage: int  # 0-100 for gradual rollout
   - created_at: datetime
   - updated_at: datetime
   - updated_by: str

9. FlagChange dataclass:
   - flag_name: str
   - old_value: bool
   - new_value: bool
   - changed_by: str
   - changed_at: datetime
   - reason: str

10. Default Feature Flags:
    - ai_enhanced_detection: True
    - audio_intelligence: True
    - cross_camera_tracking: True
    - natural_language_search: True
    - telegram_alerts: True
    - clip_recording: True
    - advanced_analytics: True  # business tier only
    - maintenance_mode: False  # kill switch for all non-admin access
    - new_onboarding_flow: False  # for A/B testing

TEST CASES:
test_verify_tenant_access_own_resource_returns_true, test_verify_tenant_access_other_resource_returns_false, test_enforce_tenant_isolation_adds_where_clause, test_get_tenant_context_from_request, test_verify_bulk_tenant_access_filters_correctly, test_record_action_creates_audit_entry, test_get_audit_logs_filters_by_action, test_get_audit_log_by_id_returns_entry, test_export_audit_logs_creates_csv, test_get_audit_stats_returns_counts, test_verify_audit_integrity_no_tampering, test_verify_audit_integrity_detects_tampering, test_archive_old_logs_moves_to_cold_storage, test_get_flag_returns_default_value, test_set_flag_updates_value, test_set_user_override_overrides_global, test_remove_user_override_restores_global, test_get_all_flags_returns_list, test_get_flag_history_tracks_changes, test_maintenance_mode_blocks_non_admin, test_rollout_percentage_gradually_enables

OUTPUT: Generate tenant_isolation.py, audit_trail.py, feature_flags.py, test_tenant_isolation.py, test_audit_trail.py, and test_feature_flags.py. Use async/await throughout.
```

---

## SPRINT 12.10 — Customer Support Ticketing & In-App Help
### Files: backend/support/ticket_system.py, backend/support/knowledge_base.py, backend/support/live_chat.py, backend/dashboard/templates/support.html, backend/dashboard/templates/support_ticket.html, backend/dashboard/static/support.js, backend/dashboard/static/support.css
### Tests: backend/tests/unit/test_support.py

```
You are building the customer support system for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async + Jinja2 + WebSocket
- Support ticket system: create, update, comment, close tickets
- Knowledge base: searchable help articles (extends Sprint 11.4)
- Live chat: WebSocket-based real-time chat with support agents
- Ticket priorities: low, medium, high, critical
- Ticket categories: billing, technical, account, feature request, bug report
- Auto-categorization using AI (Gemini)
- Email notifications on ticket updates
- SLA for tickets: critical (1hr), high (4hr), medium (24hr), low (72hr)
- Supports 20 cameras per user, ticket history retained for 2 years

KEY DECISIONS:
- D026: All calls async
- WebSocket for live chat (scalable via Cloud Run)
- AI auto-categorization using Gemini API
- Ticket SLA enforced by alert system

FUNCTIONS TO IMPLEMENT:

1. TicketSystem class (in ticket_system.py):
   - create_ticket(user_id: str, subject: str, description: str, category: str, priority: str) -> Ticket
   - get_ticket(ticket_id: str) -> Optional[Ticket]
   - get_user_tickets(user_id: str, status: str = None, limit: int = 20) -> list[Ticket]
   - get_all_tickets(filters: TicketFilter) -> list[Ticket]
   - update_ticket(ticket_id: str, admin_id: str, updates: dict) -> Ticket
   - add_comment(ticket_id: str, user_id: str, comment: str, is_internal: bool = False) -> Comment
   - close_ticket(ticket_id: str, user_id: str, resolution: str) -> Ticket
   - reopen_ticket(ticket_id: str, user_id: str, reason: str) -> Ticket
   - assign_ticket(ticket_id: str, admin_id: str) -> Ticket
   - escalate_ticket(ticket_id: str, reason: str) -> Ticket
   - auto_categorize(subject: str, description: str) -> str  # uses Gemini
   - check_ticket_sla() -> list[SLABreach]
   - get_ticket_stats(since: datetime) -> TicketStats

2. Ticket dataclass:
   - ticket_id: str
   - user_id: str
   - subject: str
   - description: str
   - category: str (billing/technical/account/feature_request/bug)
   - priority: str (low/medium/high/critical)
   - status: str (open/in_progress/waiting_on_customer/resolved/closed)
   - assigned_to: Optional[str]
   - created_at: datetime
   - updated_at: datetime
   - resolved_at: Optional[datetime]
   - closed_at: Optional[datetime]
   - sla_deadline: datetime
   - sla_breached: bool
   - resolution: Optional[str]
   - comments: list[Comment]

3. Comment dataclass:
   - comment_id: str
   - ticket_id: str
   - user_id: str
   - content: str
   - is_internal: bool  # only visible to admins
   - created_at: datetime

4. TicketFilter dataclass:
   - status: Optional[str]
   - priority: Optional[str]
   - category: Optional[str]
   - assigned_to: Optional[str]
   - user_id: Optional[str]
   - created_after: Optional[datetime]
   - created_before: Optional[datetime]
   - sla_breached: Optional[bool]
   - limit: int = 20
   - offset: int = 0

5. TicketStats dataclass:
   - total_open: int
   - total_in_progress: int
   - total_resolved_today: int
   - avg_resolution_time_hours: float
   - sla_compliance_pct: float
   - tickets_by_category: dict
   - tickets_by_priority: dict
   - breached_sla_count: int

6. KnowledgeBase class (in knowledge_base.py):
   - search_articles(query: str, category: str = None) -> list[Article]
   - get_article(article_id: str) -> Optional[Article]
   - get_popular_articles(limit: int = 10) -> list[Article]
   - get_articles_by_category(category: str) -> list[Article]
   - record_article_view(article_id: str, user_id: str) -> dict
   - record_article_feedback(article_id: str, helpful: bool) -> dict
   - suggest_articles(ticket_subject: str) -> list[Article]  # AI-powered suggestions

7. LiveChat class (in live_chat.py):
   - start_chat_session(user_id: str) -> ChatSession
   - send_message(session_id: str, user_id: str, message: str) -> ChatMessage
   - get_chat_history(session_id: str) -> list[ChatMessage]
   - assign_agent(session_id: str, agent_id: str) -> dict
   - end_chat_session(session_id: str) -> dict
   - get_active_sessions() -> list[ChatSession]
   - transfer_session(session_id: str, to_agent_id: str) -> dict
   - generate_chat_transcript(session_id: str) -> str

8. ChatSession dataclass:
   - session_id: str
   - user_id: str
   - agent_id: Optional[str]
   - status: str (waiting/active/ended)
   - started_at: datetime
   - ended_at: Optional[datetime]
   - unread_count: int

9. Support UI Pages:
   - support.html: Support center with ticket list, knowledge base search, live chat button
   - support_ticket.html: Individual ticket view with comments, status, SLA timer
   - support.js: Ticket CRUD, live chat WebSocket client, knowledge base search
   - support.css: Matching dark navy theme

TEST CASES:
test_create_ticket_returns_ticket_with_id, test_get_ticket_returns_correct_ticket, test_get_user_tickets_returns_filtered_list, test_update_ticket_changes_status, test_add_comment_appends_to_ticket, test_close_ticket_marks_resolved, test_reopen_ticket_reactivates, test_assign_ticket_updates_assignee, test_escalate_ticket_increases_priority, test_auto_categorize_uses_ai, test_check_ticket_sla_detects_breach, test_get_ticket_stats_returns_metrics, test_search_articles_returns_relevant, test_get_popular_articles_returns_top, test_suggest_articles_for_ticket, test_start_chat_session_creates_session, test_send_message_stores_message, test_get_chat_history_returns_ordered, test_assign_agent_updates_session, test_end_chat_session_closes, test_support_page_loads, test_ticket_page_shows_sla_timer

OUTPUT: Generate ticket_system.py, knowledge_base.py, live_chat.py, support.html, support_ticket.html, support.js, support.css, and test_support.py. Use async/await throughout.
```

---

## SPRINT 12.11 — Webhook System, Data Export & Status Page
### Files: backend/core/webhook_manager.py, backend/api/data_export.py, backend/dashboard/templates/status.html, backend/dashboard/static/status.js, backend/dashboard/static/status.css
### Tests: backend/tests/unit/test_webhooks.py, backend/tests/unit/test_data_export.py, backend/tests/unit/test_status_page.py

```
You are building the webhook system, data export API, and public status page for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + Python asyncio + SQLAlchemy async + Jinja2
- Webhooks: event-driven notifications to external URLs (e.g., Discord, Slack, custom servers)
- Webhook events: camera_offline, camera_online, threat_detected, motion_detected, person_identified, alert_triggered
- Webhook retry: 3 retries with exponential backoff (5s, 30s, 300s)
- Webhook signing: HMAC-SHA256 signature for payload verification
- Data export: GDPR-compliant user data export (ZIP with JSON/CSV)
- Data export includes: profile, cameras, events, clips metadata, billing history
- Status page: public page showing system status (operational/degraded/down)
- Status page: shows uptime for last 90 days, incident history
- Supports 20 cameras per user, webhook rate limited to 1000/hr per user

KEY DECISIONS:
- D026: All calls async
- Webhook payloads signed with HMAC-SHA256
- Status page is public (no auth required)
- Data export runs as async background task

FUNCTIONS TO IMPLEMENT:

1. WebhookManager class (in webhook_manager.py):
   - register_webhook(user_id: str, url: str, events: list[str], secret: str = None) -> Webhook
   - update_webhook(webhook_id: str, updates: dict) -> Webhook
   - delete_webhook(webhook_id: str) -> dict
   - get_user_webhooks(user_id: str) -> list[Webhook]
   - trigger_webhook(webhook_id: str, event: str, payload: dict) -> WebhookDelivery
   - trigger_event(event: str, user_id: str, payload: dict) -> list[WebhookDelivery]
   - retry_delivery(delivery_id: str) -> WebhookDelivery
   - get_delivery_logs(webhook_id: str, limit: int = 20) -> list[WebhookDelivery]
   - get_webhook_stats(user_id: str) -> WebhookStats
   - verify_signature(payload: dict, signature: str, secret: str) -> bool

2. Webhook dataclass:
   - webhook_id: str
   - user_id: str
   - url: str
   - events: list[str]
   - secret: str  # auto-generated if not provided
   - is_active: bool
   - created_at: datetime
   - last_triggered_at: Optional[datetime]
   - last_success_at: Optional[datetime]
   - failure_count: int

3. WebhookDelivery dataclass:
   - delivery_id: str
   - webhook_id: str
   - event: str
   - payload: dict
   - status: str (success/failed/retrying)
   - attempt: int
   - max_attempts: int = 3
   - response_status_code: Optional[int]
   - response_body: Optional[str]
   - duration_ms: float
   - error: Optional[str]
   - created_at: datetime
   - next_retry_at: Optional[datetime]

4. WebhookStats dataclass:
   - total_webhooks: int
   - active_webhooks: int
   - total_deliveries: int
   - successful_deliveries: int
   - failed_deliveries: int
   - success_rate_pct: float
   - avg_delivery_time_ms: float
   - deliveries_last_24h: int

5. DataExportManager class (in data_export.py):
   - request_data_export(user_id: str) -> ExportRequest
   - get_export_status(request_id: str) -> ExportStatus
   - download_export(request_id: str, user_id: str) -> Optional[str]  # returns signed URL
   - cancel_export(request_id: str) -> dict
   - get_user_exports(user_id: str) -> list[ExportRequest]
   - execute_export(request_id: str) -> str  # background task, returns file path
   - cleanup_old_exports(days: int = 7) -> int

6. ExportRequest dataclass:
   - request_id: str
   - user_id: str
   - status: str (pending/processing/completed/failed)
   - requested_at: datetime
   - completed_at: Optional[datetime]
   - file_size_bytes: Optional[int]
   - download_url: Optional[str]
   - expires_at: Optional[datetime]  # 48 hours
   - error: Optional[str]

7. ExportStatus dataclass:
   - request_id: str
   - status: str
   - progress_pct: float
   - estimated_completion: Optional[datetime]
   - message: str

8. Data Export Contents (ZIP file):
   - profile.json: user profile data
   - cameras.json: all
