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

from backend.config import settings
from backend.core.pipeline import CameraPipeline, PipelineContext, PipelineResult
from backend.storage.engine import create_session

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

        Returns:
            PipelineResult with incident outcome.
        """
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

        # Build pipeline context
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
        )

        # Run the pipeline
        result = await pipeline.process_trigger(ctx)
        return result

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
