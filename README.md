# Vision OS

AI-powered CCTV intelligence for the Bangladesh market. Analyzes camera streams using Gemini vision and alerts building owners via Telegram.

## What it does

- **Plug in any IP camera and get instant AI alerts.** VisionOS connects to existing cameras over RTSP or P2P relay, detects people and vehicles, and sends Telegram notifications when something important happens.
- **Ask your security system questions in plain language.** "Who wore a red shirt today?" "Are all gates closed?" VisionOS remembers events and lets you search through natural language.
- **Automatic on-premise detection gate.** A YOLO nano model runs on the Windows agent to filter irrelevant frames before cloud AI is called, keeping costs low.

## Tech stack

| Layer | Technology | Purpose | Notes |
|-------|-----------|---------|-------|
| AI Vision | Vertex AI Gemini 2.x Flash | Frame analysis, threat detection | google-cloud-aiplatform SDK |
| Detection gate | YOLOv8 nano (ONNX Runtime) | Filters irrelevant frames before Gemini | On-device, ~200ms per frame |
| Object tracking | BoT-SORT + Upstash Redis | Persistent track IDs per camera | IoU-based matching |
| Backend | FastAPI + Python 3.11 | REST API, WebSocket, pipeline orchestration | Async, Cloud Run |
| Database | Neon PostgreSQL + pgvector | Events, users, cameras, Re-ID vectors | Serverless Postgres |
| Cache | Upstash Redis | Tracker state, session deduplication | HTTP-based, no VPC |
| Dashboard | Jinja2 + vanilla JS | Server-rendered web UI | Tabler icons |
| Alerts | Telegram Bot API | Push notifications | Text, photo, voice note |
| Hosting | Google Cloud Run | Serverless container | Auto-scaling, asia-south1 |
| Client | Python + PyInstaller (.exe) | On-premise camera agent | Windows 10/11 |

## Architecture

```
  Camera (RTSP/Dahua P2P)
       │
  Connect Client (.exe)
  ├── YOLO nano gate (ONNX, on-device)
  ├── BoT-SORT tracker (Redis state)
  └── Trigger sender (HTTP → Cloud Run)
       │
  Cloud Run Backend
  ├── Session dedup (45s merge window)
  ├── Pipeline V2 orchestrator
  │   ├── YOLO gate (cloud-side verify)
  │   ├── Gemini 2.x vision analysis
  │   ├── Re-ID engine (pgvector cosine)
  │   └── Alert router (Telegram)
  └── PostgreSQL (Neon) + Upstash Redis
       │
  Dashboard (Web UI)
```

## Quickstart

```bash
# Clone the repository
git clone https://github.com/RohanKamal123/RUX-View.git
cd RUX-View

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env      # Windows
# cp .env.example .env       # Linux / macOS
```

Edit `.env` with your API keys. Required environment variables:

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for Vertex AI |
| `GOOGLE_CLOUD_REGION` | Vertex AI region (default: asia-south1) |
| `DATABASE_URL` | Neon PostgreSQL connection string with pgvector |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | Default Telegram chat ID |
| `SECRET_KEY` | Random secret for session signing |

### Run the development server

```bash
uvicorn backend.dashboard.server:app --reload --port 8000
```

Visit **http://localhost:8000** to open the dashboard.

## Folder structure

| Directory | Contents |
|-----------|----------|
| `backend/` | FastAPI backend, AI pipeline, API routes, dashboard |
| `connect/` | Windows desktop client agent (.exe) |
| `doc/` | Architecture, decisions, runbooks |
| `masscan/` | RTSP camera discovery utility |
| `alembic/` | PostgreSQL migration versions |
| `infrastructure/` | Cloud Run deployment config |
| `scripts/` | Utility scripts |

## Running tests

```bash
# Run all backend tests
pytest backend/tests/ -v

# Run connect client tests
pytest connect/tests/ -v
```

## Deployment

```bash
# Build the container
docker build -t gcr.io/PROJECT_ID/visionos-backend .

# Push to Google Container Registry
docker push gcr.io/PROJECT_ID/visionos-backend

# Deploy to Cloud Run
gcloud run deploy visionos-backend \
  --image gcr.io/PROJECT_ID/visionos-backend \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production
```

See **[doc/LAUNCH_RUNBOOK.md](doc/LAUNCH_RUNBOOK.md)** for the full deployment checklist.

## Documentation

See **[doc/INDEX.md](doc/INDEX.md)** for a complete index of all documentation.