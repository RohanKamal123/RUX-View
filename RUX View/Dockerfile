# ──────────────────────────────────────────────────────────────
# Vision OS — Production Dockerfile
# Target: Cloud PaaS (Railway / Render / Cloud Run)
# Base: python:3.12-slim with system deps for OpenCV + audio
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir firebase-admin pgvector

# ── Runtime stage ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only the backend code needed at runtime (not connect/, android/, ios/, etc.)
COPY backend/ backend/
COPY alembic/ alembic/
COPY alembic.ini .
COPY requirements.txt .
COPY scripts/ scripts/

# Create non-root user
RUN useradd -m -u 1000 visionos && chown -R visionos:visionos /app
USER visionos

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8080\")}/health')"

EXPOSE 8080

CMD uvicorn backend.dashboard.server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2
