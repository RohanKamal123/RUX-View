# Vision OS — AI-Powered CCTV Intelligence SaaS

> Plug into any camera. Get AI-powered alerts, audio intelligence, and natural language search over your security — starting at 299 BDT/month.

---

## 🎯 What It Is

Vision OS is an AI-powered CCTV intelligence platform for Bangladesh. It connects to existing IP cameras and adds an intelligence layer:

- ✅ **Real-time incident detection** — Person tracking, loitering, ghost detection
- ✅ **Audio transcription** — Whisper API transcribes Bangla audio from cameras
- ✅ **Cross-camera Re-ID** — Track same person across multiple cameras
- ✅ **Natural language queries** — "Who wore red today?" "Are all gates closed?"
- ✅ **5 camera modes** — Indoor, Outdoor, Parking, Mixed, Shop/Analytics
- ✅ **Three-tier pricing** — Free (1-2 cams), Household (299 BDT/cam), Business (499 BDT/cam)

---

## 📚 Documentation

- **[ARCHITECTURE.md](doc/ARCHITECTURE-1.md)** — Complete technical specification
- **[BUILD_PLAN.md](doc/BUILD_PLAN-1.md)** — 12-week solo build roadmap
- **[DECISIONS.md](doc/DECISIONS-1.md)** — Every architectural decision explained

---

## 🏗️ Project Structure

```
RUX View/
├── backend/          # FastAPI server (Google Cloud Run)
│   ├── storage/      # Database (Cloud SQL Postgres + pgvector)
│   ├── ai/           # Gemini 2.0 Flash + Whisper + Re-ID
│   ├── core/         # Incident tracking + cross-camera logic
│   ├── modes/        # Indoor/Outdoor/Parking/Mixed/Shop
│   ├── analytics/    # Digests + shop analytics
│   ├── alerts/       # Telegram + SMS + voice notes
│   ├── api/          # REST endpoints
│   └── dashboard/    # Web UI (FastAPI + Jinja2)
│
├── connect/          # Windows/Android client agent (Phase 2)
│   ├── camera/       # RTSP + motion detection
│   ├── audio/        # YAMNet sound classification
│   └── transport/    # WebSocket + offline buffer
│
└── doc/              # Architecture docs
```

---

## 🚀 Quick Start (Development)

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Google Cloud account (Gemini API enabled)
- OpenAI API key (Whisper)
- Firebase project (Auth + FCM)

### 2. Setup

```bash
# Clone repo
cd "c:/Users/HP Zbook/Documents/RUX View"

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env
# Fill in your API keys in .env

# Initialize database
python -m backend.storage.database init

# Run migrations
alembic upgrade head
```

### 3. Run Development Server

```bash
# Backend API
uvicorn backend.dashboard.server:app --reload --port 8000

# Visit: http://localhost:8000
```

### 4. Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=backend --cov-report=html

# Specific module
pytest backend/tests/unit/test_database.py -v
```

---

## 🧪 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **AI Vision** | Gemini 2.0 Flash | Unified vision + reasoning, cheaper than split Gemma/Gemini |
| **AI Audio** | OpenAI Whisper | Best Bangla transcription accuracy |
| **Re-ID** | BoxMOT (FastReID) | Faster than torchreid, actively maintained |
| **Database** | Postgres + pgvector | Native vector similarity for embeddings |
| **Backend** | FastAPI + async | High performance, async-native |
| **Auth** | Firebase Auth | Google ecosystem integration |
| **Alerts** | Telegram Bot API | Free, popular in BD |
| **Deployment** | Google Cloud Run | Serverless, scales to zero |
| **Scheduling** | APScheduler | Async job scheduler for digests |
| **TTS** | Kokoro-82M | Natural-sounding voice notes |

---

## 📦 Deployment (Production)

### Google Cloud Run

```bash
# Build container
docker build -t gcr.io/PROJECT_ID/visionos-backend .

# Push to registry
docker push gcr.io/PROJECT_ID/visionos-backend

# Deploy
gcloud run deploy visionos-backend \
  --image gcr.io/PROJECT_ID/visionos-backend \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production
```

### Cloud SQL Setup

```bash
# Create instance
gcloud sql instances create visionos-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-4096 \
  --region=asia-south1 \
  --database-flags=cloudsql.enable_pgvector=on

# Create database
gcloud sql databases create visionos --instance=visionos-db

# Enable pgvector
gcloud sql connect visionos-db --user=postgres
# In psql: CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 🎯 Current Phase: **PHASE 1 — FOUNDATION**

### ✅ Completed
- [x] Architecture docs
- [x] Build plan
- [x] Project structure
- [x] requirements.txt

### 🔄 In Progress
- [ ] Database schema (Sprint 1.2)
- [ ] Firebase Auth (Sprint 1.3)
- [ ] AI Client (Sprint 1.4)
- [ ] API stubs (Sprint 1.5)
- [ ] GitHub Actions CI (Sprint 1.6)

### 📅 Next Phases
- Phase 2: Client Agent (Windows .exe)
- Phase 3: Core Intelligence (Re-ID, modes, alerts)
- Phase 4: Audio + Business Features
- Phase 5: Dashboard + NL Queries
- Phase 6: Beta Testing

---

## 🤝 Contributing

This is a solo build project. See [BUILD_PLAN.md](doc/BUILD_PLAN-1.md) for the development roadmap.

---

## 📄 License

Proprietary — Vision OS V1

---

## 📞 Contact

For beta testing inquiries: [Your contact info]

---

**Status:** 🚧 Active Development — Phase 1 Foundation
**Target Launch:** Q3 2026
**Market:** Bangladesh
