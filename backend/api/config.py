"""
config.py — API endpoints for the runtime tunable config system.

Provides CRUD-like endpoints backed by ``config_store`` so the
dashboard tuning UI can read, update, and reset thresholds live.
"""

import logging
from fastapi import APIRouter
from backend.core.config_store import get_config, set_config, reset_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


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
    return await set_config(updates)


@router.post("/thresholds/reset")
async def reset_thresholds():
    """Delete the stored config and return the default envelope."""
    return await reset_config()