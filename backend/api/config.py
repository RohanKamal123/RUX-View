"""
config.py — API endpoints for the runtime tunable config system.

Provides CRUD-like endpoints backed by ``config_store`` so the
dashboard tuning UI can read, update, and reset thresholds live.
"""

import logging
from fastapi import APIRouter, Depends
from backend.core.config_store import get_config, set_config, reset_config
from backend.dashboard.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

# Subset of config_store.DEFAULTS relevant to the connect/ Windows client
# agent (motion detection + RTSP reconnection). The client has no direct
# Redis access — it polls GET /client periodically (see
# connect/config_sync.py) instead of reading config_store itself.
CLIENT_CONFIG_KEYS = [
    "motion_min_area",
    "motion_threshold",
    "motion_history",
    "motion_var_threshold",
    "fg_mask_threshold",
    "rtsp_reconnect_delay_sec",
    "rtsp_connect_timeout_sec",
]


async def _refresh_db_pool_if_needed() -> None:
    """Best-effort immediate DB-pool rebuild after a config write.

    Only db_pool_* keys actually trigger a rebuild (refresh_engine_config()
    no-ops if nothing changed), so this is cheap to call unconditionally.
    Import is local to avoid a hard dependency for callers/tests that don't
    care about the DB engine.
    """
    try:
        from backend.storage.engine import refresh_engine_config
        await refresh_engine_config()
    except Exception as exc:
        logger.warning("Failed to refresh DB engine after config write: %s", exc)


@router.get("/thresholds")
async def get_thresholds():
    """Return the full config envelope.

    Response shape:
        values:           {key: value}  — merged (live over defaults)
        defaults:         {key: value}  — hardcoded fallbacks
        modified_keys:    [str]         — keys differing from defaults
        category_groups:  {cat: [keys]} — 14 logical groupings
        live_effective:   [str]         — keys affecting single-clip detection
    """
    return await get_config()


@router.post("/thresholds")
async def update_thresholds(updates: dict):
    """Apply *updates* to the stored config and return the new envelope."""
    result = await set_config(updates)
    await _refresh_db_pool_if_needed()
    return result


@router.post("/thresholds/reset")
async def reset_thresholds():
    """Delete the stored config and return the default envelope."""
    result = await reset_config()
    await _refresh_db_pool_if_needed()
    return result


@router.get("/client")
async def get_client_config(user: dict = Depends(get_current_user)):
    """Return the client-relevant tunable subset for the connect/ agent.

    Polled by connect/config_sync.py::ClientConfigSync so a Windows agent
    running at a customer site can pick up motion_*/rtsp_* tuning-dashboard
    changes without a client rebuild/redeploy. Uses the same
    get_current_user auth the client already authenticates triggers with
    (Authorization: Bearer <api_key>), rather than a separate scheme.
    """
    cfg = await get_config()
    values = cfg["values"]
    return {key: values[key] for key in CLIENT_CONFIG_KEYS}