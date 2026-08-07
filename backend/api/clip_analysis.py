"""
clip_analysis.py — API for clip-based dry-run analysis of the AI pipeline.

Endpoints:
  POST   /api/clip-analysis/upload              — upload mp4 (max 200MB)
  POST   /api/clip-analysis/{clip_id}/run        — run full pipeline on clip, SSE stream
  GET    /api/clip-analysis/{clip_id}/status     — current progress

The run endpoint streams Server-Sent Events with per-frame results.
Every process_frame() call uses dry_run=True — Gemini calls happen for
real, but DB writes, Redis writes, and alert sends are suppressed.

REQUIRED CALLER PATTERN for frame processing loop:
    synthetic_id = f"clip-analysis-{clip_id}"
    try:
        for frame in frames:
            result = await pv2.process_frame(
                camera_id=synthetic_id, dry_run=True, ...)
    finally:
        cleanup_synthetic_camera(synthetic_id)
        pipeline_manager.cleanup_synthetic_camera(synthetic_id)

NOTE: This shares the global Gemini rate limiter (_GEMINI_MIN_INTERVAL=8s)
with production traffic.  Running clip analysis will add ~8s of latency
to any production Gemini calls that happen to land during this run.
Acceptable for now since this is single-user testing on a low-traffic
system.  Revisit with a separate Cloud Run deployment before this
matters at real scale.
"""

import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from starlette.requests import Request

import cv2

from backend.core.config_store import get_config as _get_config
from backend.core.detection.incident_builder import cleanup_synthetic_camera

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clip-analysis", tags=["clip_analysis"])

# In-memory store for upload metadata
_clip_store: dict[str, dict] = {}

# Maximum upload size (200 MB)
MAX_UPLOAD_BYTES = 200 * 1024 * 1024

# Default frames-per-second for extraction (matches production MAIN_LOOP_INTERVAL = 0.1)
DEFAULT_FPS = 10


def _probe_video(path: str) -> tuple[int, float, float]:
    """Probe a video file for total_frames, fps, and duration_sec.
    
    Extracted as a standalone function so tests can mock it easily.
    Returns (total_frames, fps, duration_sec).
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return (0, 0.0, 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration_sec = total_frames / fps if fps > 0 else 0.0
    cap.release()
    return (total_frames, fps, duration_sec)


async def _get_max_frames() -> int:
    """Read max_clip_analysis_frames from config_store, fallback to 1800."""
    try:
        cfg = await _get_config()
        return cfg["values"].get("max_clip_analysis_frames", 1800)
    except Exception:
        return 1800


async def _get_gemini_interval() -> int:
    """Read gemini_interval_sec from config_store, fallback to 60."""
    try:
        cfg = await _get_config()
        return int(cfg["values"].get("gemini_interval_sec", 60))
    except Exception:
        return 60


@router.post("/upload")
async def upload_clip(file: UploadFile = File(...)):
    """Upload a video clip for analysis.

    Accepts mp4 files up to 200MB.  Saves to a temp directory.
    Returns ``{"clip_id": uuid}``.
    """
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(400, detail={"error": "Only .mp4 files are accepted", "code": "INVALID_FORMAT"})

    # Read file bytes incrementally up to 200MB
    contents = b""
    while True:
        chunk = await file.read(8 * 1024 * 1024)  # 8MB chunks
        if not chunk:
            break
        contents += chunk
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, detail={
                "error": "File exceeds 200MB limit",
                "code": "FILE_TOO_LARGE",
                "max_bytes": MAX_UPLOAD_BYTES,
            })

    clip_id = uuid.uuid4().hex
    clip_dir = Path(tempfile.gettempdir()) / "clip_analysis" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clip_dir / "source.mp4"

    clip_path.write_bytes(contents)

    # Probe metadata
    total_frames, fps, duration_sec = _probe_video(str(clip_path))

    _clip_store[clip_id] = {
        "path": str(clip_path),
        "fps": round(fps, 1),
        "duration_sec": round(duration_sec, 1),
        "total_frames": total_frames,
        "frames_done": 0,
        "status": "uploaded",
    }

    logger.info("Clip uploaded: %s (%d frames, %.1fs at %.1ffps)", clip_id, total_frames, duration_sec, fps)
    return {"clip_id": clip_id, "total_frames": total_frames, "duration_sec": round(duration_sec, 1), "source_fps": round(fps, 1)}


@router.post("/{clip_id}/run")
async def run_clip_analysis(clip_id: str, request: Request, fps: int = Form(DEFAULT_FPS)):
    """Run the full pipeline on an uploaded clip, streaming SSE events.

    Safety rail: if estimated frames exceed ``max_clip_analysis_frames``
    (default 1800, configurable via tuning UI), returns 400 error.
    Provide a lower ``?fps=`` override for longer clips.

    Each SSE event is one JSON object per-frame, plus an initial
    ``type: meta`` event with estimates.  On completion a
    ``type: complete`` event is emitted.  On error a
    ``type: error`` event is emitted.
    """
    # Validate clip exists
    clip_info = _clip_store.get(clip_id)
    if clip_info is None:
        raise HTTPException(404, detail={"error": "Clip not found", "code": "NOT_FOUND"})

    # Get pipeline instances from app state
    pv2 = request.app.state.pipeline_v2
    pm = request.app.state.pipeline_manager
    if pv2 is None or pm is None:
        raise HTTPException(503, detail={"error": "Pipeline not available", "code": "PIPELINE_UNAVAILABLE"})

    # Calculate estimated frames at this fps
    frame_interval = 1.0 / max(fps, 0.5)  # Minimum 0.5 fps
    source_fps = clip_info.get("fps", fps)
    source_frames = clip_info.get("total_frames", 0)
    duration_sec = clip_info.get("duration_sec", 0.0)

    if source_frames > 0 and fps > source_fps:
        fps = int(source_fps)  # Cap at source frame rate

    if duration_sec > 0:
        estimated_frames = int(duration_sec / frame_interval)
    elif source_frames > 0:
        # Fallback: estimate from source frame count
        ratio = fps / max(source_fps, 0.5)
        estimated_frames = int(source_frames * ratio)
    else:
        estimated_frames = 1000  # Safe fallback for unknown clips

    max_frames = await _get_max_frames()

    if estimated_frames > max_frames:
        raise HTTPException(400, detail={
            "error": "CLIP_TOO_LONG",
            "estimated_frames": estimated_frames,
            "max_allowed": max_frames,
            "hint": (
                f"Trim the clip or pass a lower fps value (e.g. fps=2). "
                f"At fps={fps}, max clip duration is {max_frames / fps / 60:.1f} minutes. "
                f"Estimated {estimated_frames} frames at {fps}fps."
            ),
        })

    clip_info["status"] = "running"
    clip_info["frames_done"] = 0
    clip_path = clip_info["path"]
    synthetic_id = f"clip-analysis-{clip_id}"

    async def event_generator():
        """SSE event generator with mandatory try/finally cleanup."""
        cap = None
        try:
            # First event: meta (cost/time estimate)
            gemini_interval = await _get_gemini_interval()
            meta_event = {
                "type": "meta",
                "estimated_total_frames": estimated_frames,
                "fps": fps,
                "estimated_duration_minutes": round(estimated_frames / fps / 60, 1),
                "gemini_max_calls": estimated_frames,
                "gemini_effective_ceiling": (
                    f"At most once per {gemini_interval}s per camera session — "
                    f"real call count will be far lower than total frames."
                ),
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            # Open video with OpenCV
            cap = cv2.VideoCapture(clip_path)
            if not cap.isOpened():
                raise RuntimeError(f"Failed to open video: {clip_path}")

            clip_fps = cap.get(cv2.CAP_PROP_FPS)
            if clip_fps <= 0:
                clip_fps = 30.0  # Safe default

            frame_skip = max(1, int(round(clip_fps / fps)))

            frame_number = 0
            frames_extracted = 0

            while frames_extracted < estimated_frames:
                # Read frames, skipping to match target fps
                ret, frame = cap.read()
                if not ret:
                    break  # End of video

                frame_number += 1
                if frame_number % frame_skip != 0:
                    continue

                # Encode frame as JPEG
                _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                jpeg_bytes = jpeg_buffer.tobytes()
                video_timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                # Run the pipeline
                result = await pv2.process_frame(
                    camera_id=synthetic_id,
                    user_id="clip-analysis-user",
                    location_id="clip-analysis-location",
                    mode="indoor",
                    jpeg_bytes=jpeg_bytes,
                    dry_run=True,
                )

                frames_extracted += 1
                clip_info["frames_done"] = frames_extracted

                # Build SSE payload
                event = {
                    "type": "frame",
                    "frame_number": frames_extracted,
                    "video_timestamp_sec": round(video_timestamp_sec, 2),
                    "stage_timings_ms": result.stage_timings_ms or {},
                    "result": {
                        "detections": [],
                        "tracks": [],
                        "gemini_called": result.threat_level not in ("LOW", "TRACKING") or (result.alert_message and result.alert_message != ""),
                        "gemini_skip_reason": result.skip_reason if not result.change_detected else None,
                        "threat_level": result.threat_level,
                        "incident_id": result.incident_id,
                        "suppressed_alerts": result.suppressed_alerts,
                        "suppressed_db_events": result.suppressed_db_events,
                    },
                }

                yield f"data: {json.dumps(event)}\n\n"

            # Final completion event
            clip_info["status"] = "complete"
            yield f"data: {json.dumps({'type': 'complete', 'frames_processed': frames_extracted})}\n\n"

        except Exception as exc:
            clip_info["status"] = "error"
            logger.error("Clip analysis %s failed: %s", clip_id, exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        finally:
            # REQUIRED CLEANUP — runs on success, error, or crash
            if cap is not None:
                cap.release()
            cleanup_synthetic_camera(synthetic_id)
            pm.cleanup_synthetic_camera(synthetic_id)
            logger.info("Clip analysis %s: cleanup complete", clip_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{clip_id}/status")
async def get_clip_status(clip_id: str):
    """Get the current status of a clip analysis run.

    Returns ``frames_done``, ``total_frames``, and ``status``.
    """
    clip_info = _clip_store.get(clip_id)
    if clip_info is None:
        raise HTTPException(404, detail={"error": "Clip not found", "code": "NOT_FOUND"})

    return {
        "clip_id": clip_id,
        "frames_done": clip_info.get("frames_done", 0),
        "total_frames": clip_info.get("total_frames", clip_info.get("frames_done", 0)),
        "status": clip_info.get("status", "unknown"),
    }