"""
server.py — Vision OS Dashboard Server (PostgreSQL Backend).

FastAPI application with:
- Layer 2: Neon PostgreSQL + pgvector for structured data & vectors
- Firebase Auth for production authentication
- Jinja2 templates for dashboard pages
- CORS middleware, security headers, rate limiting
- PipelineManager for AI-powered camera processing

Stack: FastAPI + Jinja2 + PostgresCRUD + Firebase Auth + PipelineManager
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


from backend.config import settings
from backend.storage.pg_crud import PostgresCRUD
from backend.storage.hybrid_crud import HybridCRUD
from backend.storage.engine import close_db, init_db
from backend.dashboard.auth import init_firebase

logger = logging.getLogger(__name__)

# ── Global instances ────────────────────────────────────────────

pg_crud: PostgresCRUD = None  # type: ignore
hybrid_crud: HybridCRUD = None  # type: ignore
pipeline_manager: "PipelineManager" = None  # type: ignore


# ── Application Lifespan ────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    On startup:
      1. Initialize Firebase Auth (production) or dev mode
      2. Initialize PostgreSQL CRUD (Layer 2 — structured data)
      3. Initialize PipelineManager for AI camera processing
    On shutdown: cleanup resources.
    """
    logger.info("Starting Vision OS Dashboard (PostgreSQL Backend)...")

    # ── 1. Initialize Firebase Auth ────────────────────────────
    try:
        init_firebase()
        logger.info("Firebase Auth initialized")
    except Exception as e:
        logger.error("Firebase Auth initialization failed: %s", e)
        if settings.environment == "production":
            raise

    # ── 2. Initialize PostgreSQL CRUD (Layer 2) ────────────────
    global pg_crud
    try:
        pg_crud = PostgresCRUD()
        app.state.pg_crud = pg_crud
        logger.info("PostgreSQL CRUD initialized")

        # Auto-create tables if they don't exist (e.g., first deploy)
        # This handles both fresh deploys and schema updates
        try:
            await init_db()
            logger.info("Database tables created / verified via init_db()")
        except Exception as schema_err:
            logger.error("init_db() failed: %s", schema_err)
            # Fallback: try running Alembic migrations
            try:
                from alembic.config import Config
                from alembic import command
                alembic_cfg = Config("alembic.ini")
                command.upgrade(alembic_cfg, "head")
                logger.info("Alembic migrations completed successfully")
            except Exception as mig_err:
                logger.error("Alembic migration also failed: %s", mig_err)
                raise  # Re-raise so we know PG is broken
    except Exception as e:
        logger.error("Failed to initialize PostgreSQL CRUD: %s", e)
        logger.warning("Running without PostgreSQL — vector search unavailable")
        pg_crud = None
        app.state.pg_crud = None

    # ── 3. Create HybridCRUD (PostgreSQL only, MEGA.nz disabled) ──
    global hybrid_crud
    hybrid_crud = HybridCRUD(pg_crud=pg_crud)
    app.state.hybrid_crud = hybrid_crud

    import backend.dashboard.routes as dashboard_routes
    dashboard_routes.hybrid_crud = hybrid_crud

    import backend.api.cameras as cameras_api
    cameras_api.hybrid_crud = hybrid_crud

    import backend.api.users as users_api
    users_api.hybrid_crud = hybrid_crud

    import backend.api.triggers as triggers_api
    triggers_api.hybrid_crud = hybrid_crud

    import backend.api.queries as queries_api
    queries_api.hybrid_crud = hybrid_crud

    import backend.api.payments as payments_api
    payments_api.hybrid_crud = hybrid_crud

    logger.info("HybridCRUD initialized (PG: %s)",
                "ok" if pg_crud else "unavailable")

    # ── 4. Initialize PipelineManager ──────────────────────────
    global pipeline_manager
    try:
        from backend.core.pipeline_manager import PipelineManager
        pipeline_manager = PipelineManager()
        await pipeline_manager.initialize()
        app.state.pipeline_manager = pipeline_manager

        # Wire into triggers API so frame/audio triggers feed the pipeline
        triggers_api.pipeline_manager = pipeline_manager

        logger.info("PipelineManager initialized — AI pipeline ready")
    except Exception as e:
        logger.error("PipelineManager initialization failed: %s", e)
        logger.warning("Running without AI pipeline — triggers will be stored only")
        pipeline_manager = None
        app.state.pipeline_manager = None

    yield

    # Shutdown
    logger.info("Shutting down Vision OS Dashboard...")
    if pipeline_manager is not None:
        await pipeline_manager.shutdown()
    await close_db()


# ── FastAPI Application ─────────────────────────────────────────

app = FastAPI(
    title="Vision OS Dashboard",
    description="AI-Powered CCTV Intelligence for Bangladesh",
    version="11.4.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files ────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="backend/dashboard/static"), name="static")

# ── Templates ───────────────────────────────────────────────────

templates = Jinja2Templates(directory="backend/dashboard/templates")


# ── Error Handlers ──────────────────────────────────────────────


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Handle storage errors gracefully.

    Args:
        request: FastAPI request object.
        exc: The exception.

    Returns:
        JSON response with error details.
    """
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "code": "STORAGE_ERROR"},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with a JSON response.

    Args:
        request: FastAPI request object.
        exc: The exception.

    Returns:
        JSON response with 404 error.
    """
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "code": "NOT_FOUND"},
    )


# ── Health Check ────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Dict with status, storage type, and timestamp.
    """
    # Check PostgreSQL health
    pg_status = "unavailable"
    if pg_crud is not None:
        try:
            health = await pg_crud.check_health()
            pg_status = health.get("status", "error")
        except Exception:
            pg_status = "error"

    # Check pipeline manager health
    pipeline_status = "unavailable"
    if pipeline_manager is not None:
        pipeline_status = "ok" if pipeline_manager.is_initialized else "not_initialized"

    return {
        "status": "ok",
        "storage": {
            "layer2_postgres": pg_status,
        },
        "pipeline": {
            "status": pipeline_status,
            "active_pipelines": pipeline_manager.active_pipelines if pipeline_manager else 0,
        },
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }


# ── WebSocket Endpoint ──────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for client agent connections.

    Accepts the connection, waits for an auth message
    ``{"type": "auth", "camera_id": "...", "token": "..."}``,
    then relays heartbeats and commands.

    In development mode, any non-empty token is accepted.
    """
    await websocket.accept()
    camera_id = "unknown"
    try:
        # Wait for auth message
        raw = await websocket.receive_text()
        msg = json.loads(raw)
        if msg.get("type") == "auth":
            camera_id = msg.get("camera_id", "unknown")
            token = msg.get("token", "")
            if not token:
                await websocket.send_json({"type": "error", "message": "Missing token"})
                await websocket.close(code=4001)
                return
            logger.info("WebSocket client authenticated: camera=%s", camera_id)
            await websocket.send_json({"type": "auth_ok", "camera_id": camera_id})
        else:
            await websocket.send_json({"type": "error", "message": "Expected auth message"})
            await websocket.close(code=4001)
            return

        # Keep connection alive — handle heartbeats and commands
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "heartbeat":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                logger.debug("Unhandled WS message from %s: %s", camera_id, msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: camera=%s", camera_id)
    except Exception:
        logger.exception("WebSocket error (camera=%s)", camera_id)


# ── Include Routers ─────────────────────────────────────────────

from backend.dashboard.routes import router as dashboard_router
from backend.api.cameras import router as cameras_router
from backend.api.users import router as users_router
from backend.api.triggers import router as triggers_router
from backend.api.queries import router as queries_router
from backend.api.analytics import router as analytics_router
from backend.api.payments import router as payments_router

app.include_router(dashboard_router)
app.include_router(payments_router)
app.include_router(cameras_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(triggers_router, prefix="/api")
app.include_router(queries_router, prefix="/api")
app.include_router(analytics_router)
