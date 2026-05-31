"""
triggers.py — Trigger API for Vision OS (Hybrid Backend).

Receives frame and audio triggers from client agents and:
  1. Stores them as events in the database (via HybridCRUD)
  2. Feeds them through the AI pipeline for analysis and alerting (via PipelineManager)
  3. Updates the event record with pipeline results (threat_level, alert_message, person_ids)
  4. Serves event images via GET /api/triggers/image/{event_id}

Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

import base64
import logging
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triggers", tags=["triggers"])

# Global instances (initialized in server.py lifespan)
hybrid_crud: HybridCRUD = None  # type: ignore
pipeline_manager: "PipelineManager" = None  # type: ignore

# Per-camera cooldown tracking: camera_id -> last_event_timestamp (seconds since epoch)
_last_event_time: dict[str, float] = {}
_COOLDOWN_SECONDS = 30
_MIN_CONFIDENCE = 0.3



def get_crud() -> HybridCRUD:
    """Dependency to get the HybridCRUD instance.

    Returns:
        HybridCRUD instance.

    Raises:
        HTTPException 503: If no storage backend is available.
    """
    if hybrid_crud is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Storage not initialized", "code": "STORAGE_UNAVAILABLE"},
        )
    return hybrid_crud


@router.post("/frame")
async def receive_frame_trigger(
    trigger_data: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Receive a frame trigger from a client agent.

    Creates an event with the frame data encoded as base64, then feeds
    the trigger through the AI pipeline for analysis and alerting.
    After pipeline processing, updates the event record with the
    Gemini analysis result (threat_level, alert_message, person_ids).

    Args:
        trigger_data: Dict with camera_id, image_base64, timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with event_id, status, and pipeline result.

    Raises:
        HTTPException 422: If required fields are missing.
    """
    user_id = user.get("uid", "anonymous")
    camera_id = trigger_data.get("camera_id")
    image_base64 = trigger_data.get("image_base64", "")
    timestamp = trigger_data.get("timestamp", datetime.utcnow().isoformat())
    mode = trigger_data.get("mode", "indoor")
    location_id = trigger_data.get("location_id", user_id)  # Fallback to user_id

    if not camera_id:
        raise HTTPException(status_code=422, detail={
            "error": "camera_id is required", "code": "VALIDATION_ERROR",
        })

    # ── Cooldown check: skip if this camera sent a frame within 30 seconds ──
    now = time.time()
    confidence = trigger_data.get("confidence", 1.0)
    last_time = _last_event_time.get(camera_id, 0.0)
    if now - last_time < _COOLDOWN_SECONDS:
        logger.info(
            "Cooldown active for camera %s (%.1fs since last event, confidence=%.2f) — skipping",
            camera_id, now - last_time, confidence,
        )
        return {
            "event_id": None,
            "status": "skipped",
            "message": f"Cooldown active ({_COOLDOWN_SECONDS}s). Only {now - last_time:.1f}s since last event.",
        }

    # ── Confidence filter: skip low-confidence triggers ──
    if confidence < _MIN_CONFIDENCE:
        logger.info(
            "Low confidence for camera %s (confidence=%.2f < %.2f) — skipping",
            camera_id, confidence, _MIN_CONFIDENCE,
        )
        return {
            "event_id": None,
            "status": "skipped",
            "message": f"Confidence {confidence:.2f} below minimum {_MIN_CONFIDENCE}",
        }

    # Decode base64 image to bytes for pipeline processing
    jpeg_bytes = None
    if image_base64:
        try:
            jpeg_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            logger.warning("Failed to decode image_base64: %s", exc)

    try:
        # Store the full image base64 so it can be served back to the frontend
        details = {
            "image_base64": image_base64,
            "timestamp": timestamp,
            "confidence": confidence,
        }
        event = await crud.create_event(
            user_id=user_id,
            camera_id=camera_id,
            event_type="motion",
            details=details,
        )

        # ── Update cooldown tracker ──
        _last_event_time[camera_id] = now


        # ── Feed through AI pipeline ──────────────────────────────
        pipeline_result = None
        if pipeline_manager is not None and jpeg_bytes is not None:
            logger.info("PIPELINE: pipeline_manager available, calling process_trigger() for camera %s ...", camera_id)
            try:
                pipeline_result = await pipeline_manager.process_trigger(
                    camera_id=camera_id,
                    user_id=user_id,
                    location_id=location_id,
                    mode=mode,
                    jpeg_bytes=jpeg_bytes,
                    motion_result={
                        "pixel_diff": trigger_data.get("confidence", 1.0) * 100,
                        "diff_category": "trigger" if trigger_data.get("confidence", 1.0) > 0.5 else "skip",
                    },
                )
                logger.info(
                    "PIPELINE: process_trigger() returned — threat=%s, alert=%s, incident=%s, persons=%s",
                    pipeline_result.threat_level,
                    pipeline_result.alert_sent,
                    pipeline_result.incident_id,
                    pipeline_result.person_ids,
                )

                # ── Update the event with pipeline results ────────────
                try:
                    await crud.update_event(
                        event_id=event.event_id,
                        threat_level=pipeline_result.threat_level,
                        alert_message=str(pipeline_result.alert_sent),
                        person_ids=pipeline_result.person_ids,
                    )
                    logger.info(
                        "PIPELINE: Updated event %s with pipeline result: threat=%s, persons=%s",
                        event.event_id,
                        pipeline_result.threat_level,
                        pipeline_result.person_ids,
                    )
                except Exception as update_err:
                    logger.error("PIPELINE: Failed to update event with pipeline result: %s", update_err)

            except Exception as pipe_err:
                logger.error("PIPELINE: process_trigger() raised exception for camera %s: %s", camera_id, pipe_err, exc_info=True)
                # Don't fail the request — the event was already saved
        elif pipeline_manager is None:
            logger.warning("PIPELINE: pipeline_manager is None — was PipelineManager initialized on startup?")
        elif jpeg_bytes is None:
            logger.warning("PIPELINE: jpeg_bytes is None — skipping pipeline (image_base64 was empty or failed to decode)")

        response: dict = {
            "event_id": event.event_id,
            "status": "created",
            "message": "Frame trigger recorded",
        }

        # Include pipeline result if available
        if pipeline_result is not None:
            response["pipeline"] = {
                "incident_id": pipeline_result.incident_id,
                "threat_level": pipeline_result.threat_level,
                "alert_sent": pipeline_result.alert_sent,
                "person_ids": pipeline_result.person_ids,
            }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.post("/audio")
async def receive_audio_trigger(
    trigger_data: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Receive an audio trigger from a client agent.

    Creates an event with the audio data encoded as base64, then feeds
    the trigger through the AI pipeline for analysis and alerting.

    Args:
        trigger_data: Dict with camera_id, audio_base64, timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with event_id, status, and pipeline result.

    Raises:
        HTTPException 422: If required fields are missing.
    """
    user_id = user.get("uid", "anonymous")
    camera_id = trigger_data.get("camera_id")
    audio_base64 = trigger_data.get("audio_base64", "")
    timestamp = trigger_data.get("timestamp", datetime.utcnow().isoformat())
    mode = trigger_data.get("mode", "indoor")
    location_id = trigger_data.get("location_id", user_id)  # Fallback to user_id

    if not camera_id:
        raise HTTPException(status_code=422, detail={
            "error": "camera_id is required", "code": "VALIDATION_ERROR",
        })

    # Decode base64 audio to bytes for pipeline processing
    audio_bytes = None
    if audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as exc:
            logger.warning("Failed to decode audio_base64: %s", exc)

    try:
        details = {
            "audio_base64": audio_base64[:100] + "..." if len(audio_base64) > 100 else audio_base64,
            "timestamp": timestamp,
            "confidence": trigger_data.get("confidence", 0.0),
        }
        event = await crud.create_event(
            user_id=user_id,
            camera_id=camera_id,
            event_type="audio",
            details=details,
        )

        # ── Feed through AI pipeline ──────────────────────────────
        pipeline_result = None
        if pipeline_manager is not None:
            try:
                pipeline_result = await pipeline_manager.process_trigger(
                    camera_id=camera_id,
                    user_id=user_id,
                    location_id=location_id,
                    mode=mode,
                    audio_bytes=audio_bytes,
                    yamnet_result=trigger_data.get("yamnet_result"),
                )
                logger.info(
                    "Pipeline result for audio trigger on camera %s: threat=%s",
                    camera_id,
                    pipeline_result.threat_level,
                )
            except Exception as pipe_err:
                logger.error("Pipeline audio processing failed for camera %s: %s", camera_id, pipe_err)

        response: dict = {
            "event_id": event.event_id,
            "status": "created",
            "message": "Audio trigger recorded",
        }

        if pipeline_result is not None:
            response["pipeline"] = {
                "incident_id": pipeline_result.incident_id,
                "threat_level": pipeline_result.threat_level,
                "alert_sent": pipeline_result.alert_sent,
            }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.get("/image/{event_id}")
async def get_event_image(
    event_id: str,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Serve the frame image for a given event.

    Retrieves the event's stored base64 image data and returns it
    as a JPEG response for display in the dashboard.

    Args:
        event_id: The event ID (e.g. "EVT_...").

    Returns:
        JPEG image response.

    Raises:
        HTTPException 404: If event not found or no image data.
    """
    user_id = user.get("uid", "anonymous")
    event = await crud.get_event_by_id(event_id, user_id)

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    image_base64 = event.details.get("image_base64", "") if event.details else ""
    if not image_base64:
        raise HTTPException(status_code=404, detail="No image data for this event")

    try:
        jpeg_bytes = base64.b64decode(image_base64)
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except Exception as exc:
        logger.error("Failed to decode image for event %s: %s", event_id, exc)
        raise HTTPException(status_code=500, detail="Failed to decode image")


@router.get("/recent")
async def get_recent_triggers(
    limit: int = 20,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Get recent triggers for the authenticated user.

    Args:
        limit: Maximum number of triggers to return.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with events list.
    """
    user_id = user.get("uid", "anonymous")
    events = await crud.get_user_events(user_id, limit=limit)
    return {
        "events": [{
            "event_id": e.event_id,
            "camera_id": e.camera_id,
            "event_type": e.event_type,
            "confidence": e.confidence,
            "created_at": e.created_at,
        } for e in events],
        "total": len(events),
    }
