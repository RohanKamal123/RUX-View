"""
pipeline.py — Main pipeline orchestrator for Vision OS.

One CameraPipeline instance per camera.
Orchestrates the entire incident flow:
  incident_tracker → gemma → reid → cross_camera → repeat_sighting
  → ghost_detector → gemini_decision → alert_router → database

All calls async, use asyncio.gather() for parallel AI calls (D026).
Trigger-only architecture (D005).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    camera_id: str
    user_id: str
    location_id: str
    mode: str
    timestamp: datetime
    jpeg_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    motion_result: Optional[dict] = None
    yamnet_result: Optional[dict] = None


@dataclass
class PipelineResult:
    incident_id: Optional[str] = None
    threat_level: str = "LOW"
    alert_sent: bool = False
    person_ids: list = field(default_factory=list)
    error: Optional[str] = None


class CameraPipeline:
    """Main pipeline orchestrator for a single camera."""

    def __init__(self, camera_id: str, user_id: str, location_id: str,
                 mode: str = "indoor", db_session_factory=None):
        """Initialize pipeline with all sub-modules.

        Args:
            camera_id: Unique camera identifier.
            user_id: User UUID.
            location_id: Location UUID.
            mode: Camera mode (indoor/outdoor/parking/shop).
            db_session_factory: Factory callable for async DB sessions.
        """
        self.camera_id = camera_id
        self.user_id = user_id
        self.location_id = location_id
        self.mode = mode
        self._db_factory = db_session_factory

        # Sub-modules (lazy-initialized)
        self._incident_tracker = None
        self._reid_engine = None
        self._cross_camera = None
        self._ghost_detector = None
        self._repeat_sighting = None
        self._alert_router = None

        # Shared ReID engine singleton
        self._shared_reid = None

    def _init_tracker(self):
        """Initialize incident tracker."""
        if self._incident_tracker is None:
            from backend.core.incident_tracker import IncidentTracker
            self._incident_tracker = IncidentTracker(
                camera_id=self.camera_id,
                mode=self.mode,
            )

    def _init_reid(self):
        """Initialize Re-ID engine (shared singleton)."""
        if self._shared_reid is None:
            from backend.ai.reid_engine import ReIDEngine
            self._shared_reid = ReIDEngine()
        self._reid_engine = self._shared_reid

    def _init_cross_camera(self):
        """Initialize cross-camera correlator."""
        if self._cross_camera is None:
            from backend.core.cross_camera import CrossCameraCorrelator
            self._cross_camera = CrossCameraCorrelator(
                db_session_factory=self._db_factory,
            )

    def _init_ghost(self):
        """Initialize ghost detector."""
        if self._ghost_detector is None:
            from backend.core.ghost_detector import GhostDetector
            self._ghost_detector = GhostDetector()

    def _init_repeat_sighting(self):
        """Initialize repeat sighting tracker."""
        if self._repeat_sighting is None:
            from backend.core.repeat_sighting import RepeatSightingTracker
            self._repeat_sighting = RepeatSightingTracker()

    def _init_alert_router(self):
        """Initialize alert router."""
        if self._alert_router is None:
            from backend.alerts.alert_router import AlertRouter
            from backend.alerts.telegram_client import TelegramClient
            from backend.alerts.voice_note import VoiceNoteGenerator
            from backend.alerts.sms_client import SMSClient

            # These would be configured from user settings
            telegram = TelegramClient(bot_token="")  # Token from config
            voice = VoiceNoteGenerator()
            sms = SMSClient(api_key="", api_secret="", sender_id="VisionOS")

            self._alert_router = AlertRouter(
                telegram_client=telegram,
                voice_note_generator=voice,
                sms_client=sms,
            )

    async def process_trigger(self, ctx: PipelineContext) -> PipelineResult:
        """Process a trigger through the full pipeline.

        Args:
            ctx: PipelineContext with trigger data.

        Returns:
            PipelineResult with incident outcome.
        """
        try:
            # Initialize all modules
            self._init_tracker()
            self._init_reid()
            self._init_cross_camera()
            self._init_ghost()
            self._init_repeat_sighting()
            self._init_alert_router()

            # Step 1: Run incident tracker
            from backend.core.incident_tracker import TriggerData, IncidentAction

            trigger_data = TriggerData(
                camera_id=ctx.camera_id,
                timestamp=ctx.timestamp,
                pixel_diff=ctx.motion_result.get("pixel_diff", 0) if ctx.motion_result else 0,
                diff_category=ctx.motion_result.get("diff_category", "skip") if ctx.motion_result else "skip",
                jpeg_bytes=ctx.jpeg_bytes,
                audio_bytes=ctx.audio_bytes,
                yamnet_result=ctx.yamnet_result,
            )

            action = await self._incident_tracker.process(trigger_data)

            # If no action needed, return early
            if action == IncidentAction.NONE:
                return PipelineResult(
                    incident_id=self._incident_tracker.incident_id,
                    threat_level="LOW",
                )

            # Step 2: If GEMMA_CALL, run vision analysis
            person_results = []
            if action in (IncidentAction.GEMMA_CALL, IncidentAction.BURST):
                vision_result = await self._run_vision_analysis(ctx)

                # Step 3: If persons found, run Re-ID
                if vision_result.get("persons"):
                    person_ids = await self._run_reid(
                        ctx.jpeg_bytes, vision_result["persons"], ctx
                    )
                    person_results = vision_result["persons"]

                    # Step 4: Run cross-camera correlation (parallel)
                    if person_ids:
                        await self._run_cross_camera_parallel(person_ids, ctx)

                    # Step 5: Record repeat sightings
                    await self._run_repeat_sightings(person_ids, ctx)

                    # Step 6: Track ghost entries
                    await self._run_ghost_tracking(person_ids, ctx)

            # Step 7: If CLOSE_INCIDENT, make decision and route alert
            if action == IncidentAction.CLOSE_INCIDENT:
                decision = await self._make_decision(
                    self._incident_tracker.timeline, ctx, person_results
                )
                result = await self._route_and_save(decision, ctx, person_results)
                self._incident_tracker.reset()
                return result

            # Still tracking — return intermediate result
            return PipelineResult(
                incident_id=self._incident_tracker.incident_id,
                threat_level="TRACKING",
                person_ids=[p.get("person_uid", "") for p in person_results],
            )

        except Exception as exc:
            logger.error(
                "Pipeline error for camera %s: %s",
                ctx.camera_id, exc, exc_info=True,
            )
            return PipelineResult(
                error=str(exc),
                threat_level="LOW",
            )

    async def _run_vision_analysis(self, ctx: PipelineContext) -> dict:
        """Run Gemini vision analysis on the frame.

        Args:
            ctx: PipelineContext with frame data.

        Returns:
            Dict with analysis results (persons, threat_level, etc.).
        """
        try:
            from backend.ai import analyse_frame

            if ctx.jpeg_bytes is None:
                return {"persons": [], "threat_level": "LOW"}

            result = await analyse_frame(
                jpeg_bytes=ctx.jpeg_bytes,
                camera_id=ctx.camera_id,
                mode=ctx.mode,
            )
            return result or {"persons": [], "threat_level": "LOW"}
        except Exception as exc:
            logger.error("Vision analysis failed: %s", exc, exc_info=True)
            return {"persons": [], "threat_level": "LOW"}

    async def _run_reid(self, frame_bytes: Optional[bytes], person_results: list,
                         ctx: PipelineContext) -> list[str]:
        """Run Re-ID on all detected persons.

        Args:
            frame_bytes: JPEG frame bytes.
            person_results: List of person dicts from vision analysis.
            ctx: PipelineContext.

        Returns:
            List of person_uid strings.
        """
        if not frame_bytes or not person_results:
            return []

        person_ids = []
        try:
            import cv2
            import numpy as np

            # Decode JPEG to numpy array
            np_arr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                logger.warning("Failed to decode frame for Re-ID")
                return []

            for person in person_results:
                person_uid, confidence = await self._reid_engine.identify(
                    db=None,  # Would use actual DB session
                    frame=frame,
                    person_result=person,
                    location_id=ctx.location_id,
                    user_id=ctx.user_id,
                )
                person["person_uid"] = person_uid
                person["reid_confidence"] = confidence
                person_ids.append(person_uid)

            # Update incident tracker with person IDs
            self._incident_tracker.person_ids = person_ids

        except Exception as exc:
            logger.error("Re-ID failed: %s", exc, exc_info=True)

        return person_ids

    async def _run_cross_camera_parallel(self, person_ids: list[str],
                                          ctx: PipelineContext) -> None:
        """Run cross-camera correlation for all persons in parallel.

        Args:
            person_ids: List of person UIDs.
            ctx: PipelineContext.
        """
        if not person_ids:
            return

        tasks = []
        for pid in person_ids:
            tasks.append(
                self._cross_camera.correlate_across_cameras(
                    person_uid=pid,
                    source_camera_id=ctx.camera_id,
                    location_id=ctx.location_id,
                    event_timestamp=ctx.timestamp,
                )
            )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for pid, result in zip(person_ids, results):
                if isinstance(result, Exception):
                    logger.error("Cross-camera failed for %s: %s", pid, result)
                elif result and result.matched:
                    logger.info(
                        "Cross-camera match: %s seen on %s (gap=%.1fs)",
                        pid, result.source_camera_id, result.time_gap_seconds,
                    )

    async def _run_repeat_sightings(self, person_ids: list[str],
                                     ctx: PipelineContext) -> None:
        """Record repeat sightings for all persons.

        Args:
            person_ids: List of person UIDs.
            ctx: PipelineContext.
        """
        for pid in person_ids:
            level = await self._repeat_sighting.record_sighting(
                person_uid=pid,
                user_id=ctx.user_id,
                timestamp=ctx.timestamp,
            )
            if level != "none":
                logger.info("Repeat sighting %s: level=%s", pid, level)

    async def _run_ghost_tracking(self, person_ids: list[str],
                                   ctx: PipelineContext) -> None:
        """Track ghost entries for all persons.

        Args:
            person_ids: List of person UIDs.
            ctx: PipelineContext.
        """
        for pid in person_ids:
            await self._ghost_detector.track_entry(
                person_uid=pid,
                camera_id=ctx.camera_id,
                location_id=ctx.location_id,
                timestamp=ctx.timestamp,
            )

    async def _make_decision(self, timeline: list, ctx: PipelineContext,
                              person_results: list) -> dict:
        """Make incident decision with Gemini.

        Args:
            timeline: Incident timeline from tracker.
            ctx: PipelineContext.
            person_results: List of person dicts.

        Returns:
            Decision dict with threat_level, alert_message, etc.
        """
        try:
            from backend.ai import make_incident_decision

            decision = await make_incident_decision(
                timeline=timeline,
                camera_id=ctx.camera_id,
                mode=ctx.mode,
                persons=person_results,
                yamnet_result=ctx.yamnet_result,
            )
            return decision or {
                "threat_level": "LOW",
                "alert_message": "Incident closed",
            }
        except Exception as exc:
            logger.error("Incident decision failed: %s", exc, exc_info=True)
            return {
                "threat_level": "MEDIUM",
                "alert_message": f"Incident closed (decision fallback)",
            }

    async def _route_and_save(self, decision: dict, ctx: PipelineContext,
                               person_results: list) -> PipelineResult:
        """Route alert and save event to database.

        Args:
            decision: Decision dict from Gemini.
            ctx: PipelineContext.
            person_results: List of person dicts.

        Returns:
            PipelineResult with final outcome.
        """
        threat_level = decision.get("threat_level", "LOW")
        alert_message = decision.get("alert_message", "No alert")

        # Build incident dict for alert router
        incident = {
            "threat_level": threat_level,
            "alert_message": alert_message,
            "camera_id": ctx.camera_id,
            "camera_name": ctx.camera_id,  # Would use actual camera name
            "timestamp": ctx.timestamp.isoformat(),
            "person_ids": [p.get("person_uid", "") for p in person_results],
            "jpeg_bytes": ctx.jpeg_bytes,
            "timeline": self._incident_tracker.timeline,
            "sighting_count": len(person_results),
        }

        # Build user dict (would come from DB)
        user = {
            "user_id": ctx.user_id,
            "telegram_chat_id": None,  # From user config
        }

        # Route alert
        alert_sent = False
        try:
            action = await self._alert_router.route_alert(
                incident=incident,
                user=user,
                tier="household",  # From user config
            )
            alert_sent = action.channel != "log"
        except Exception as exc:
            logger.error("Alert routing failed: %s", exc, exc_info=True)

        # Save to database
        try:
            if self._db_factory:
                from backend.storage.crud import save_incident_event
                async with self._db_factory() as db:
                    await save_incident_event(
                        db=db,
                        incident_id=self._incident_tracker.incident_id,
                        camera_id=ctx.camera_id,
                        location_id=ctx.location_id,
                        user_id=ctx.user_id,
                        threat_level=threat_level,
                        alert_message=alert_message,
                        person_ids=[p.get("person_uid", "") for p in person_results],
                        timeline=self._incident_tracker.timeline,
                    )
        except Exception as exc:
            logger.error("Failed to save incident event: %s", exc, exc_info=True)

        return PipelineResult(
            incident_id=self._incident_tracker.incident_id,
            threat_level=threat_level,
            alert_sent=alert_sent,
            person_ids=[p.get("person_uid", "") for p in person_results],
        )

    async def shutdown(self) -> None:
        """Clean shutdown of all sub-modules."""
        logger.info("Shutting down pipeline for camera %s", self.camera_id)
        self._incident_tracker = None
        self._reid_engine = None
        self._cross_camera = None
        self._ghost_detector = None
        self._repeat_sighting = None
        self._alert_router = None
