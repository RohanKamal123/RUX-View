"""
config_store.py — Runtime-configurable threshold system backed by Redis.

Stores tunable parameters in Upstash Redis as a JSON blob so the
dashboard tuning UI can update them live.  Defaults are defined
here; any key missing from Redis falls back to its default.

Shape returned by get_config():
    {
        "values": {key: value, ...},         # merged (live over defaults)
        "defaults": {key: value, ...},       # hardcoded fallbacks
        "modified_keys": [key, ...],         # keys differing from defaults
        "category_groups": {cat: [key, ...]},# grouping dict
        "live_effective": [key, ...],        # keys affecting single-clip detection
    }
"""

import json
import logging
from backend.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# =========================================================================
# DEFAULTS — Every numeric constant from NUMERICAL_AUDIT.md (58 keys)
# =========================================================================
DEFAULTS = {
    # === DETECTION ===
    "yolo_confidence_threshold": 0.35,   # Sec 3: YOLO acceptance gate
    "nms_iou_threshold": 0.45,           # Sec 3: NMS suppression IoU
    "yolo_input_size": 640,              # Sec 3: ONNX input resolution
    "yolo_jpeg_quality": 85,             # Sec 3: annotated-frame JPEG quality

    # === MOTION ===
    "motion_min_area": 8000,             # Sec 5: min contour area (px²)
    "motion_threshold": 0.05,            # Sec 5: MOG2 sensitivity
    "motion_history": 500,               # Sec 5: MOG2 background frames
    "motion_var_threshold": 56,          # Sec 5: MOG2 variance threshold
    "fg_mask_threshold": 200,            # Sec 5: foreground mask binary threshold

    # === FRAME QUALITY GATES ===
    "brightness_gate_min": 30,           # Sec 6: pipeline — mean brightness floor
    "blur_gate_min": 50,                 # Sec 6: pipeline — Laplacian variance floor
    "pixel_diff_threshold": 25,          # Sec 6: pipeline — pixel intensity diff floor
    "motion_percent_gate": 2.0,          # Sec 6: pipeline — % changed pixels floor
    "motion_trigger_confidence": 0.5,    # Sec 1: legacy motion gate (confidence > 0.5)

    # === TRACKING ===
    "track_match_iou": 0.25,             # Sec 4: BoT-SORT detection → track IoU
    "lost_track_threshold_sec": 30,      # Sec 4: lost-track grace period
    "track_ttl_sec": 300,                # Sec 4: Redis TTL on track state

    # === INCIDENTS / GEMINI GATING ===
    "gemini_interval_sec": 60,           # Sec 2: per-camera Gemini interval
    "track_count_delta": 2,              # Sec 2: track-count change triggers Gemini
    "gemini_confidence_floor": 0.6,      # Sec 7: Gemini structured confidence floor
    "gemini_min_interval_sec": 8.0,      # Sec 7: global Gemini rate limiter
    "per_incident_throttle_sec": 15,     # Sec 6: per-incident Gemini throttle
    "session_timeout_sec": 180,          # Sec 1: session extend/create boundary

    # === RE-ID ===
    "reid_exact_match_threshold": 0.72,  # Sec 8: auto-match cosine similarity floor
    "reid_uncertain_min": 0.50,          # Sec 8: uncertainty zone lower bound
    "reid_uncertain_max": 0.72,          # Sec 8: uncertainty zone upper bound
    "reid_find_similar_limit": 5,        # Sec 8: max pgvector candidate results
    "reid_pgvector_threshold": 0.7,      # Sec 10: pgvector cosine distance threshold
    "reid_tiebreaker_boost": 0.9,        # Sec 8: anchor in (best_score + boost) / 2
    #   ^ Not a standalone threshold — used inside the averaging formula when
    #     Gemini confirms a match: confidence = (best_score + reid_tiebreaker_boost) / 2

    # === GHOST / REPEAT SIGHTING ===
    "ghost_check_interval_sec": 60,      # Sec 11: periodic ghost scan interval
    "ghost_high_alert_sec": 1800,        # Sec 11: 30 min tracked → HIGH alert
    "ghost_medium_alert_sec": 600,       # Sec 11: 10 min tracked → MEDIUM alert
    "repeat_reset_timeout_hours": 6,     # Sec 11: sighting count reset window
    "night_start_hour": 22,              # Sec 11: night hours start (10 PM)
    "night_end_hour": 6,                 # Sec 11: night hours end (6 AM)

    # === ALERTS ===
    "alert_retry_interval_sec": 90,      # Sec 9: emergency alert retry interval
    "alert_max_retries": 3,              # Sec 9: max retries before escalation
    "telegram_timeout_sec": 30.0,        # Sec 9: Telegram API client timeout

    # === STORAGE / DB ===
    "db_pool_size": 3,                   # Sec 10: SQLAlchemy pool persistent conns
    "db_max_overflow": 2,                # Sec 10: max overflow conns (total = 5)
    "db_pool_timeout_sec": 15,           # Sec 10: seconds to wait for pooled conn
    "db_connect_timeout_sec": 15,        # Sec 10: PostgreSQL connect timeout
    "pg_find_similar_limit": 10,         # Sec 10: default rows returned by find_similar_persons

    # === ACCOUNT / QUOTA ===
    "max_cameras_per_user": 20,          # Sec 10: hardcoded camera limit

    # === CACHING ===
    "cache_ttl_static_sec": 3600,        # Sec 12: static assets cache TTL
    "cache_ttl_thumbnail_sec": 86400,    # Sec 12: thumbnail cache TTL
    "cache_ttl_clip_sec": 0,             # Sec 12: clip cache TTL (0 = no cache)
    "cache_ttl_receipt_sec": 0,          # Sec 12: receipt cache TTL (0 = no cache)

    # === RETENTION ===
    "retention_free_days": 7,            # Sec 12: free-tier retention
    "retention_household_days": 30,      # Sec 12: household-tier retention
    "retention_business_days": 90,       # Sec 12: business-tier retention
    "transcript_retention_days": 3,      # Sec 12: transcript retention
    "max_clip_duration_household_sec": 30,    # Sec 12: household max clip length
    "max_clip_duration_business_sec": 60,     # Sec 12: business max clip length

    # === RTSP / CAMERA CLIENT ===
    "rtsp_reconnect_delay_sec": 5,       # Sec 5: RTSP reconnection wait
    "rtsp_connect_timeout_sec": 10.0,    # Sec 5: RTSP stream open timeout

    # === AI CLIENT ===
    "gemini_max_output_tokens": 2048,    # Sec 7: max output tokens (set explicitly)
    "gemini_digest_word_limit": 200,     # Sec 7: free-tier digest word cap

    # === CLIP ANALYSIS ===
    "max_clip_analysis_frames": 1800,    # Sec 14: ceiling for clip analysis (3 min @ 10fps)
}
# -------------------------------------------------------------------------
# End DEFAULTS — 58 keys, one per constant enumerated in NUMERICAL_AUDIT.md
# -------------------------------------------------------------------------

CONFIG_KEY = "visionos:tunable_config"

# Category grouping — maps each logical category to its list of DEFAULTS keys
CATEGORY_GROUPS = {
    "DETECTION": [
        "yolo_confidence_threshold",
        "nms_iou_threshold",
        "yolo_input_size",
        "yolo_jpeg_quality",
    ],
    "MOTION": [
        "motion_min_area",
        "motion_threshold",
        "motion_history",
        "motion_var_threshold",
        "fg_mask_threshold",
    ],
    "FRAME_QUALITY_GATES": [
        "brightness_gate_min",
        "blur_gate_min",
        "pixel_diff_threshold",
        "motion_percent_gate",
        "motion_trigger_confidence",
    ],
    "TRACKING": [
        "track_match_iou",
        "lost_track_threshold_sec",
        "track_ttl_sec",
    ],
    "INCIDENTS_GEMINI": [
        "gemini_interval_sec",
        "track_count_delta",
        "gemini_confidence_floor",
        "gemini_min_interval_sec",
        "per_incident_throttle_sec",
        "session_timeout_sec",
    ],
    "RE_ID": [
        "reid_exact_match_threshold",
        "reid_uncertain_min",
        "reid_uncertain_max",
        "reid_find_similar_limit",
        "reid_pgvector_threshold",
        "reid_tiebreaker_boost",
    ],
    "GHOST_REPEAT": [
        "ghost_check_interval_sec",
        "ghost_high_alert_sec",
        "ghost_medium_alert_sec",
        "repeat_reset_timeout_hours",
        "night_start_hour",
        "night_end_hour",
    ],
    "ALERTS": [
        "alert_retry_interval_sec",
        "alert_max_retries",
        "telegram_timeout_sec",
    ],
    "STORAGE_DB": [
        "db_pool_size",
        "db_max_overflow",
        "db_pool_timeout_sec",
        "db_connect_timeout_sec",
        "pg_find_similar_limit",
    ],
    "ACCOUNT_QUOTA": [
        "max_cameras_per_user",
    ],
    "CACHING": [
        "cache_ttl_static_sec",
        "cache_ttl_thumbnail_sec",
        "cache_ttl_clip_sec",
        "cache_ttl_receipt_sec",
    ],
    "RETENTION": [
        "retention_free_days",
        "retention_household_days",
        "retention_business_days",
        "transcript_retention_days",
        "max_clip_duration_household_sec",
        "max_clip_duration_business_sec",
    ],
    "RTSP_CAMERA_CLIENT": [
        "rtsp_reconnect_delay_sec",
        "rtsp_connect_timeout_sec",
    ],
    "AI_CLIENT": [
        "gemini_max_output_tokens",
        "gemini_digest_word_limit",
    ],
    "CLIP_ANALYSIS": [
        "max_clip_analysis_frames",
    ],
}

# LIVE_EFFECTIVE — keys whose values alter the outcome of a single clip-test
# detection cycle.  Excludes ALERTS, STORAGE_DB, ACCOUNT_QUOTA, CACHING,
# RETENTION, RTSP_CAMERA_CLIENT, and AI_CLIENT because those categories
# do not affect what a single clip detects.
LIVE_EFFECTIVE = frozenset(
    key for cat in [
        CATEGORY_GROUPS["DETECTION"],
        CATEGORY_GROUPS["MOTION"],
        CATEGORY_GROUPS["FRAME_QUALITY_GATES"],
        CATEGORY_GROUPS["TRACKING"],
        CATEGORY_GROUPS["INCIDENTS_GEMINI"],
        CATEGORY_GROUPS["RE_ID"],
        CATEGORY_GROUPS["GHOST_REPEAT"],
    ] for key in cat
)


async def get_config() -> dict:
    """Return the full config envelope: values, defaults, modified_keys,
    category_groups, live_effective.

    The ``values`` dict merges stored Redis values over ``DEFAULTS`` so
    missing keys always fall back to their built-in default. Fails open on
    any Redis error (timeout, connection refused, etc.) — this is read on
    every trigger via PipelineV2 and now also on dashboard page renders
    (see get_max_cameras()), so a transient Redis blip must degrade to
    "use hardcoded defaults", not take down the pipeline or the dashboard.
    """
    merged = dict(DEFAULTS)
    try:
        redis = await get_redis_client()
        raw = await redis.get(CONFIG_KEY)
    except Exception as exc:
        logger.warning("config_store: Redis unavailable, using defaults: %s", exc)
        raw = None
    if raw is not None:
        try:
            stored = json.loads(raw)
            merged.update(stored)
        except json.JSONDecodeError:
            logger.warning("config_store: invalid JSON in Redis key %s", CONFIG_KEY)

    modified_keys = [k for k in DEFAULTS if merged.get(k) != DEFAULTS[k]]
    return {
        "values": merged,
        "defaults": dict(DEFAULTS),
        "modified_keys": modified_keys,
        "category_groups": {cat: list(keys) for cat, keys in CATEGORY_GROUPS.items()},
        "live_effective": sorted(LIVE_EFFECTIVE),
    }


async def get_max_cameras() -> int:
    """Convenience accessor for the ``max_cameras_per_user`` tunable.

    For call sites that only need this one value (camera-quota display,
    limit enforcement) and don't want the full get_config() envelope.
    Previously this limit was hardcoded to 20 in half a dozen places
    across hybrid_crud.py, dashboard/routes.py, and core/camera_limits.py
    instead of reading this tunable — see CLAUDE.md.
    """
    cfg = await get_config()
    return int(cfg["values"].get("max_cameras_per_user", DEFAULTS["max_cameras_per_user"]))


async def set_config(updates: dict) -> dict:
    """Apply *updates* to the current config and persist to Redis.

    Returns the same envelope shape as :func:`get_config` so the
    caller always sees the freshest state (including modified_keys).
    """
    current = await get_config()
    current["values"].update(updates)
    redis = await get_redis_client()
    await redis.set(CONFIG_KEY, json.dumps(current["values"]))
    # Re-derive the envelope so modified_keys is correct
    return await get_config()


async def reset_config() -> dict:
    """Delete the Redis key and return the default envelope."""
    redis = await get_redis_client()
    await redis.delete(CONFIG_KEY)
    return await get_config()