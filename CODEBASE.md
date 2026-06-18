# Vision OS — CODEBASE.md

> AI-powered CCTV intelligence platform for Bangladesh.
> Backend: FastAPI + PostgreSQL (Neon) + Gemini 2.0 Flash + Groq.
> Client: Python desktop agent (RTSP → motion → trigger → backend).

---

## Project Structure

```
RUX View/
├── backend/                  # FastAPI backend server
│   ├── ai/                   # Gemini vision + Groq audio transcription
│   ├── alerts/               # Telegram, SMS, voice note alert routing
│   ├── analytics/            # Shop analytics aggregation
│   ├── api/                  # REST endpoints (triggers, cameras, users, payments, queries)
│   ├── core/                 # Pipeline orchestrator + incident tracker
│   ├── dashboard/            # Jinja2 web dashboard + auth + static assets
│   ├── storage/              # PostgreSQL CRUD + engine + ORM models
│   ├── tests/                # Unit, integration, e2e tests
│   ├── config.py             # Pydantic settings from env vars
│   └── __init__.py           # Package marker
├── connect/                  # Client agent (desktop app)
│   ├── audio/                # Audio capture + YAMNet classification
│   ├── buffer/               # Local queue for trigger batching
│   ├── camera/               # RTSP reader + motion detection
│   ├── tests/                # Client agent tests
│   ├── transport/            # HTTP trigger sender to backend
│   ├── ui/                   # Windows system tray + tkinter settings
│   ├── config.py             # JSON-based persistent config
│   └── main.py               # Client entry point
├── infrastructure/           # Deployment scripts (Cloud Run)
│   ├── deploy.sh             # Bash deploy script (GCR → Cloud Run)
│   └── cloud_run_config.yaml # Cloud Run service YAML
├── alembic/                  # Database migrations
│   ├── versions/             # Migration scripts
│   ├── env.py                # Alembic environment config
│   └── script.py.mako        # Migration template
├── scripts/                  # Utility scripts
│   └── seed_database.py      # DB seeding (pgvector + migrations)
├── doc/                      # Architecture docs, runbooks, prompts
├── .github/workflows/        # CI/CD (GitHub Actions → Cloud Run)
├── ios/                      # iOS/VisionOS mobile app (Swift)
├── android/                  # Android mobile app (Kotlin)
├── dist/                     # Build output (VisionOS-Connect.exe)
├── test_gemini_frames/       # Test images for Gemini analysis
├── test_temp_clips/          # Temporary test video clips
├── Dockerfile                # Multi-stage Docker build
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── pytest.ini                # Pytest configuration
├── alembic.ini               # Alembic configuration
├── build_client.bat          # Windows client build script
├── VisionOS-Connect.spec     # PyInstaller spec for client EXE
└── CODEBASE.md               # This file
```

---

## What Each Major Folder Does

| Folder | Purpose |
|---|---|
| `backend/` | FastAPI server — handles triggers, AI analysis, alerts, dashboard, database |
| `backend/ai/` | Gemini 2.0 Flash vision analysis + Groq Whisper audio transcription |
| `backend/alerts/` | Routes alerts via Telegram, SMS (SSL Wireless), and voice notes (Kokoro TTS) |
| `backend/analytics/` | Aggregates hourly shop analytics (customer count, demographics) |
| `backend/api/` | REST endpoints: frame/audio triggers, camera CRUD, user mgmt, payments, NL queries |
| `backend/core/` | Pipeline orchestrator — incident tracking → vision → Re-ID → cross-camera → alert |
| `backend/dashboard/` | Jinja2 web dashboard with Firebase auth, session cookies, tier gating |
| `backend/storage/` | PostgreSQL ORM models (SQLAlchemy), async engine, CRUD operations |
| `backend/tests/` | Pytest suite: unit (auth, API, AI, DB), integration, e2e |
| `connect/` | Windows desktop client agent — captures RTSP, detects motion, sends triggers |
| `connect/audio/` | Audio capture + YAMNet sound classification |
| `connect/buffer/` | In-memory queue for batching triggers before sending |
| `connect/camera/` | RTSP stream reader + OpenCV motion detection |
| `connect/transport/` | HTTP client that sends triggers to backend API |
| `connect/ui/` | Windows system tray app (pystray) + tkinter settings window |
| `infrastructure/` | Cloud Run deploy script + service YAML config |
| `alembic/` | Database migration scripts (Alembic + SQLAlchemy) |
| `scripts/` | One-off utilities (DB seeding) |
| `doc/` | Architecture decisions, runbooks, prompt history, testing guides |
| `.github/workflows/` | GitHub Actions CI/CD pipeline (test → build → deploy to Cloud Run) |

---

## Entry Points

### Backend Server

```bash
# Development (hot reload)
uvicorn backend.dashboard.server:app --reload --host 0.0.0.0 --port 8080

# Production
gunicorn backend.dashboard.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080

# Docker
docker build -t visionos .
docker run -p 8080:8080 --env-file .env visionos
```

The backend serves:
- **API**: `http://localhost:8080/api/...` (triggers, cameras, users, payments)
- **Dashboard**: `http://localhost:8080/` (Jinja2 web UI)
- **Health**: `http://localhost:8080/health`

### Client Agent (Windows Desktop)

```bash
# Run directly
python -m connect.main

# Build standalone EXE
build_client.bat

# Run built EXE
dist/VisionOS-Connect/VisionOS-Connect.exe
```

The client connects to the backend via `BACKEND_URL` (default: `https://api.visionos.app`).

---

## Environment Variables

Copy `.env.example` to `.env` and fill in values.

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Neon PostgreSQL URL (e.g. `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/visionos`) |
| `GEMINI_API_KEY` | ✅ | Google Gemini 2.0 Flash API key |
| `GROQ_API_KEY` | ✅ | Groq API key (audio transcription) |
| `FIREBASE_CREDENTIALS_JSON` | Production | Inline Firebase service account JSON |
| `FIREBASE_CREDENTIALS_PATH` | Development | Path to `service-account.json` file |
| `TELEGRAM_BOT_TOKEN` | For alerts | Telegram bot token |
| `TELEGRAM_CHAT_ID` | For alerts | Telegram chat ID to receive alerts |
| `SSL_WIRELESS_API_KEY` | For SMS | SSL Wireless Bangladesh SMS API key |
| `SSL_WIRELESS_API_SECRET` | For SMS | SSL Wireless API secret |
| `SSL_WIRELESS_SID` | For SMS | SSL Wireless sender ID |
| `BKASH_APP_KEY` | For billing | bKash merchant app key |
| `BKASH_APP_SECRET` | For billing | bKash merchant app secret |
| `BKASH_SANDBOX` | Optional | Set `True` for sandbox mode |
| `ENVIRONMENT` | ✅ | `development`, `staging`, or `production` |
| `LOG_LEVEL` | Optional | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `SECRET_KEY` | ✅ | Random string for session signing |
| `GOOGLE_CLOUD_PROJECT` | For deploy | GCP project ID |
| `GOOGLE_CLOUD_REGION` | For deploy | GCP region (default: `asia-south1`) |

---

## Deployment

### Google Cloud Run (Production)

```bash
# Using deploy script
bash infrastructure/deploy.sh --env production --tag v1.0.0

# Or manually
gcloud builds submit --tag us-central1-docker.pkg.dev/rux-view-497104/visionos/visionos:latest
gcloud run deploy visionos \
  --image us-central1-docker.pkg.dev/rux-view-497104/visionos/visionos:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### GitHub Actions (CI/CD)

Push to `main` or `staging` branch triggers automatic:
1. Run tests (`pytest backend/tests/`)
2. Build Docker image
3. Push to Artifact Registry
4. Deploy to Cloud Run
5. Smoke test health endpoint

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Seed fresh database
python scripts/seed_database.py
```

---

## Key Architecture Decisions

- **Trigger-only architecture**: Client sends triggers (motion/audio) → backend processes asynchronously
- **Gemini 2.0 Flash**: Primary vision AI (not Vertex AI)
- **Groq Whisper**: Audio transcription (replaced OpenAI Whisper)
- **PostgreSQL + pgvector**: Structured data + vector similarity search for Re-ID
- **Firebase Auth**: Authentication with session cookie fallback for browser
- **Tier gating**: `free` → `guard` → `guard_pro` subscription tiers
- **Per-camera pipeline**: One `CameraPipeline` instance per camera, lazy-created

---

## Testing

```bash
# Run all backend tests
pytest backend/tests/ -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=term-missing

# Run specific test file
pytest backend/tests/unit/test_ai_client.py -v

# Run client tests
pytest connect/tests/ -v
```
