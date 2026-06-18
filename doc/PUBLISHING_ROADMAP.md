# Vision OS — Complete SaaS Publishing Roadmap (MEGA.nz Edition)
# From Code to Live Production: MEGA.nz as Backend Storage

**Date**: May 1, 2026
**Author**: Vision OS Engineering
**Status**: ⬜ Not Started | 🔄 In Progress | ✅ Complete

---

## 📋 EXECUTIVE SUMMARY

Vision OS has **all planning complete** and **V1 backend code implemented**. This roadmap uses **MEGA.nz as the backend storage** instead of PostgreSQL/Cloud SQL — dramatically reducing infrastructure complexity, cost, and setup time.

### 🎯 Why MEGA.nz Instead of a Database?

| Requirement | PostgreSQL (Old Plan) | MEGA.nz (New Plan) |
|-------------|----------------------|---------------------|
| **Setup time** | 2-3 hours (Cloud SQL, VPC, migrations) | 5 minutes (create account) |
| **Monthly cost** | $15-25/month | $0 (free 20GB) |
| **Backup** | Complex (Cloud SQL backups) | Built-in (MEGA version history) |
| **Visualization** | Need separate BI tool | CSV export → Looker Studio |
| **Manual inspection** | Need SQL client | Open JSON in any text editor |
| **Scaling** | Need connection pooling | MEGA handles it automatically |

### Current State Assessment

| Area | Status | Details |
|------|--------|---------|
| **Architecture & Planning** | ✅ 100% | All docs finalized |
| **V1 Backend Core** | ✅ Complete | Database, Auth, AI Client, API stubs, CI/CD |
| **V10 Prompt Files** | ✅ Complete | All prompts written |
| **V10 Code Implementation** | ✅ ~30% | camera_limits, security_middleware, api_key_manager, firebase_rules, readiness_check, deploy.sh, Dockerfile, e2e tests |
| **V11 Prompt Files (MEGA.nz Integration)** | ✅ NEW | 8 sprints covering MegaClient, CRUD, API, dashboard, backup, analytics, client agent, billing |
| **Client Agent (connect/)** | ⬜ Not started | RTSP reader, motion detector, transport |
| **Core Intelligence** | ⬜ Not started | Incident tracker, camera modes, Re-ID engine |
| **V6-V9 Features** | ⬜ Not started | Multi-camera, subscription, admin, launch features |
| **Manual Setup Guide** | ✅ NEW | doc/MANUAL_SETUP_STEPS.md — 13 steps, 2-3 hours |
| **Visualization Guide** | ✅ NEW | Looker Studio dashboard setup in MANUAL_SETUP_STEPS.md |

---

## 🗺️ PHASE 1: COMPLETE V10 CODING (Weeks 1-2)

> **Goal**: Generate all missing V10 code from the prompt files using DeepSeek

### Sprint 12.1 — Camera Capacity Upgrade (10→20) ✅ DONE
- [x] `backend/core/camera_limits.py` — CameraLimits class, ValidationResult, QuotaInfo
- [x] `backend/tests/unit/test_camera_limits.py` — 13 test cases

### Sprint 12.2 — Global Deployment Pipeline ✅ DONE
- [x] `infrastructure/deploy.sh` — One-command deployment script
- [x] `Dockerfile` — Multi-stage build (<200MB)
- [x] `.github/workflows/deploy.yml` — CI/CD pipeline
- [x] `infrastructure/secrets_setup.py` — Secret Manager bootstrap
- [x] `infrastructure/test_deploy_pipeline.py` — 15 test cases

### Sprint 12.3 — Public Access Hardening ✅ DONE
- [x] `backend/core/security_middleware.py` — CORS, rate limiting, HTTPS redirect, security headers
- [x] `backend/core/firebase_rules.json` — Firebase Security Rules
- [x] `backend/core/api_key_manager.py` — API key lifecycle management
- [x] `backend/tests/unit/test_security_middleware.py` — 18 test cases

### Sprint 12.4 — End-to-End Smoke Test Suite ✅ DONE
- [x] `backend/tests/e2e/conftest.py` — Test fixtures
- [x] `backend/tests/e2e/test_full_journey.py` — Complete user lifecycle (20 tests)
- [x] `backend/tests/e2e/test_20_cameras.py` — 20-camera capacity verification (10 tests)

### Sprint 12.5 — Production Readiness Checker ✅ DONE
- [x] `infrastructure/readiness_check.py` — 60+ checks across 12 categories
- [x] `backend/tests/unit/test_readiness_check.py` — 21 test cases

### Sprint 12.6 — Launch Day Operations Runbook ✅ DONE
- [x] `doc/LAUNCH_RUNBOOK.md` — Complete runbook with pre-launch, timeline, incident response, rollback

### Sprint 12.7 — Data Retention, Privacy & GDPR/DPDP Compliance ⬜ NEEDS CODING
- [ ] `backend/core/data_retention.py` — DataRetentionManager, RetentionPolicy, DeletionResult
- [ ] `backend/core/data_deletion.py` — DataDeletionManager, DeletionRequest, GDPR right to erasure
- [ ] `backend/core/privacy_manager.py` — PrivacyManager, ConsentRecord, DPA generation
- [ ] `backend/dashboard/templates/privacy_policy.html` — Privacy policy page (EN + Bengali)
- [ ] `backend/dashboard/templates/terms_of_service.html` — Terms of service page
- [ ] `backend/dashboard/templates/cookie_consent.html` — GDPR-compliant cookie consent banner
- [ ] `backend/tests/unit/test_data_retention.py` — Test cases
- [ ] `backend/tests/unit/test_privacy.py` — Test cases

### Sprint 12.8 — Backup, Disaster Recovery & SLA Monitoring ⬜ NEEDS CODING
- [ ] `infrastructure/backup_manager.py` — BackupManager, BackupRecord, automated backups
- [ ] `infrastructure/disaster_recovery.py` — DisasterRecovery, DR drills, failover/failback
- [ ] `backend/monitoring/sla_monitor.py` — SLAMonitor, SLA reports, service credits
- [ ] `backend/tests/unit/test_backup_manager.py` — Test cases
- [ ] `backend/tests/unit/test_sla_monitor.py` — Test cases

### Sprint 12.9 — Tenant Isolation, Audit Trail & Feature Flags ⬜ NEEDS CODING
- [ ] `backend/core/tenant_isolation.py` — TenantIsolationMiddleware, TenantContext
- [ ] `backend/core/audit_trail.py` — AuditTrail, AuditEntry (blockchain-style integrity hashes)
- [ ] `backend/core/feature_flags.py` — FeatureFlagManager, gradual rollout, A/B testing
- [ ] `backend/tests/unit/test_tenant_isolation.py` — Test cases
- [ ] `backend/tests/unit/test_audit_trail.py` — Test cases
- [ ] `backend/tests/unit/test_feature_flags.py` — Test cases

### Sprint 12.10 — Customer Support Ticketing & In-App Help ⬜ NEEDS CODING
- [ ] `backend/support/ticket_system.py` — TicketSystem, Ticket, Comment, SLA enforcement
- [ ] `backend/support/knowledge_base.py` — KnowledgeBase, Article search, AI suggestions
- [ ] `backend/support/live_chat.py` — LiveChat, WebSocket-based real-time chat
- [ ] `backend/dashboard/templates/support.html` — Support center page
- [ ] `backend/dashboard/templates/support_ticket.html` — Individual ticket view
- [ ] `backend/dashboard/static/support.js` — Support UI JavaScript
- [ ] `backend/dashboard/static/support.css` — Support UI styles
- [ ] `backend/tests/unit/test_support.py` — Test cases

### Sprint 12.11 — Webhook System, Data Export & Status Page ⬜ NEEDS CODING
- [ ] `backend/core/webhook_manager.py` — WebhookManager, WebhookDelivery, HMAC signing
- [ ] `backend/api/data_export.py` — DataExportManager, GDPR-compliant ZIP export
- [ ] `backend/dashboard/templates/status.html` — Public status page
- [ ] `backend/dashboard/static/status.js` — Status page JavaScript
- [ ] `backend/dashboard/static/status.css` — Status page styles
- [ ] `backend/tests/unit/test_webhooks.py` — Test cases
- [ ] `backend/tests/unit/test_data_export.py` — Test cases
- [ ] `backend/tests/unit/test_status_page.py` — Test cases

---

## 🗺️ PHASE 1B: V11 MEGA.nz INTEGRATION (Weeks 2-3)

> **Goal**: Replace PostgreSQL with MEGA.nz as the backend storage layer

### Sprint 11.1 — MEGA.nz API Client ⬜ NEEDS CODING
- [ ] `backend/storage/mega_client.py` — MegaClient, MegaCache, PathBuilder
- [ ] `backend/storage/mega_schema.py` — FileInfo, CacheStats dataclasses
- [ ] `backend/tests/unit/test_mega_client.py` — 24 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.1

### Sprint 11.2 — MEGA.nz CRUD Operations ⬜ NEEDS CODING
- [ ] `backend/storage/mega_crud.py` — UserCRUD, CameraCRUD, EventCRUD, BillingCRUD, AuditCRUD, IndexManager
- [ ] `backend/tests/unit/test_mega_crud.py` — 25 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.2

### Sprint 11.3 — Simplified API Layer (MEGA-Backed) ⬜ NEEDS CODING
- [ ] `backend/api/cameras.py` — Camera endpoints (MEGA-backed)
- [ ] `backend/api/users.py` — User endpoints (MEGA-backed)
- [ ] `backend/api/triggers.py` — Trigger endpoints (MEGA-backed)
- [ ] `backend/api/queries.py` — Query endpoints (MEGA-backed)
- [ ] `backend/tests/unit/test_api_mega.py` — 21 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.3

### Sprint 11.4 — Simplified Dashboard (MEGA-Backed) ⬜ NEEDS CODING
- [ ] `backend/dashboard/server.py` — FastAPI app with MegaClient init
- [ ] `backend/dashboard/routes.py` — Dashboard routes
- [ ] `backend/dashboard/templates/dashboard.html` — Main dashboard
- [ ] `backend/dashboard/templates/index.html` — Landing page
- [ ] `backend/tests/unit/test_dashboard_mega.py` — 11 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.4

### Sprint 11.5 — MEGA.nz Backup & Data Export ⬜ NEEDS CODING
- [ ] `backend/storage/mega_backup.py` — MegaBackup, backup/restore
- [ ] `backend/api/data_export.py` — DataExportManager, GDPR ZIP export
- [ ] `backend/tests/unit/test_mega_backup.py` — 17 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.5

### Sprint 11.6 — MEGA.nz Analytics & CSV Export ⬜ NEEDS CODING
- [ ] `backend/analytics/mega_analytics.py` — MegaAnalytics, DailyStats, CSV generation
- [ ] `backend/api/analytics.py` — Analytics API endpoints
- [ ] `backend/tests/unit/test_mega_analytics.py` — 12 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.6

### Sprint 11.7 — Simplified Client Agent (MEGA-Backed) ⬜ NEEDS CODING
- [ ] `connect/camera/rtsp_reader.py` — RTSP stream reader
- [ ] `connect/camera/motion_detector.py` — OpenCV motion detection
- [ ] `connect/transport/trigger_sender.py` — Send triggers to API
- [ ] `connect/tests/test_client_mega.py` — 16 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.7

### Sprint 11.8 — Simplified Subscription & Billing (MEGA-Backed) ⬜ NEEDS CODING
- [ ] `backend/billing/subscription_manager.py` — Subscription management
- [ ] `backend/billing/payment_processor.py` — bKash/Nagad integration
- [ ] `backend/billing/trial_manager.py` — Free trial management
- [ ] `backend/tests/unit/test_billing_mega.py` — 19 test cases
- **Prompt**: `doc/DEEPSEEK_PROMPTS_V11.md` → Sprint 11.8

---

## 🗺️ PHASE 2: CLIENT AGENT — connect/ (Weeks 4-5)

> **Goal**: Build the Windows client agent that runs on user's PC to capture camera feeds

### Sprint 2.1 — RTSP Reader + Frame Selector ⬜ NEEDS CODING
- [ ] `connect/camera/rtsp_reader.py` — RTSP stream reader with reconnection
- [ ] `connect/camera/frame_selector.py` — Smart frame selection (key frames, motion frames)
- [ ] `connect/tests/test_camera.py` — Test cases

### Sprint 2.2 — Motion Detector ⬜ NEEDS CODING
- [ ] `connect/camera/motion_detector.py` — OpenCV-based motion detection
- [ ] `connect/tests/test_motion.py` — Test cases

### Sprint 2.3 — YAMNet Audio Detector ⬜ NEEDS CODING
- [ ] `connect/audio/yamnet_detector.py` — YAMNet-based audio event detection
- [ ] `connect/audio/audio_capture.py` — Audio capture from microphone
- [ ] `connect/tests/test_audio.py` — Test cases

### Sprint 2.4 — Transport + Buffer ⬜ NEEDS CODING
- [ ] `connect/transport/trigger_sender.py` — Send triggers to backend API
- [ ] `connect/transport/websocket_client.py` — WebSocket for real-time events
- [ ] `connect/transport/sms_sender.py` — Direct SMS sending
- [ ] `connect/buffer/local_queue.py` — Local buffer for offline resilience
- [ ] `connect/tests/test_transport.py` — Test cases

### Sprint 2.5 — Windows App Packaging ⬜ NEEDS CODING
- [ ] `connect/ui/tray_app.py` — Windows system tray application
- [ ] `connect/main.py` — Main entry point with config loading
- [ ] `connect/config.py` — Client configuration
- [ ] `setup.py` / `pyinstaller.spec` — Windows executable packaging

---

## 🗺️ PHASE 3: CORE INTELLIGENCE — backend/ (Weeks 6-8)

> **Goal**: Build the AI-powered intelligence engine

### Sprint 3.1 — Incident Tracker ⬜ NEEDS CODING
- [ ] `backend/core/incident_tracker.py` — Incident detection, tracking, state machine

### Sprint 3.2 — Camera Modes ⬜ NEEDS CODING
- [ ] `backend/modes/indoor_mode.py` — Indoor-specific detection logic
- [ ] `backend/modes/outdoor_mode.py` — Outdoor-specific detection logic
- [ ] `backend/modes/parking_mode.py` — Parking lot detection logic
- [ ] `backend/modes/shop_mode.py` — Retail shop detection logic
- [ ] `backend/modes/mixed_mode.py` — Mixed/hybrid mode

### Sprint 3.3 — Re-ID Engine ⬜ NEEDS CODING
- [ ] `backend/ai/reid_engine.py` — Person re-identification across cameras

### Sprint 3.4 — Cross-Camera + Ghost Detection ⬜ NEEDS CODING
- [ ] `backend/core/cross_camera.py` — Cross-camera tracking
- [ ] `backend/core/ghost_detector.py` — Ghost detection (false positive reduction)

### Sprint 3.5 — Alert Router + Telegram ⬜ NEEDS CODING
- [ ] `backend/alerts/alert_router.py` — Alert routing logic
- [ ] `backend/alerts/telegram_client.py` — Telegram bot integration
- [ ] `backend/alerts/sms_client.py` — SMS alerts via SSL Wireless
- [ ] `backend/alerts/voice_note.py` — Emergency voice notes via Kokoro TTS

### Sprint 3.6 — Pipeline Orchestrator ⬜ NEEDS CODING
- [ ] `backend/core/pipeline.py` — End-to-end pipeline orchestration

---

## 🗺️ PHASE 4: V6-V9 FEATURES (Weeks 9-12)

> **Goal**: Multi-camera management, subscription, production deployment, launch features

### V6 — Multi-Camera Management ⬜ NEEDS CODING
- [ ] `backend/core/camera_health.py` — Camera health monitoring
- [ ] `backend/analytics/camera_metrics.py` — Camera metrics & analytics
- [ ] `backend/api/admin_cameras.py` — Admin camera management API
- [ ] `backend/dashboard/templates/admin_cameras.html` — Admin camera UI
- [ ] `backend/core/bulk_operations.py` — Bulk camera operations

### V7 — Onboarding & Subscription ⬜ NEEDS CODING
- [ ] `backend/core/onboarding.py` — User onboarding flow
- [ ] `backend/billing/subscription_manager.py` — Subscription management
- [ ] `backend/billing/payment_processor.py` — bKash/Nagad payment integration
- [ ] `backend/billing/trial_manager.py` — Free trial management
- [ ] `backend/analytics/usage_tracker.py` — Usage tracking & limits

### V8 — Production Deployment ⬜ NEEDS CODING
- [ ] `infrastructure/autoscaling.py` — Auto-scaling configuration
- [ ] `infrastructure/load_balancer.py` — Load balancer setup
- [ ] `backend/storage/connection_pool.py` — Database connection pooling
- [ ] `backend/storage/cdn_manager.py` — CDN integration for static assets
- [ ] `backend/monitoring/metrics_collector.py` — Monitoring & alerting

### V9 — Launch Features ⬜ NEEDS CODING
- [ ] `backend/dashboard/templates/landing.html` — Public landing page
- [ ] `backend/api/public_signup.py` — Self-service signup
- [ ] `backend/notifications/email_service.py` — Email notifications (SendGrid)
- [ ] `backend/dashboard/templates/help.html` — Help center & documentation
- [ ] `backend/dashboard/templates/admin_analytics.html` — Admin analytics dashboard

---

## 🗺️ PHASE 5: INFRASTRUCTURE & DEVOPS (Weeks 13-14)

> **Goal**: Set up actual cloud infrastructure and make the app publicly accessible

### Google Cloud Platform Setup
- [ ] Create GCP project (vision-os-platform)
- [ ] Enable required APIs (Cloud Run, Cloud SQL, Secret Manager, Artifact Registry, Cloud Monitoring)
- [ ] Set up billing account and budget alerts
- [ ] Create service accounts with minimal permissions
- [ ] Set up VPC connector for Cloud SQL access

### Database Setup
- [ ] Provision Cloud SQL PostgreSQL instance (minimal: db-f1-micro for launch)
- [ ] Enable pgvector extension
- [ ] Configure connection pooling (PgBouncer or built-in)
- [ ] Set up automated backups (daily)
- [ ] Configure read replica (optional for launch)

### Domain & SSL
- [ ] Register domain (e.g., visionos.bd or visionos.com)
- [ ] Set up Cloud DNS
- [ ] Provision SSL certificate (Google-managed)
- [ ] Configure custom domain mapping on Cloud Run
- [ ] Set up CDN (Cloud CDN) for static assets

### Firebase Setup
- [ ] Create Firebase project (linked to GCP)
- [ ] Enable Email/Password authentication
- [ ] Download service account JSON
- [ ] Configure Firebase Security Rules (from firebase_rules.json)
- [ ] Set up Firebase Realtime Database or Firestore

### Payment Gateway Setup
- [ ] Register for bKash Merchant API (sandbox first)
- [ ] Register for Nagad Merchant API (sandbox first)
- [ ] Configure webhook endpoints for payment callbacks
- [ ] Test payment flow end-to-end with 1 BDT transactions

### Monitoring & Alerting
- [ ] Set up Google Cloud Monitoring dashboards
- [ ] Configure uptime checks (every 5 minutes)
- [ ] Set up alert policies (PagerDuty or email)
- [ ] Configure log-based metrics
- [ ] Set up error reporting

---

## 🗺️ PHASE 6: PRE-LAUNCH QUALITY ASSURANCE (Week 15)

> **Goal**: Ensure everything works before public launch

### Security Audit
- [ ] Run security scan (gcloud beta scanners scan)
- [ ] Test rate limiting (attempt 100+ requests/min)
- [ ] Verify HTTPS redirect works
- [ ] Test Firebase Security Rules
- [ ] Verify API key authentication
- [ ] Test SQL injection protection
- [ ] Test XSS protection
- [ ] Verify CORS configuration
- [ ] Test cookie consent banner

### Performance Testing
- [ ] Run load test with 50 concurrent users (k6)
- [ ] Measure API p95 latency (< 500ms target)
- [ ] Test database query performance (< 100ms)
- [ ] Test static asset loading (< 200ms)
- [ ] Simulate 20 concurrent camera connections
- [ ] Test cold start time (< 1.5s)
- [ ] Verify auto-scaling works

### Payment Testing
- [ ] Test bKash payment flow (sandbox)
- [ ] Test Nagad payment flow (sandbox)
- [ ] Test subscription upgrade/downgrade
- [ ] Test free trial expiration
- [ ] Test payment failure handling
- [ ] Verify billing history is accurate

### Compliance Verification
- [ ] Test GDPR data deletion (right to erasure)
- [ ] Test GDPR data export
- [ ] Verify privacy policy page loads
- [ ] Verify terms of service page loads
- [ ] Test cookie consent banner functionality
- [ ] Verify audit trail is recording
- [ ] Test data retention policies

### E2E Smoke Tests
- [ ] Run `pytest backend/tests/e2e/ -v` against staging
- [ ] Verify full user journey (signup → add camera → trigger event → view dashboard)
- [ ] Verify 20-camera capacity limit
- [ ] Test all API endpoints return correct status codes
- [ ] Test error handling returns proper messages

---

## 🗺️ PHASE 7: LAUNCH DAY (Week 16)

> **Goal**: Successfully launch to public

### Pre-Launch (T-24 hours)
- [ ] Run `python -m infrastructure.readiness_check` — all checks pass
- [ ] Verify SSL certificate valid (not expiring within 7 days)
- [ ] Test payment flow with 1 BDT test payment
- [ ] Verify Firebase Auth email delivery
- [ ] Test Telegram bot responds
- [ ] Confirm database backups are enabled
- [ ] Verify monitoring dashboards receiving data
- [ ] Prepare rollback tag: `git tag rollback/v1.0.0-launch`
- [ ] Verify GDPR data deletion works
- [ ] Test data export functionality
- [ ] Confirm cookie consent banner visible
- [ ] Verify status page accessible

### Launch Day Timeline
- [ ] **T-60min**: Final readiness check, warm up Cloud Run instances
- [ ] **T-30min**: Enable public signup (remove maintenance mode)
- [ ] **T-0**: Announce on social media / Telegram group
- [ ] **T+15min**: Check first signup flow end-to-end
- [ ] **T+1hr**: Review monitoring dashboards, check error rates
- [ ] **T+4hr**: Check database connection pool utilization
- [ ] **T+8hr**: Review first-day metrics (signups, cameras, events)
- [ ] **T+24hr**: Post-launch retrospective

### Post-Launch (T+24 hours)
- [ ] Review first-day metrics
- [ ] Check for any security incidents
- [ ] Verify all payments processed correctly
- [ ] Check AI API costs
- [ ] Review user feedback
- [ ] Schedule retrospective meeting
- [ ] Update runbook with lessons learned
- [ ] Verify SLA uptime for first 24 hours

---

## 🗺️ PHASE 8: POST-LAUNCH GROWTH (Weeks 17-20)

> **Goal**: Iterate based on user feedback, optimize costs, scale

### Week 17 — Bug Fixes & Polish
- [ ] Address critical bugs from launch
- [ ] Optimize AI API costs (cache frequent queries)
- [ ] Improve dashboard UX based on feedback
- [ ] Add missing error handling

### Week 18 — Feature Enhancements
- [ ] Add advanced analytics (trend analysis, reports)
- [ ] Improve Re-ID accuracy
- [ ] Add more camera modes
- [ ] Enhance mobile responsiveness

### Week 19 — Performance Optimization
- [ ] Optimize database queries
- [ ] Implement caching layer (Redis)
- [ ] Reduce AI latency
- [ ] Optimize image/video storage

### Week 20 — Scale Planning
- [ ] Analyze usage patterns
- [ ] Plan infrastructure scaling
- [ ] Evaluate need for dedicated AI servers
- [ ] Plan V11 features based on user demand

---

## 💰 COST ESTIMATES FOR LAUNCH

### Monthly Infrastructure Costs

| Service | Configuration | Estimated Cost/Month |
|---------|--------------|---------------------|
| **Cloud Run** | 2 instances, 1 vCPU, 512MB | $50-80 |
| **Cloud SQL** | db-f1-micro (0.6GB, 1 vCPU) | $15-25 |
| **Cloud Storage** | 50GB for clips/thumbnails | $5-10 |
| **Cloud CDN** | Static assets delivery | $5-10 |
| **Secret Manager** | 10 secrets | $5 |
| **Cloud Monitoring** | Basic monitoring | $10-20 |
| **Firebase Auth** | Free tier (first 50K users) | $0 |
| **Gemini API** | ~1000 AI calls/day | $30-60 |
| **Groq API** | ~500 audio transcriptions/day | $10-20 |
| **SendGrid Email** | Free tier (100 emails/day) | $0 |
| **Domain & DNS** | .bd or .com domain | $10-15/year |
| **Total** | | **$130-245/month** |

### One-Time Setup Costs

| Item | Cost |
|------|------|
| Domain registration | $10-15 |
| SSL certificate (Google-managed) | $0 |
| bKash Merchant registration | $0 (may require deposit) |
| Nagad Merchant registration | $0 (may require deposit) |
| Legal/DPO consultation | $500-2000 (optional) |
| **Total** | **$510-2,015** |

### Revenue Projection (First 3 Months)

| Month | Users (avg) | Cameras (avg) | MRR (BDT) | MRR (USD) |
|-------|-------------|---------------|-----------|-----------|
| Month 1 | 10 | 20 | 9,800 BDT | $90 |
| Month 2 | 25 | 50 | 24,500 BDT | $225 |
| Month 3 | 50 | 100 | 49,000 BDT | $450 |

**Break-even point**: Month 2-3 (when MRR exceeds ~$200 monthly costs)

---

## 🚨 CRITICAL PATH ITEMS

These are the **most important** things to complete before launch:

### 1. ✅ Security Hardening (Sprint 12.3) — **DONE**
CORS, rate limiting, HTTPS redirect, security headers, Firebase rules, API key management

### 2. ⬜ Data Retention & Privacy (Sprint 12.7) — **NEEDS CODING**
GDPR/DPDP compliance is legally required. Without this, you risk:
- Legal liability for user data
- Inability to delete user data on request
- Cookie consent violations

### 3. ⬜ Backup & DR (Sprint 12.8) — **NEEDS CODING**
Without backups, a database failure means **total data loss** for all users.

### 4. ⬜ Tenant Isolation (Sprint 12.9) — **NEEDS CODING**
Without tenant isolation, one user could potentially access another user's camera feeds — a **catastrophic security breach**.

### 5. ⬜ Client Agent (Phase 2) — **NEEDS CODING**
The backend is useless without the client agent that connects to cameras. Users need the Windows app to:
- Connect to RTSP cameras
- Detect motion
- Send events to the backend

### 6. ⬜ Payment Integration (V7) — **NEEDS CODING**
Without payment processing, you cannot charge users. bKash/Nagad integration is essential for the Bangladesh market.

### 7. ⬜ Infrastructure Setup (Phase 5) — **NEEDS SETUP**
The code is ready, but GCP needs to be configured:
- Cloud Run service
- Cloud SQL database
- Domain + SSL
- Firebase project

---

## 📊 PROGRESS TRACKING

### Overall Progress: ~15%

| Phase | Progress | Estimated Effort |
|-------|----------|-----------------|
| **Phase 1: V10 Coding** | ~30% | 2 weeks |
| **Phase 1B: V11 MEGA.nz Integration** | ⬜ 0% (prompts ready) | 2 weeks |
| **Phase 2: Client Agent** | ~5% | 2 weeks |
| **Phase 3: Core Intelligence** | ~5% | 3 weeks |
| **Phase 4: V6-V9 Features** | ~10% | 4 weeks |
| **Phase 5: Infrastructure** | ~5% | 1 week (simplified with MEGA.nz) |
| **Phase 6: QA** | ~10% | 1 week |
| **Phase 7: Launch** | ~5% | 1 week |
| **Phase 8: Post-Launch** | ~0% | 4 weeks |

### How to Use This Roadmap

1. **Start with Phase 1** — Generate all missing V10 code using DeepSeek prompts from `doc/DEEPSEEK_PROMPTS_V10.md`
2. **Then Phase 1B** — Generate V11 MEGA.nz integration code from `doc/DEEPSEEK_PROMPTS_V11.md` (this replaces PostgreSQL with MEGA.nz)
3. **Follow MANUAL_SETUP_STEPS.md** — Do the manual setup (GCP, Firebase, MEGA.nz account, API keys) — takes 2-3 hours
4. **Then Phase 2** — Build the client agent so cameras can connect
5. **Then Phase 3** — Add AI intelligence features
6. **Then Phase 4** — Add business features (subscription, payment, admin)
7. **Then Phase 5** — Set up cloud infrastructure (simplified — no Cloud SQL needed)
8. **Then Phase 6** — Test everything thoroughly
9. **Then Phase 7** — Launch!
10. **Then Phase 8** — Iterate and grow

### Quick Start Command

```bash
# 1. Generate V10 code from DeepSeek prompts
# Open doc/DEEPSEEK_PROMPTS_V10.md → copy sprints 12.7-12.11 into DeepSeek

# 2. Generate V11 MEGA.nz code from DeepSeek prompts
# Open doc/DEEPSEEK_PROMPTS_V11.md → copy sprints 11.1-11.8 into DeepSeek

# 3. Follow manual setup
# Open doc/MANUAL_SETUP_STEPS.md → follow steps 1-13

# 4. Run tests after each sprint:
pytest backend/tests/ -v

# 5. Start dev server:
uvicorn backend.dashboard.server:app --reload --port 8000

# 6. Open browser:
start http://localhost:8000
```

---

*Vision OS — Publishing Roadmap (MEGA.nz Edition)*
*From Code to Live Production — No Database Needed*
*Next Step: Generate Sprint 12.7 code (Data Retention, Privacy & GDPR/DPDP Compliance)*
