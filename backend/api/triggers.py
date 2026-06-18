"""
triggers.py — Trigger API for Vision OS (Hybrid Backend).

Receives frame and audio triggers from client agents and:
  1. Stores them as events in the database (via HybridCRUD)
  2. Feeds them through the AI pipeline for analysis and alerting (via PipelineManager)
  3. Updates the event record with pipeline results (threat_level, alert_message, person_ids)
  4. Serves event images via GET /api/triggers/image/{event_id}

Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

import asyncio
import base64
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triggers", tags=["triggers"])

# Global instances (initialized in server.py lifespan)
hybrid_crud: HybridCRUD = None  # type: ignore
pipeline_manager: "PipelineManager" = None  # type: ignore

# Threat level ordering (lowest to highest) for session escalation.
# "PENDING" is below "LOW" so that the first Gemini result always
# outranks the initial placeholder when comparing max_threat.
_THREAT_ORDER = {"PENDING": -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3, "EMERGENCY": 4}

# Session timeout: frames arriving within this window of the last motion
# are merged into the existing event; otherwise a new event is created.
SESSION_TIMEOUT_SEC = 45

# Per-camera active session tracking.
# structure per camera_id:
# {
#   "event_id": str,
#   "started_at": datetime,
#   "last_motion_at": datetime,
#   "frame_count": int,
#   "max_threat": str,
# }
_active_sessions: dict[str, dict] = {}

# Handle to the background cleanup task (set by the lifespan in server.py).
_session_cleanup_task: Optional[asyncio.Task] = None


async def _session_cleanup_loop():
    """Background loop that closes out camera sessions that have gone quiet.

    Every 15s it scans `_active_sessions` and any session whose
    `last_motion_at` is older than `SESSION_TIMEOUT_SEC` is closed:
    the event is updated with `timestamp_end`, `duration_sec`, and the
    session's `max_threat`, then the session is dropped from the dict.
    """
    while True:
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            logger.info("Session cleanup loop cancelled — shutting down")
            return
        try:
            now = datetime.now(timezone.utc)
            timed_out = [
                cam_id
                for cam_id, session in _active_sessions.items()
                if (now - session["last_motion_at"]).total_seconds() > SESSION_TIMEOUT_SEC
            ]
            for cam_id in timed_out:
                session = _active_sessions.pop(cam_id, None)
                if session is None:
                    continue
                duration = (now - session["started_at"]).total_seconds()
                crud = hybrid_crud
                if crud is not None:
                    try:
                        await crud.update_event(
                            session["event_id"],
                            timestamp_end=now,
                            duration_sec=int(duration),
                            threat_level=session["max_threat"],
                            frame_count=session["frame_count"],
                        )
                    except Exception as update_err:
                        logger.error(
                            "Cleanup: failed to close event %s: %s",
                            session["event_id"], update_err,
                        )
                logger.info(
                    "Session closed: %s | duration=%.0fs | threat=%s | frames=%d",
                    cam_id, duration, session["max_threat"], session["frame_count"],
                )
        except asyncio.CancelledError:
            logger.info("Session cleanup loop cancelled — shutting down")
            return
        except Exception as loop_err:
            logger.error("Session cleanup loop error: %s", loop_err, exc_info=True)


def start_session_cleanup_loop() -> Optional[asyncio.Task]:
    """Schedule the cleanup loop. Called from server.py lifespan."""
    global _session_cleanup_task
    if _session_cleanup_task is not None and not _session_cleanup_task.done():
        return _session_cleanup_task
    _session_cleanup_task = asyncio.create_task(_session_cleanup_loop())
    logger.info("Session cleanup loop started (interval=15s, timeout=%ds)", SESSION_TIMEOUT_SEC)
    return _session_cleanup_task


def stop_session_cleanup_loop() -> None:
    """Cancel the cleanup loop. Called from server.py lifespan on shutdown."""
    global _session_cleanup_task
    if _session_cleanup_task is not None and not _session_cleanup_task.done():
        _session_cleanup_task.cancel()
        _session_cleanup_task = None
        logger.info("Session cleanup loop stop requested")


class FrameTriggerRequest(BaseModel):
    camera_id: str = Field(..., description="Unique camera identifier")
    image_base64: str = Field("", description="Base64-encoded JPEG frame")
    timestamp: str = Field("", description="ISO 8601 trigger timestamp")
    mode: str = Field("indoor", description="Camera mode: indoor/outdoor/parking/mixed/shop")
    location_id: str = Field("", description="Location ID, defaults to user_id if omitted")
    confidence: float = Field(1.0, description="Motion confidence score 0.0–1.0")


class AudioTriggerRequest(BaseModel):
    camera_id: str = Field(..., description="Unique camera identifier")
    audio_base64: str = Field("", description="Base64-encoded WAV audio chunk")
    timestamp: str = Field("", description="ISO 8601 trigger timestamp")
    mode: str = Field("indoor", description="Camera mode")
    location_id: str = Field("", description="Location ID, defaults to user_id if omitted")
    confidence: float = Field(0.0, description="YAMNet classification confidence")
    yamnet_result: Optional[dict] = Field(None, description="YAMNet classification result dict")


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


@router.post("/frame",
    summary="Receive a frame trigger from a client agent",
    description="Ingests a motion-detected frame from a client agent, creates or extends a session-based event in storage, "
                "feeds the frame through the AI pipeline for threat analysis and alerting, and returns the pipeline result. "
                "Frames arriving within 45s of the last motion are merged into the same incident session.",
    tags=["Triggers"],
    responses={
        200: {"description": "Event created or session updated with pipeline result"},
        401: {"description": "Missing or invalid Firebase token"},
        422: {"description": "Validation error — camera_id is required"},
        500: {"description": "Storage or pipeline processing error"},
    },
)
async def receive_frame_trigger(
    trigger_data: FrameTriggerRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Receive a frame trigger from a client agent.

    Creates an event with the frame data encoded as base64, then feeds
    the trigger through the AI pipeline for analysis and alerting.
    After pipeline processing, updates the event record with the
    Gemini analysis result (threat_level, alert_message, person_ids).

    Args:
        trigger_data: Validated FrameTriggerRequest with camera_id, image_base64, timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with event_id, status, and pipeline result.

    Raises:
        HTTPException 422: If required fields are missing.
    """
    user_id = user.get("uid", "anonymous")
    camera_id = trigger_data.camera_id
    image_base64 = trigger_data.image_base64
    timestamp = trigger_data.timestamp or datetime.utcnow().isoformat()
    mode = trigger_data.mode
    location_id = trigger_data.location_id or user_id  # Fallback to user_id

    # Decode base64 image to bytes for pipeline processing (needed before cooldown check)
    jpeg_bytes = None
    if image_base64:
        try:
            jpeg_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            logger.warning("Failed to decode image_base64: %s", exc)

    if not camera_id:
        raise HTTPException(status_code=422, detail={
            "error": "camera_id is required", "code": "VALIDATION_ERROR",
        })

    confidence = trigger_data.confidence
    now = datetime.now(timezone.utc)

    # ── Session-based deduplication ──
    # Look up the active session for this camera. If one exists and the
    # last motion was within SESSION_TIMEOUT_SEC, this frame belongs to
    # the same incident and we only update the existing event. Otherwise
    # (no session, or the previous one expired) we start a fresh event.
    existing = _active_sessions.get(camera_id)
    session_timed_out = (
        existing is not None
        and (now - existing["last_motion_at"]).total_seconds() >= SESSION_TIMEOUT_SEC
    )
    if session_timed_out:
        # Drop the expired session — a new one will be created below.
        logger.info(
            "Session for camera %s timed out (event %s, %d frames) — closing",
            camera_id, existing["event_id"], existing["frame_count"],
        )
        _active_sessions.pop(camera_id, None)
        existing = None

    try:
        # ── Existing live session: extend it with this frame ──
        if existing is not None:
            session = existing
            session["last_motion_at"] = now
            session["frame_count"] += 1
            logger.info(
                "Session EXTEND camera %s → event %s (frame %d, max_threat=%s)",
                camera_id, session["event_id"], session["frame_count"], session["max_threat"],
            )

            pipeline_result = None
            if jpeg_bytes is not None:
                try:
                    # Try PipelineV2 first (YOLO gate + BoT-SORT + incident builder)
                    pipeline_v2 = getattr(request.app.state, "pipeline_v2", None)
                    if pipeline_v2 is not None:
                        pipeline_result = await pipeline_v2.process_frame(
                            camera_id=camera_id,
                            user_id=user_id,
                            location_id=location_id,
                            mode=mode,
                            jpeg_bytes=jpeg_bytes,
                            camera_profile=trigger_data.camera_profile
                                           if hasattr(trigger_data, "camera_profile")
                                           else None,
                        )
                        if not pipeline_result.change_detected:
                            _active_sessions.pop(camera_id, None)
                            return {"status": "no_change", "camera_id": camera_id}
                    else:
                        # Fallback to existing pipeline if v2 unavailable
                        pipeline_result = await pipeline_manager.process_trigger(
                            camera_id=camera_id,
                            user_id=user_id,
                            location_id=location_id,
                            mode=mode,
                            jpeg_bytes=jpeg_bytes,
                            motion_result={
                                "pixel_diff": confidence * 100,
                                "diff_category": "trigger",
                            },
                        )

                    # Step 3 — NO_CHANGE gating: skip event update entirely
                    if not pipeline_result.change_detected:
                        logger.debug(
                            "NO_CHANGE response for camera %s — skipping event update",
                            camera_id,
                        )
                        return {"status": "no_change", "camera_id": camera_id}

                    new_threat = pipeline_result.threat_level or "LOW"
                    if _THREAT_ORDER.get(new_threat, 0) > _THREAT_ORDER.get(session["max_threat"], 0):
                        logger.info(
                            "Session ESCALATION camera %s event %s: %s → %s",
                            camera_id, session["event_id"], session["max_threat"], new_threat,
                        )
                        session["max_threat"] = new_threat
                        try:
                            await crud.update_event(
                                event_id=session["event_id"],
                                threat_level=pipeline_result.threat_level,
                                alert_message=pipeline_result.alert_message,
                                person_ids=pipeline_result.person_ids,
                                frame_count=session["frame_count"],
                            )
                        except Exception as update_err:
                            logger.error(
                                "Failed to update event %s with escalated threat: %s",
                                session["event_id"], update_err,
                            )
                    else:
                        # Same-or-lower threat: still keep frame_count fresh
                        # so the dashboard sees accurate progress on live cards.
                        try:
                            await crud.update_event(
                                event_id=session["event_id"],
                                frame_count=session["frame_count"],
                            )
                        except Exception as update_err:
                            logger.error(
                                "Failed to bump frame_count on event %s: %s",
                                session["event_id"], update_err,
                            )
                except Exception as pipe_err:
                    logger.error(
                        "Pipeline failed during session extend for camera %s: %s",
                        camera_id, pipe_err, exc_info=True,
                    )
            elif jpeg_bytes is None:
                logger.warning("jpeg_bytes is None — skipping session extend analysis")

            return {
                "event_id": session["event_id"],
                "status": "session_updated",
                "frame_count": session["frame_count"],
                "max_threat": session["max_threat"],
            }

        # ── No live session: create a new event + start a session ──
        details = {
            "image_base64": image_base64,
            "timestamp": timestamp,
            "confidence": confidence,
            "threat_level": "PENDING",
        }
        event = await crud.create_event(
            user_id=user_id,
            camera_id=camera_id,
            event_type="motion",
            details=details,
        )
        logger.info("Event %s created — starting new session for camera %s", event.event_id, camera_id)

        session = {
            "event_id": event.event_id,
            "started_at": now,
            "last_motion_at": now,
            "frame_count": 1,
            "max_threat": "PENDING",
        }
        _active_sessions[camera_id] = session

        pipeline_result = None
        if jpeg_bytes is not None:
            try:
                # Try PipelineV2 first (YOLO gate + BoT-SORT + incident builder)
                pipeline_v2 = getattr(request.app.state, "pipeline_v2", None)
                if pipeline_v2 is not None:
                    pipeline_result = await pipeline_v2.process_frame(
                        camera_id=camera_id,
                        user_id=user_id,
                        location_id=location_id,
                        mode=mode,
                        jpeg_bytes=jpeg_bytes,
                        camera_profile=trigger_data.camera_profile
                                       if hasattr(trigger_data, "camera_profile")
                                       else None,
                    )
                    if not pipeline_result.change_detected:
                        _active_sessions.pop(camera_id, None)
                        return {"status": "no_change", "camera_id": camera_id}
                else:
                    # Fallback to existing pipeline if v2 unavailable
                    pipeline_result = await pipeline_manager.process_trigger(
                        camera_id=camera_id,
                        user_id=user_id,
                        location_id=location_id,
                        mode=mode,
                        jpeg_bytes=jpeg_bytes,
                        motion_result={
                            "pixel_diff": confidence * 100,
                            "diff_category": "trigger" if confidence > 0.5 else "skip",
                        },
                    )

                # NO_CHANGE gating: skip DB write entirely
                if not pipeline_result.change_detected:
                    logger.debug(
                        "NO_CHANGE response for camera %s (new session) — skipping",
                        camera_id,
                    )
                    # Clean up the partial session
                    _active_sessions.pop(camera_id, None)
                    return {"status": "no_change", "camera_id": camera_id}

                new_threat = pipeline_result.threat_level or "LOW"
                session["max_threat"] = new_threat
                try:
                    await crud.update_event(
                        event_id=event.event_id,
                        threat_level=pipeline_result.threat_level,
                        alert_message=pipeline_result.alert_message,
                        person_ids=pipeline_result.person_ids,
                        frame_count=session["frame_count"],
                    )
                except Exception as update_err:
                    logger.error("Failed to update event %s with pipeline result: %s", event.event_id, update_err)
            except Exception as pipe_err:
                logger.error(
                    "Pipeline failed during session create for camera %s: %s",
                    camera_id, pipe_err, exc_info=True,
                )
        elif jpeg_bytes is None:
            logger.warning("jpeg_bytes is None — skipping pipeline (image_base64 was empty or failed to decode)")

        response: dict = {
            "event_id": event.event_id,
            "status": "session_created",
            "frame_count": session["frame_count"],
            "max_threat": session["max_threat"],
        }
        if pipeline_result is not None:
            response["pipeline"] = {
                "incident_id": pipeline_result.incident_id,
                "threat_level": pipeline_result.threat_level,
                "alert_message": pipeline_result.alert_message,
                "alert_sent": pipeline_result.alert_sent,
                "person_ids": pipeline_result.person_ids,
            }
        return response

    except Exception as e:
        # If we partially created a session, drop it so the next frame
        # can start fresh instead of being silently absorbed.
        _active_sessions.pop(camera_id, None)
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.post("/audio",
    summary="Receive an audio trigger from a client agent",
    description="Ingests audio data (base64-encoded WAV) from a client agent, creates an audio event in storage, "
                "feeds the audio through the AI pipeline for speech transcription and threat analysis, "
                "and returns the pipeline result. Supports YAMNet sound classification results.",
    tags=["Triggers"],
    responses={
        200: {"description": "Audio event created with pipeline result"},
        401: {"description": "Missing or invalid Firebase token"},
        422: {"description": "Validation error — camera_id is required"},
        500: {"description": "Storage or pipeline processing error"},
    },
)
async def receive_audio_trigger(
    trigger_data: AudioTriggerRequest,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Receive an audio trigger from a client agent.

    Creates an event with the audio data encoded as base64, then feeds
    the trigger through the AI pipeline for analysis and alerting.

    Args:
        trigger_data: Validated AudioTriggerRequest with camera_id, audio_base64, timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with event_id, status, and pipeline result.

    Raises:
        HTTPException 422: If required fields are missing.
    """
    user_id = user.get("uid", "anonymous")
    camera_id = trigger_data.camera_id
    audio_base64 = trigger_data.audio_base64
    timestamp = trigger_data.timestamp or datetime.utcnow().isoformat()
    mode = trigger_data.mode
    location_id = trigger_data.location_id or user_id  # Fallback to user_id

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
            "confidence": trigger_data.confidence,
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
                    yamnet_result=trigger_data.yamnet_result,
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
                "alert_message": pipeline_result.alert_message,
                "alert_sent": pipeline_result.alert_sent,
            }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.get("/image/{event_id}",
    summary="Serve the frame image for a given event",
    description="Retrieves the base64-encoded JPEG frame from the stored event and returns it as a binary image response. "
                "Use this endpoint to display event snapshots in the dashboard or mobile apps.",
    tags=["Triggers"],
    responses={
        200: {"description": "JPEG image bytes returned successfully", "content": {"image/jpeg": {}}},
        401: {"description": "Missing or invalid Firebase token"},
        404: {"description": "Event not found or no image data for this event"},
        500: {"description": "Failed to decode stored image data"},
    },
)
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


@router.get("/recent",
    summary="Get recent triggers for the authenticated user",
    description="Returns the most recent events (frame and audio triggers) for the authenticated user, ordered by creation time. "
                "Use this endpoint to populate the dashboard event feed. Defaults to the 20 most recent events.",
    tags=["Triggers"],
    responses={
        200: {"description": "List of recent events returned"},
        401: {"description": "Missing or invalid Firebase token"},
    },
)
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
