"""
pipeline_manager.py — Manages CameraPipeline instances across all cameras.

One CameraPipeline per camera, created lazily on first trigger.
Orchestrates the full incident flow:
  trigger → incident_tracker → gemini_vision → reid → cross_camera
  → repeat_sighting → ghost_detector → gemini_decision → alert_router → database

Initialized on server startup in the lifespan handler.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from upstash_redis.asyncio import Redis

from backend.config import settings
from backend.core.pipeline import CameraPipeline, PipelineContext, PipelineResult
from backend.storage.engine import create_session

# Upstash Redis client — used for caching, rate-limiting, and real-time state
redis = Redis(url=settings.upstash_redis_rest_url, token=settings.upstash_redis_rest_token)

logger = logging.getLogger(__name__)


class PipelineManager:
    """Manages CameraPipeline instances across all cameras.

    Creates one CameraPipeline per camera on first trigger.
    Provides a unified interface for feeding triggers into the pipeline.
    """

    def __init__(self):
        """Initialize the pipeline manager with an empty camera registry."""
        self._pipelines: dict[str, CameraPipeline] = {}
        self._initialized = False
        logger.info("PipelineManager created (no pipelines yet)")

    async def initialize(self) -> None:
        """Pre-warm the manager. Currently a no-op; pipelines are lazy-created.

        In the future, this could load all active cameras from the database
        and pre-create pipelines for them.
        """
        self._initialized = True
        logger.info("PipelineManager initialized")

    async def process_trigger(
        self,
        camera_id: str,
        user_id: str,
        location_id: str,
        mode: str,
        jpeg_bytes: Optional[bytes] = None,
        audio_bytes: Optional[bytes] = None,
        motion_result: Optional[dict] = None,
        yamnet_result: Optional[dict] = None,
        camera_profile: Optional[dict] = None,
        config: Optional[dict] = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Process a trigger through the pipeline for the given camera.

        Creates a CameraPipeline for this camera if one doesn't exist yet.

        Args:
            camera_id: Unique camera identifier.
            user_id: User UUID.
            location_id: Location UUID.
            mode: Camera mode (indoor/outdoor/parking/shop).
            jpeg_bytes: JPEG frame bytes (optional).
            audio_bytes: Audio bytes (optional).
            motion_result: Motion detection result dict (optional).
            yamnet_result: YAMNet audio classification result (optional).
            camera_profile: Optional dict with name, location, after_hours_enabled,
                           loiter_threshold_sec for camera context in prompts.
            dry_run: If True, DB writes, Redis writes, and alert sends are suppressed.
                     Gemini calls still happen (real behavior visible).

        Returns:
            PipelineResult with incident outcome.
        """
        logger.debug("PipelineManager.process_trigger called for camera %s (dry_run=%s)", camera_id, dry_run)
        # Lazy-create pipeline for this camera
        if camera_id not in self._pipelines:
            self._pipelines[camera_id] = CameraPipeline(
                camera_id=camera_id,
                user_id=user_id,
                location_id=location_id,
                mode=mode,
                db_session_factory=create_session,
            )
            logger.info("Created new pipeline for camera %s (mode=%s)", camera_id, mode)

        pipeline = self._pipelines[camera_id]

        # Build pipeline context — attach dry_run flag so sub-modules can read it
        ctx = PipelineContext(
            camera_id=camera_id,
            user_id=user_id,
            location_id=location_id,
            mode=mode,
            timestamp=datetime.now(timezone.utc),
            jpeg_bytes=jpeg_bytes,
            audio_bytes=audio_bytes,
            motion_result=motion_result,
            yamnet_result=yamnet_result,
            camera_profile=camera_profile,
            config=config,
            dry_run=dry_run,
        )

        # Run the pipeline
        result = await pipeline.process_trigger(ctx)
        return result

    def cleanup_synthetic_camera(self, camera_id: str) -> None:
        """Remove a synthetic (clip-analysis) pipeline instance.

        # REQUIRED CALLER PATTERN (see clip_analysis.py once built):
        #
        #     synthetic_id = f"clip-analysis-{clip_id}"
        #     try:
        #         for frame in frames:
        #             result = await pv2.process_frame(
        #                 camera_id=synthetic_id, dry_run=True, ...)
        #     finally:
        #         cleanup_synthetic_camera(synthetic_id)
        #         self.pipeline_manager.cleanup_synthetic_camera(synthetic_id)
        #
        # This MUST run even if the clip loop crashes partway
        # through (bad frame, OOM, timeout) or synthetic camera
        # state leaks indefinitely across a week of repeated
        # clip-analysis runs.

        Deletes the CameraPipeline so its per-instance state
        (incident tracker, repeat sighting records, ghost entries)
        is garbage collected.  Safe to call even if camera_id
        doesn't exist.
        """
        self._pipelines.pop(camera_id, None)
        logger.debug("Cleaned up synthetic pipeline for camera %s", camera_id)

    async def shutdown(self) -> None:
        """Gracefully shut down all pipelines."""
        logger.info("Shutting down %d pipeline(s)...", len(self._pipelines))
        for camera_id, pipeline in self._pipelines.items():
            try:
                await pipeline.shutdown()
            except Exception as exc:
                logger.error("Error shutting down pipeline for %s: %s", camera_id, exc)
        self._pipelines.clear()
        self._initialized = False
        logger.info("All pipelines shut down")

    @property
    def active_pipelines(self) -> int:
        """Return the number of active pipeline instances."""
        return len(self._pipelines)

    @property
    def is_initialized(self) -> bool:
        """Return whether the manager has been initialized."""
        return self._initialized


# Global singleton — initialized in server.py lifespan
pipeline_manager: PipelineManager = None  # type: ignore
