"""
triggers.py — Trigger API for Vision OS (Hybrid Backend).

Receives frame and audio triggers from client agents and:
  1. Stores them as events in the database (via HybridCRUD)
  2. Feeds them through the AI pipeline for analysis and alerting (via PipelineManager)

Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

import base64
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triggers", tags=["triggers"])

# Global instances (initialized in server.py lifespan)
hybrid_crud: HybridCRUD = None  # type: ignore
pipeline_manager: "PipelineManager" = None  # type: ignore


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

    # Decode base64 image to bytes for pipeline processing
    jpeg_bytes = None
    if image_base64:
        try:
            jpeg_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            logger.warning("Failed to decode image_base64: %s", exc)

    try:
        details = {
            "image_base64": image_base64[:100] + "..." if len(image_base64) > 100 else image_base64,
            "timestamp": timestamp,
            "confidence": trigger_data.get("confidence", 0.0),
        }
        event = await crud.create_event(
            user_id=user_id,
            camera_id=camera_id,
            event_type="motion",
            details=details,
        )

        # ── Feed through AI pipeline ──────────────────────────────
        pipeline_result = None
        if pipeline_manager is not None and jpeg_bytes is not None:
            try:
                pipeline_result = await pipeline_manager.process_trigger(
                    camera_id=camera_id,
                    user_id=user_id,
                    location_id=location_id,
                    mode=mode,
                    jpeg_bytes=jpeg_bytes,
                    motion_result={
                        "pixel_diff": trigger_data.get("confidence", 0) * 100,
                        "diff_category": "trigger" if trigger_data.get("confidence", 0) > 0.5 else "skip",
                    },
                )
                logger.info(
                    "Pipeline result for camera %s: threat=%s, alert=%s, incident=%s",
                    camera_id,
                    pipeline_result.threat_level,
                    pipeline_result.alert_sent,
                    pipeline_result.incident_id,
                )
            except Exception as pipe_err:
                logger.error("Pipeline processing failed for camera %s: %s", camera_id, pipe_err)
                # Don't fail the request — the event was already saved

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
