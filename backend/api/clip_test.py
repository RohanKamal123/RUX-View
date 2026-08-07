"""
clip_test.py — Full Vision OS pipeline dry-run endpoint for tuning dashboard.

POST /api/config/clip-test
  Accepts N JPEG files (pre-extracted from video in the browser).
  Runs the full PipelineV2 chain (YOLO gate → BoT-SORT tracker →
  incident builder → Gemini vision → alert routing) with dry_run=True
  so NO data is written to the database, NO alerts are sent, and NO
  production Redis tracker state is touched.

  Uses a synthetic camera ID per request so every test run starts
  with fresh incident builder state.

Why dry_run:
  You adjust sliders on the tuning page, run the clip test, and see
  exactly which pipeline stage filtered each frame and why — without
  corrupting production state.

Streaming protocol:
  NDJSON (newline-delimited JSON). One JSON object per line,
  flushed immediately after each frame completes pipeline processing.
  First line is always type=meta. Last line is always type=summary.
  Frame lines in between have type=frame.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.core.config_store import LIVE_EFFECTIVE, get_config
from backend.core.detection.incident_builder import cleanup_synthetic_camera
from backend.core.pipeline_v2 import PipelineV2

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])

MAX_FRAMES = 90          # hard ceiling: 30s @ 3fps
MAX_JPEG_BYTES = 512_000  # 500KB per frame — reject obviously wrong files
VALID_MODES = {"indoor", "outdoor", "parking", "shop", "night"}


def _get_pipeline_stage(result) -> str:
    """Derive the pipeline stage reached from a PipelineV2.PipelineResult.

    Logic:
      - skip_reason None + incident_id set  → "complete"
      - skip_reason == "yolo_gate"          → "yolo_gate"
      - skip_reason == "throttled"          → "incident_builder"
      - else                                → "tracker"
    """
    if result.skip_reason is None and result.incident_id:
        return "complete"
    if result.skip_reason == "yolo_gate":
        return "yolo_gate"
    if result.skip_reason == "throttled":
        return "incident_builder"
    # Everything else means we got past YOLO gate but were
    # stopped before Gemini (e.g. tracker-only fallback)
    return "tracker"


async def _stream_pipeline_results(
    frames: list[tuple[int, float, bytes]],
    camera_mode: str,
    config: dict,
    synthetic_id: str,
    pv2: PipelineV2,
) -> AsyncGenerator[str, None]:
    """Yield NDJSON lines: meta → frame results → summary.

    Guarantees synthetic camera cleanup in the finally block
    even if an exception occurs mid-stream.
    """
    # ── state accumulators for summary ─────────────────────────
    total_frames = len(frames)
    yolo_filtered = 0
    incident_builder_throttled = 0
    gemini_called = 0
    gemini_no_change = 0
    alerts_would_send = 0
    threat_breakdown: dict[str, int] = {}
    all_total_ms: list[float] = []
    all_person_ids: set[str] = set()

    # ── only expose live-effective keys in meta snapshot ────────
    snapshot = {k: v for k, v in config.items() if k in LIVE_EFFECTIVE}

    try:
        # ── meta line ─────────────────────────────────────────
        yield json.dumps({
            "type": "meta",
            "total_frames": total_frames,
            "camera_mode": camera_mode,
            "synthetic_camera_id": synthetic_id,
            "config_snapshot": snapshot,
        }) + "\n"

        # ── process each frame sequentially ────────────────────
        for frame_idx, ts, jpeg_bytes in frames:
            try:
                result = await pv2.process_frame(
                    camera_id=synthetic_id,
                    user_id="clip-test",
                    location_id="clip-test",
                    mode=camera_mode,
                    jpeg_bytes=jpeg_bytes,
                    camera_profile=None,
                    dry_run=True,
                )
            except Exception as exc:
                logger.error("clip_test: frame %d failed: %s", frame_idx, exc, exc_info=True)
                yield json.dumps({
                    "type": "error",
                    "message": str(exc),
                    "frame_index": frame_idx,
                }) + "\n"
                continue

            # ── classify the stage this frame reached ──────────
            stage = _get_pipeline_stage(result)

            if stage == "yolo_gate":
                yolo_filtered += 1
            elif stage == "incident_builder":
                incident_builder_throttled += 1

            if stage in ("gemini", "complete"):
                gemini_called += 1
                if not result.change_detected:
                    gemini_no_change += 1

            tl = result.threat_level or "LOW"
            threat_breakdown[tl] = threat_breakdown.get(tl, 0) + 1
            if tl in ("HIGH", "CRITICAL", "EMERGENCY"):
                alerts_would_send += 1

            total_ms = (result.stage_timings_ms or {}).get("total_ms")
            if total_ms is not None:
                all_total_ms.append(total_ms)

            if result.person_ids:
                all_person_ids.update(result.person_ids)

            yield json.dumps({
                "type": "frame",
                "frame_index": frame_idx,
                "timestamp_sec": round(float(ts), 3),

                "pipeline_stage_reached": stage,
                "skip_reason": result.skip_reason,
                "threat_level": result.threat_level,
                "change_detected": result.change_detected,
                "alert_message": result.alert_message or None,

                "stage_timings_ms": result.stage_timings_ms or {},

                "annotated_jpeg_b64": result.annotated_jpeg_b64,

                "person_ids": result.person_ids or [],
            }) + "\n"

        # ── summary line ───────────────────────────────────────
        avg_ms = round(sum(all_total_ms) / len(all_total_ms), 1) if all_total_ms else 0.0
        yield json.dumps({
            "type": "summary",
            "total_frames": total_frames,
            "yolo_filtered": yolo_filtered,
            "incident_builder_throttled": incident_builder_throttled,
            "gemini_called": gemini_called,
            "gemini_no_change": gemini_no_change,
            "alerts_would_send": alerts_would_send,
            "threat_breakdown": threat_breakdown,
            "avg_total_ms": avg_ms,
            "person_ids_seen": sorted(all_person_ids),
        }) + "\n"

    except Exception as exc:
        # Catastrophic failure before or after meta — yield error line
        logger.error("clip_test: generator failed: %s", exc, exc_info=True)
        yield json.dumps({
            "type": "error",
            "message": str(exc),
            "frame_index": -1,
        }) + "\n"
        return
    finally:
        # ── cleanup synthetic camera state ─────────────────────
        cleanup_synthetic_camera(synthetic_id)
        # pipeline_manager.cleanup_synthetic_camera exists (confirmed)
        pv2.pipeline_manager.cleanup_synthetic_camera(synthetic_id)
        logger.info("clip_test: cleaned up synthetic camera %s", synthetic_id)


@router.post("/clip-test")
async def clip_test(
    request: Request,
    frames: list[UploadFile] = File(...),
    timestamps: str = Form(...),
    camera_mode: str = Form(default="indoor"),
):
    """Run full PipelineV2 dry-run on pre-extracted JPEG frames.

    Args:
        frames:      List of JPEG files. Named "frames" in FormData.
        timestamps:  JSON array of float seconds, one per frame.
                     e.g. "[0.0, 0.5, 1.0, 1.5, ...]"
                     Must have the same length as frames.
        camera_mode: Camera operational mode. One of:
                     indoor / outdoor / parking / shop / night.

    Returns:
        StreamingResponse (application/x-ndjson).
        One JSON line per processed frame with full pipeline metadata.
    """
    # ── validate camera_mode ──────────────────────────────────
    if camera_mode not in VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid camera_mode '{camera_mode}'. "
                   f"Must be one of: {', '.join(sorted(VALID_MODES))}",
        )

    # ── parse timestamps ──────────────────────────────────────
    try:
        ts_list: list[float] = json.loads(timestamps)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="timestamps must be a JSON array of floats",
        )

    if not isinstance(ts_list, list) or not all(isinstance(v, (int, float)) for v in ts_list):
        raise HTTPException(
            status_code=422,
            detail="timestamps must be a JSON array of floats",
        )

    if len(ts_list) != len(frames):
        raise HTTPException(
            status_code=422,
            detail=f"timestamps length {len(ts_list)} != frames length {len(frames)}",
        )

    if len(frames) > MAX_FRAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Too many frames ({len(frames)}). Max is {MAX_FRAMES}. "
                   "Use 1-3 fps for clips up to 30s.",
        )

    # ── read all JPEG bytes upfront ───────────────────────────
    frame_data: list[tuple[int, float, bytes]] = []
    for i, (upload, ts) in enumerate(zip(frames, ts_list)):
        raw = await upload.read()

        if len(raw) > MAX_JPEG_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Frame {i} too large ({len(raw)//1024}KB). Max 500KB.",
            )

        if not raw[:3] == b'\xff\xd8\xff':
            raise HTTPException(
                status_code=415,
                detail=f"Frame {i} is not a valid JPEG.",
            )

        frame_data.append((i, round(float(ts), 3), raw))

    # ── load current config from Redis ────────────────────────
    config_envelope = await get_config()
    config = config_envelope["values"]

    # ── override rate limiter for test speed ──────────────────
    config["gemini_min_interval_sec"] = 1.0
    logger.debug("clip_test: overriding gemini_min_interval_sec to 1.0 for test run")

    # ── synthetic camera ID (fully isolated per request) ──────
    synthetic_id = f"clip-test-{uuid.uuid4().hex[:8]}"

    # ── access shared pipeline_manager and redis_client from app state ──
    pipeline_manager = request.app.state.pipeline_manager
    if pipeline_manager is None:
        raise HTTPException(
            status_code=500,
            detail="PipelineManager not available (not initialized at startup)",
        )

    redis_client = request.app.state.pipeline_v2.redis
    if redis_client is None:
        raise HTTPException(
            status_code=500,
            detail="Upstash Redis client not available (PipelineV2 not initialized)",
        )

    # ── create per-request PipelineV2 instance ─────────────────
    pv2 = PipelineV2(pipeline_manager=pipeline_manager, redis_client=redis_client)

    logger.info(
        "clip_test: %d frames, mode=%s, synthetic_id=%s, conf=%.2f",
        len(frame_data),
        camera_mode,
        synthetic_id,
        config.get("yolo_confidence_threshold", 0.35),
    )

    # ── stream results ────────────────────────────────────────
    return StreamingResponse(
        _stream_pipeline_results(
            frames=frame_data,
            camera_mode=camera_mode,
            config=config,
            synthetic_id=synthetic_id,
            pv2=pv2,
        ),
        media_type="application/x-ndjson",
        headers={
            "X-Frame-Count": str(len(frame_data)),
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )