"""
triggers.py — Trigger API stubs for Vision OS.

Handles incoming frame and audio triggers from Vision OS Connect client.
All routes are protected with Firebase Auth.
Real logic will be added in Phase 3.
"""

import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.dashboard.auth import get_current_user

router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.post("/frame")
async def receive_frame_trigger(
    jpeg: UploadFile = File(...),
    motion_result: str = Form(...),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Receive JPEG trigger from Vision OS Connect client.

    Args:
        jpeg: JPEG image file.
        motion_result: Motion detection result string.
        camera_id: Camera identifier.
        timestamp: ISO format timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status and incident_id.

    TODO: Sprint 3.6 — call pipeline.process_trigger()
    """
    incident_id = f"INC_{uuid.uuid4().hex[:8].upper()}"

    return {
        "status": "received",
        "incident_id": incident_id,
        "camera_id": camera_id,
        "timestamp": timestamp,
    }


@router.post("/audio")
async def receive_audio_trigger(
    audio: UploadFile = File(...),
    yamnet_result: str = Form(...),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Receive audio trigger from Vision OS Connect client.

    Args:
        audio: Audio file (WAV).
        yamnet_result: YAMNet classification result string.
        camera_id: Camera identifier.
        timestamp: ISO format timestamp.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with status and audio_event_id.

    TODO: Sprint 4.1 — audio-visual correlation
    """
    audio_event_id = f"AUD_{uuid.uuid4().hex[:8].upper()}"

    return {
        "status": "received",
        "audio_event_id": audio_event_id,
        "camera_id": camera_id,
        "timestamp": timestamp,
    }
