================================================================================
VISION OS — PROJECT STRUCTURE DOCUMENTATION
================================================================================
Generated: 2026-06-11
Root: C:\Users\HP Zbook\Documents\RUX View

================================================================================
1. TOP-LEVEL DIRECTORY STRUCTURE
================================================================================

RUX View/
├── .benchmarks/              # Pytest benchmark data (ai_performance_results.json)
├── .github/                  # GitHub Actions CI/CD workflows
│   └── workflows/
│       └── deploy.yml        # CI/CD pipeline (test → build → deploy to Cloud Run)
├── .pytest_cache/            # Pytest cache
├── .venv/                    # Python virtual environment
├── alembic/                  # Database migration framework (Alembic + SQLAlchemy)
├── android/                  # Android (Kotlin) mobile app
├── backend/                  # FastAPI backend server (Primary component)
├── connect/                  # Client agent (RTSP camera desktop app)
├── dist/                     # Build output — VisionOS-Connect.exe (PyInstaller)
├── doc/                      # Architecture documents, runbooks, prompt history
├── infrastructure/           # Cloud deployment configs (Cloud Run)
├── ios/                      # iOS (Swift) mobile app
├── masscan/                  # Network scanner utility (masscan port scanner)
├── scripts/                  # Utility scripts (database seeding)
├── test_gemini_frames/       # Test image frames for Gemini AI analysis
├── test_temp_clips/          # Temporary test video clip storage
│
├── .dockerignore
├── .env                      # Environment variables (local secrets)
├── .env.example              # Environment variables template (documentation)
├── .gitignore
├── ai_performance_results.json
├── alembic.ini               # Alembic configuration
├── build_client.bat          # Windows client build script (PyInstaller)
├── CODEBASE.md               # Codebase overview and architecture summary
├── demo_rtsp_discovery.py    # Demo script: RTSP camera discovery + test
├── Dockerfile                # Multi-stage Docker image for Cloud Run (port 8080)
├── pytest.ini                # Pytest configuration (paths, markers, asyncio)
├── README.md                 # Project README
├── requirements.txt          # Python dependencies
├── task_progress.md          # Active task progress tracker (Vertex AI migration)
├── test_ai_performance.py    # AI performance benchmarking script
├── test_all_modalities.py    # Multi-modality integration test script
├── test_db.py                # Database connectivity test
├── TODO.md                   # Development todo list
├── trigger_test.json         # Motion trigger test payload
└── VisionOS-Connect.spec     # PyInstaller spec file for Windows EXE build

================================================================================
2. BACKEND — FastAPI Server (backend/)
================================================================================

Backend entry point:  backend/dashboard/server.py  (FastAPI app instance)
Local dev command:    uvicorn backend.dashboard.server:app --reload --port 8000
Docker command:       gunicorn backend.dashboard.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
Health endpoint:      GET /health
API root:             /api/...
Dashboard root:       /

backend/
├── __init__.py               # Package marker
├── config.py                 # Centralized config (Pydantic Settings from .env)
│
├── ai/                       # AI/ML services
│   ├── __init__.py
│   ├── ai_client.py          # ★ Vertex AI (Gemini 2.0 Flash) — vision analysis ★
│   ├── query_engine.py       # Natural language query engine ("Who wore red today?")
│   ├── reid_engine.py        # Person Re-Identification engine (cross-camera tracking)
│   └── CONTEXT.md            # AI module design context
│
├── alerts/                   # Alerting & notification system
│   ├── __init__.py
│   ├── alert_router.py       # Routes alerts to configured channels
│   ├── sms_client.py         # SMS alerts (SSL Wireless Bangladesh API)
│   ├── telegram_client.py    # Telegram bot alerts (Telegram Bot API)
│   ├── voice_note.py         # Voice note alerts (Kokoro TTS)
│   └── CONTEXT.md            # Alerts module design context
│
├── analytics/                # Analytics & reporting
│   ├── __init__.py
│   ├── advanced_analytics.py # Advanced analytics calculations
│   ├── anomaly_detector.py   # Anomaly detection algorithms
│   ├── camera_metrics.py     # Per-camera performance metrics
│   ├── digest_generator.py   # Hourly/daily digest reports
│   ├── report_builder.py     # Custom report builder
│   ├── shop_analytics.py     # Shop-specific analytics (customer count, demographics)
│   ├── trend_analyzer.py     # Trend analysis over time
│   ├── usage_tracker.py      # System usage tracking
│   └── CONTEXT.md            # Analytics module design context
│
├── api/                      # REST API routes (FastAPI routers)
│   ├── __init__.py
│   ├── admin_cameras.py      # Admin camera management endpoints
│   ├── analytics.py          # Analytics data API
│   ├── cameras.py            # Camera CRUD API (register, update, delete)
│   ├── clips.py              # Video clip retrieval API
│   ├── locations.py          # Location management API
│   ├── payments.py           # Payment processing API (bKash)
│   ├── public_signup.py      # Public user registration API
│   ├── queries.py            # Natural language query API
│   ├── telegram_test.py      # Telegram bot test endpoint
│   ├── triggers.py           # Motion/audio trigger ingestion API
│   ├── users.py              # User management API
│   └── CONTEXT.md            # API module design context
│
├── core/                     # Core business logic & orchestration
│   ├── __init__.py
│   ├── api_key_manager.py    # API key generation & validation
│   ├── audio_correlation.py  # Audio event correlation with video
│   ├── audio_only_incident.py# Audio-only incident detection
│   ├── bulk_operations.py    # Bulk camera/user operations
│   ├── cache_manager.py      # In-memory cache management
│   ├── camera_health.py      # Camera health monitoring & status
│   ├── camera_limits.py      # Per-tier camera limits enforcement
│   ├── cross_camera.py       # Cross-camera person tracking (Re-ID orchestration)
│   ├── error_handler.py      # Centralized error handling & formatting
│   ├── firebase_rules.json   # Firebase security rules
│   ├── ghost_detector.py     # Ghost detection (false positive reduction)
│   ├── health_checker.py     # System health checks (DB, AI, storage)
│   ├── incident_tracker.py   # Incident creation, storage, retrieval
│   ├── location_manager.py   # Location/camera grouping management
│   ├── onboarding.py         # New user onboarding workflow
│   ├── pipeline.py           # Per-camera pipeline orchestration
│   ├── pipeline_manager.py   # Manages all camera pipelines (lazy creation)
│   ├── repeat_sighting.py    # Repeat person sighting detection
│   ├── retry_manager.py      # Retry logic for failed operations
│   ├── security_middleware.py# Auth middleware, tier gating, rate limiting
│   └── CONTEXT.md            # Core module design context
│
├── dashboard/                # Web dashboard (FastAPI + Jinja2 + Firebase Auth)
│   ├── __init__.py
│   ├── admin_routes.py       # Admin panel routes
│   ├── auth.py               # Firebase Authentication integration
│   ├── routes.py             # Dashboard page routes (cameras, settings, etc.)
│   ├── server.py             # ★ MAIN FASTAPI APPLICATION ★
│   ├── CONTEXT.md            # Dashboard module design context
│   ├── static/               # Static assets (CSS, JS)
│   │   ├── admin_analytics.css
│   │   ├── admin_analytics.js
│   │   ├── admin_cameras.css
│   │   ├── admin_cameras.js
│   │   ├── app.js
│   │   ├── help.css
│   │   ├── help.js
│   │   ├── landing.css
│   │   ├── landing.js
│   │   ├── onboarding.css
│   │   ├── onboarding.js
│   │   ├── placeholder.jpg
│   │   └── style.css
│   └── templates/            # Jinja2 HTML templates
│       ├── admin_analytics.html
│       ├── admin_cameras.html
│       ├── admin.html
│       ├── base.html
│       ├── camera.html
│       ├── cameras.html
│       ├── dashboard.html
│       ├── help_article.html
│       ├── help.html
│       ├── index.html
│       ├── landing.html
│       ├── login.html
│       ├── onboarding.html
│       ├── payment.html
│       ├── person.html
│       └── settings.html
│
├── i18n/                     # Internationalization / Localization
│   ├── translations.py      # Translation functions
│   └── locales/              # Locale translation files (empty)
│
├── storage/                  # Data access & persistence layer
│   ├── __init__.py
│   ├── cdn_manager.py        # CDN asset management
│   ├── cleanup.py            # Storage cleanup routines
│   ├── clip_recorder.py      # Video clip recording & storage
│   ├── connection_pool.py    # Database connection pool management
│   ├── crud.py               # Generic CRUD operations
│   ├── database.py           # SQLAlchemy ORM models & Base
│   ├── engine.py             # Async SQLAlchemy engine factory
│   ├── hybrid_crud.py        # Hybrid storage (DB + MEGA.nz) CRUD
│   ├── pg_crud.py            # PostgreSQL-specific CRUD (pgvector operations)
│   └── CONTEXT.md            # Storage module design context
│
└── tests/                    # Comprehensive test suite
    ├── __init__.py
    ├── conftest.py           # Pytest fixtures (test client, auth overrides, DB)
    ├── TESTING_GUIDE.md      # Testing methodology guide
    ├── e2e/                  # End-to-end tests
    │   ├── __init__.py
    │   ├── conftest.py
    │   ├── test_20_cameras.py    # 20-camera stress test
    │   └── test_full_journey.py  # Full user journey (signup → camera → trigger → alert)
    ├── fixtures/             # Test fixture data
    │   └── __init__.py
    ├── integration/          # Integration tests
    │   └── __init__.py
    └── unit/                 # Unit tests (55+ test files)
        ├── __init__.py
        ├── execute_method.txt
        ├── test_admin_analytics.py
        ├── test_admin_cameras_ui.py
        ├── test_admin_cameras.py
        ├── test_admin.py
        ├── test_advanced_analytics.py
        ├── test_ai_client.py       # Vertex AI / Gemini client tests
        ├── test_alerts.py
        ├── test_api.py             # API endpoint tests
        ├── test_audio_intelligence.py
        ├── test_auth.py            # Firebase auth tests
        ├── test_autoscaling.py
        ├── test_bulk_operations.py
        ├── test_camera_health.py
        ├── test_camera_limits.py
        ├── test_camera_metrics.py
        ├── test_cdn_manager.py
        ├── test_cleanup.py
        ├── test_clips.py
        ├── test_connection_pool.py
        ├── test_cross_camera.py
        ├── test_dashboard.py
        ├── test_database.py
        ├── test_digest_generator.py
        ├── test_email_service.py
        ├── test_error_handler.py
        ├── test_help.py
        ├── test_i18n.py
        ├── test_incident_tracker.py
        ├── test_landing.py
        ├── test_load_balancer.py
        ├── test_location_manager.py
        ├── test_man_fixture.py
        ├── test_managernew.py
        ├── test_modes.py
        ├── test_monitoring.py
        ├── test_onboarding.py
        ├── test_payment_info.py
        ├── test_payment_processor.py
        ├── test_performance.py
        ├── test_pipeline.py
        ├── test_public_signup.py
        ├── test_query_engine.py
        ├── test_readiness_check.py
        ├── test_reid_engine.py
        ├── test_security_middleware.py
        ├── test_shop_analytics.py
        ├── test_subscription_manager.py
        ├── test_trial_manager.py
        └── test_usage_tracker.py

================================================================================
3. CLIENT AGENT — RTSP Camera Desktop App (connect/)
================================================================================

Client entry point:  connect/main.py  (VisionOSConnect orchestrator)
Run command:         python -m connect.main
Build command:       build_client.bat  (produces dist/VisionOS-Connect.exe)

The client agent runs on Windows as a system-tray application. It:
  - Reads RTSP streams from configured IP cameras
  - Detects motion via OpenCV (MOG2 background subtractor)
  - Captures audio and classifies sounds via YAMNet
  - Batches triggers and sends them to the backend API
  - Falls back to local SQLite queue when offline

connect/
├── __init__.py
├── config.py                 # Client configuration (JSON-based persistent config)
├── main.py                   # ★ MAIN CLIENT ORCHESTRATOR ★
├── CONTEXT.md                # Client module design context
│
├── audio/                    # Audio capture & classification
│   ├── __init__.py
│   ├── audio_capture.py      # Audio capture from system microphone
│   └── yamnet_detector.py    # YAMNet sound classification (gunshot, scream, glass, etc.)
│
├── buffer/                   # Offline/local queue
│   ├── __init__.py
│   └── local_queue.py        # SQLite-backed offline trigger queue (for network outages)
│
├── camera/                   # Camera stream reading & motion detection
│   ├── __init__.py
│   ├── frame_selector.py     # Best frame selection from triggered clips
│   ├── motion_detector.py    # Motion detection (OpenCV MOG2 + contour analysis)
│   ├── rtsp_discovery.py     # RTSP camera discovery on local network (ONVIF)
│   ├── rtsp_reader.py        # ★ RTSP stream reader (OpenCV VideoCapture) ★
│   └── rtsp_tester.py        # RTSP connection testing utility
│
├── tests/                    # Client test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_audio.py
│   ├── test_build_verify.py
│   ├── test_camera.py
│   ├── test_client_mega.py
│   ├── test_integration.py
│   ├── test_local_queue.py
│   ├── test_main_orchestrator.py
│   ├── test_motion.py
│   └── test_transport.py
│
├── transport/                # Communication with backend server
│   ├── __init__.py
│   ├── sms_sender.py         # Direct SMS sender (fallback channel)
│   ├── trigger_sender.py     # HTTP trigger payload sender to backend API
│   └── websocket_client.py   # WebSocket client for real-time backend communication
│
└── ui/                       # User interface (Windows system tray)
    ├── __init__.py
    └── tray_app.py           # Windows system tray app (pystray) + tkinter settings

================================================================================
4. MOBILE APPS
================================================================================

--- iOS (Swift) ---
ios/
├── VisionOS/                 # Main iOS app
│   └── Services/
│       ├── VisionOSApiService.swift   # API client for backend communication
│       └── VideoService.swift         # Video streaming & playback
│   (Views/ directory listed in open tabs but not yet confirmed on disk)
└── VisionOSTests/            # iOS tests
    └── VisionOSTests.swift

--- Android (Kotlin) ---
android/
└── app/
    └── src/
        ├── main/java/com/visionos/app/
        │   ├── MainActivity.kt       # Main Android activity
        │   ├── ApiClient.kt          # Retrofit API client
        │   ├── LoginScreen.kt        # Login screen composable
        │   ├── api/                  # API interfaces (empty)
        │   ├── data/                 # Data layer (empty)
        │   └── ui/                   # UI components (empty)
        └── test/java/com/visionos/app/
            └── ...                   # Test stubs

================================================================================
5. DATABASE MIGRATIONS (alembic/)
================================================================================

alembic/
├── env.py                    # Alembic environment configuration (async engine)
├── script.py.mako            # Migration script template
└── versions/
    ├── 001_initial_schema.py # Initial database schema (users, cameras, incidents, etc.)
    └── 002_add_payments.py   # Payment & subscription tables

Migration commands:
  Create:  alembic revision --autogenerate -m "description"
  Apply:   alembic upgrade head
  Rollback: alembic downgrade -1
  Seed:    python scripts/seed_database.py

================================================================================
6. INFRASTRUCTURE & DEPLOYMENT
================================================================================

infrastructure/
├── cloud_run_config.yaml     # Cloud Run service YAML (CPU, memory, scaling, env vars)
└── deploy.sh                 # Bash deployment script (build → push → deploy to Cloud Run)

CI/CD: .github/workflows/deploy.yml
  - Triggers on push to main/staging branches
  - Steps: pytest → Docker build → Artifact Registry push → Cloud Run deploy → smoke test

================================================================================
7. KEY CONFIGURATION FILES
================================================================================

File                      Purpose
─────────────────────────────────────────────────────────────────────────────
.env.example              Environment variable template (all required vars documented)
.env                      Actual environment variables (git-ignored, local secrets)
Dockerfile                Multi-stage Docker build based on python:3.11-slim
requirements.txt          Python dependencies (FastAPI, SQLAlchemy, vertexai, groq, etc.)
pytest.ini                Test configuration (paths, asyncio_mode = auto, markers)
alembic.ini               Alembic database migration configuration
.dockerignore             Files excluded from Docker build context
.gitignore                Git ignore rules
build_client.bat          Windows batch script: PyInstaller build for VisionOS-Connect.exe
VisionOS-Connect.spec     PyInstaller .spec file (one-file Windows EXE)
task_progress.md          Active task tracker (Vertex AI migration currently complete)

================================================================================
8. SCRIPTS & UTILITIES
================================================================================

scripts/
└── seed_database.py       # Database seeder: creates tables + inserts demo data

Root-level scripts:
  test_ai_performance.py   # AI latency/throughput benchmark
  test_all_modalities.py   # Tests all AI modalities (vision, audio, query)
  test_db.py               # Database connectivity & query test
  demo_rtsp_discovery.py   # RTSP camera discovery + connection test

================================================================================
9. DOCUMENTATION (doc/)
================================================================================

doc/
├── ARCHITECTURE-1.md              # Complete technical architecture specification
├── BUILD_PLAN-1.md                # 12-week solo build roadmap
├── CONTEXT_cross_camera_reid.md   # Cross-camera Re-ID design context
├── CONTEXT_outdoor_crowd_mode.md  # Outdoor crowd mode design context
├── DECISIONS-1.md                 # All architectural decisions explained
├── DEEPSEEK_PROMPTS_V1.md through V11.md  # AI prompt evolution history
├── E2E_TESTING_GUIDE.md           # End-to-end testing guide
├── LAUNCH_RUNBOOK.md              # Production launch day operations checklist
├── MANUAL_SETUP_STEPS.md          # Manual environment setup guide
├── PROGRESS.md                    # Overall project progress tracking
└── PUBLISHING_ROADMAP.md          # Beta → Investor publishing roadmap

================================================================================
10. ENTRY POINTS SUMMARY
================================================================================

COMPONENT                 FILE                                    PORT    COMMAND
───────────────────────────────────────────────────────────────────────────────────────────
Backend (FastAPI dev)     backend/dashboard/server.py             8000    uvicorn backend.dashboard.server:app --reload --port 8000
Backend (Docker prod)     backend/dashboard/server.py             8080    gunicorn ... --bind 0.0.0.0:8080
Client Agent (direct)     connect/main.py                         N/A     python -m connect.main
Client Agent (EXE)        dist/VisionOS-Connect/VisionOS-Connect.exe N/A   (double-click)
Database Seed             scripts/seed_database.py                N/A     python scripts/seed_database.py
Migration Apply           alembic/                                N/A     alembic upgrade head
Deploy                    infrastructure/deploy.sh                N/A     bash infrastructure/deploy.sh
iOS App                   ios/VisionOS/                           N/A     Xcode project
Android App               android/app/                            N/A     Android Studio project

================================================================================
11. TECHNOLOGY STACK OVERVIEW
================================================================================

Layer                   Technology                              Purpose
───────────────────────────────────────────────────────────────────────────────────────────
Backend Framework       FastAPI (Python 3.11)                   Async REST API server
AI Vision               Vertex AI (Gemini 2.0 Flash)            Image analysis & reasoning
AI Audio                Groq (Whisper large-v3)                 Bangla speech-to-text
Person Re-ID            BoxMOT / FastReID                       Cross-camera person tracking
Sound Classification    YAMNet (TensorFlow)                     Audio event classification
Database                PostgreSQL 15 + pgvector                Structured data + vector search
Auth                    Firebase Authentication                 User login (Google, email)
Web Dashboard           Jinja2 Templates + CSS/JS               Browser UI
Alerts                  Telegram Bot API                        Real-time push notifications
SMS                     SSL Wireless Bangladesh API             SMS alerts
Payments                bKash Merchant API                      Subscription billing
Deployment              Google Cloud Run                        Serverless container hosting
CI/CD                   GitHub Actions                           Automated test + deploy
Container               Docker (python:3.11-slim)               Reproducible builds
Client UI               pystray + tkinter                       Windows system tray app
Offline Queue           SQLite                                  Offline trigger buffering
TTS                     Kokoro-82M                              Voice note generation
Scheduling              APScheduler                              Cron-like job scheduling
RTSP Streaming          OpenCV (VideoCapture)                   IP camera stream reading
Motion Detection        OpenCV (MOG2 BackgroundSubtractor)      Motion trigger events
Migration               Alembic + SQLAlchemy                     Database schema versioning

================================================================================
12. DEPLOYMENT ARCHITECTURE
================================================================================

                            ┌─────────────┐
                            │   GitHub     │
                            │  Actions     │
                            │ (CI/CD)      │
                            └──────┬──────┘
                                   │ push Docker image
                                   ▼
                        ┌───────────────────┐
                        │ Artifact Registry  │
                        │ (Container Image)  │
                        └────────┬──────────┘
                                 │ deploy
                                 ▼
                   ┌─────────────────────────┐
                   │   Google Cloud Run       │
                   │  ┌───────────────────┐  │
                   │  │  FastAPI Server   │  │
                   │  │  (gunicorn)       │  │
                   │  │  Port 8080        │  │
                   │  └────────┬──────────┘  │
                   └───────────┼──────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Neon        │  │  Vertex AI   │  │  Telegram    │
    │  PostgreSQL  │  │  Gemini API  │  │  Bot API     │
    │  + pgvector  │  │  (Vision)    │  │  (Alerts)    │
    └──────────────┘  └──────────────┘  └──────────────┘
            ▲
            │ HTTP triggers (motion/audio events)
    ┌───────┴──────────┐
    │  VisionOS Client │
    │  (Windows .exe)  │
    │  RTSP → Motion   │
    │  → Audio → Send  │
    └──────────────────┘

================================================================================
END OF PROJECT STRUCTURE DOCUMENTATION
================================================================================