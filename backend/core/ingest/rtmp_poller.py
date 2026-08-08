"""
rtmp_poller.py — Periodic frame sampler for connection_type="rtmp_push"
cameras.

Registered as an APScheduler job (backend/dashboard/server.py) alongside
db_pool_config_refresh. Each tick: list every enabled rtmp_push camera,
pull one frame from its live stream (backend/core/ingest/rtmp_ingest.py),
and feed it through the exact same session-merge/pipeline logic a
connect/ agent's motion trigger goes through
(backend.api.triggers.process_camera_trigger) -- so an RTMP-push camera
gets identical session-merge, YOLO-gate, and Gemini-throttle behavior to
every other camera type, not a separate code path to maintain.

Known limitation -- NOT safe across multiple Cloud Run instances:
_active_sessions / _session_locks in backend/api/triggers.py are bare
in-memory module globals, one independent copy per process. A single
Cloud Run instance polling is fine (this job's normal operating mode when
traffic doesn't need more than one instance). If Cloud Run scales to
multiple instances, each one runs this poller independently and each
would think it owns the session-merge state for the same camera --
producing exactly the kind of duplicate/fragmented-event problem
test_session_merge.py exists to prevent for HTTP-trigger cameras. Fixing
this for real needs either a distributed lock / leader election so only
one instance polls at a time, or moving session state out of in-process
memory (e.g. into Redis, which config_store.py already depends on) --
neither is done here. Documented rather than deferred silently.
"""

import asyncio
import base64
import logging
from datetime import datetime, timezone

from backend.core.ingest.rtmp_ingest import sample_frame

logger = logging.getLogger(__name__)


async def poll_rtmp_cameras(hybrid_crud, pipeline_v2, rtsp_base: str) -> None:
    """One poll cycle: sample every enabled rtmp_push camera and feed any
    frame obtained through the trigger pipeline.

    Args:
        hybrid_crud: HybridCRUD instance (backend.storage.hybrid_crud).
        pipeline_v2: app.state.pipeline_v2, or None if unavailable --
            process_camera_trigger() already handles a None pipeline_v2
            by falling back to the v1 pipeline, same as the HTTP route.
        rtsp_base: settings.rtmp_ingest_rtsp_base, e.g.
            "rtsp://mediamtx-host:8554".
    """
    try:
        cameras = await hybrid_crud.get_cameras_by_connection_type("rtmp_push")
    except Exception:
        logger.exception("rtmp_poller: failed to list rtmp_push cameras")
        return

    if not cameras:
        return

    await asyncio.gather(*(
        _poll_one_camera(camera, hybrid_crud, pipeline_v2, rtsp_base)
        for camera in cameras
        if camera.rtmp_stream_key
    ))


async def _poll_one_camera(camera, hybrid_crud, pipeline_v2, rtsp_base: str) -> None:
    """Sample and process a single camera. Isolated per-camera try/except
    so one camera's failure (stream offline, decode error, pipeline
    exception) never stops the rest of the batch from being polled."""
    try:
        jpeg_bytes = await asyncio.to_thread(sample_frame, camera.rtmp_stream_key, rtsp_base)
        if jpeg_bytes is None:
            # Normal and expected -- the DVR isn't currently pushing
            # (stream offline), not an error worth logging per-tick.
            return

        # process_camera_trigger() is written for the HTTP route
        # (backend/api/triggers.py) and expects image_base64 for the
        # event's `details` payload -- re-encode rather than changing
        # that function's contract for this one caller.
        image_base64 = base64.b64encode(jpeg_bytes).decode("ascii")

        from backend.api.triggers import process_camera_trigger

        await process_camera_trigger(
            camera_id=camera.camera_id,
            user_id=camera.user_id,
            location_id=camera.user_id,
            mode=camera.mode,
            jpeg_bytes=jpeg_bytes,
            image_base64=image_base64,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            crud=hybrid_crud,
            pipeline_v2=pipeline_v2,
        )
    except Exception:
        logger.exception("rtmp_poller: failed to process camera %s", camera.camera_id)
