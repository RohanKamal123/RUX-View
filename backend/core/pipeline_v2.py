"""
pipeline_v2.py — Upgraded pipeline orchestrator for Vision OS.

Wraps the existing CameraPipeline with a smart detection
gate (YOLO nano) and stateful tracker (BoT-SORT via Redis).

Flow:
  JPEG frame
    → YOLO nano gate (filter irrelevant frames)
    → BoT-SORT tracker (assign Track IDs, Redis state)
    → Incident builder (decide if Gemini needed)
    → Existing CameraPipeline.process_trigger() (Gemini + Re-ID + alerts)

Falls back to existing pipeline if YOLO unavailable.
"""

import logging
from typing import Optional

from backend.core.detection.yolo_detector import detect, DetectionResult
from backend.core.detection.botsort_tracker import update_tracks
from backend.core.detection.incident_builder import (
    should_call_gemini,
    record_no_change,
)
from backend.core.pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class PipelineV2:
    """Upgraded pipeline with YOLO gate + BoT-SORT tracking.

    Instantiated once per application lifespan in server.py.
    Shares the existing pipeline_manager for DB and alert routing.
    """

    def __init__(self, pipeline_manager, redis_client):
        """
        Args:
            pipeline_manager: Existing PipelineManager instance.
            redis_client: Upstash async Redis client instance.
        """
        self.pipeline_manager = pipeline_manager
        self.redis = redis_client
        logger.info("PipelineV2 initialized with YOLO gate + BoT-SORT tracker")

    async def process_frame(
        self,
        camera_id: str,
        user_id: str,
        location_id: str,
        mode: str,
        jpeg_bytes: bytes,
        camera_profile: Optional[dict] = None,
    ) -> PipelineResult:
        """Process a single frame through the full v2 pipeline.

        Args:
            camera_id: Camera identifier.
            user_id: Authenticated user ID.
            location_id: Location grouping ID.
            mode: Camera mode (indoor/outdoor/parking/shop/mixed).
            jpeg_bytes: Raw JPEG frame bytes from client agent.
            camera_profile: Optional camera config dict for Gemini context.

        Returns:
            PipelineResult from the underlying CameraPipeline.
            Returns no_change result immediately if YOLO gate blocks.
        """
        # ── Stage 1: YOLO detection gate ─────────────────────────
        detection_result: DetectionResult = detect(jpeg_bytes, annotate=True)

        if not detection_result.has_relevant_objects:
            logger.debug(
                "YOLO gate: no relevant objects on camera %s — skipping Gemini",
                camera_id,
            )
            return PipelineResult(
                incident_id=None,
                threat_level="LOW",
                change_detected=False,
            )

        logger.debug(
            "YOLO gate: %s detected on camera %s",
            detection_result.object_summary,
            camera_id,
        )

        # ── Stage 2: BoT-SORT tracking ───────────────────────────
        tracking_result = await update_tracks(
            camera_id=camera_id,
            detections=detection_result.detections,
            redis_client=self.redis,
        )

        # ── Stage 3: Incident builder decision ───────────────────
        decision = should_call_gemini(camera_id, tracking_result)

        if not decision.should_call_gemini:
            logger.debug(
                "Incident builder: skip Gemini for camera %s (%s)",
                camera_id,
                decision.reason,
            )
            return PipelineResult(
                incident_id=None,
                threat_level="LOW",
                change_detected=False,
            )

        logger.info(
            "Incident builder: calling Gemini for camera %s — %s",
            camera_id,
            decision.reason,
        )

        # ── Stage 4: Existing pipeline (Gemini + Re-ID + alerts) ─
        # Use annotated frame (with bounding boxes) for richer Gemini context
        frame_to_send = (
            detection_result.annotated_jpeg
            if detection_result.annotated_jpeg
            else jpeg_bytes
        )

        # Build enriched motion_result with YOLO + tracker context
        motion_result = {
            "pixel_diff": 9999,  # Force past all pixel diff thresholds
            "diff_category": "trigger",
            "yolo_summary": detection_result.object_summary,
            "track_summary": tracking_result.track_summary,
            "track_context": decision.enriched_prompt_context,
            "new_tracks": len(tracking_result.new_tracks),
            "total_tracks": len(tracking_result.tracks),
        }

        ctx = PipelineContext(
            camera_id=camera_id,
            user_id=user_id,
            location_id=location_id,
            mode=mode,
            jpeg_bytes=frame_to_send,
            motion_result=motion_result,
            camera_profile=camera_profile,
        )

        result = await self.pipeline_manager.process_trigger(
            camera_id=camera_id,
            user_id=user_id,
            location_id=location_id,
            mode=mode,
            jpeg_bytes=frame_to_send,
            motion_result=motion_result,
            camera_profile=camera_profile,
        )

        # If Gemini returned NO_CHANGE, record it so
        # incident_builder extends the skip window
        if result and not result.change_detected:
            record_no_change(camera_id)

        return result