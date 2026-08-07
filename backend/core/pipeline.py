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
    camera_profile: Optional[dict] = None  # {name, location, after_hours_enabled, loiter_threshold_sec}
    yolo_detections: list = field(default_factory=list)  # Real YOLO Detection bboxes for Re-ID
    config: Optional[dict] = None  # Runtime tunable config (from config_store)
    dry_run: bool = False  # If True, suppress DB writes, Redis writes, and alert sends


@dataclass
class PipelineResult:
    incident_id: Optional[str] = None
    threat_level: str = "LOW"
    alert_message: str = ""
    alert_sent: bool = False
    person_ids: list = field(default_factory=list)
    change_detected: bool = True
    error: Optional[str] = None
    skip_reason: Optional[str] = None
    dry_run: bool = False  # Mirrors the input dry_run flag for downstream readers
    suppressed_alerts: list = field(default_factory=list)  # Alerts that WOULD have been sent (dry_run only)
    annotated_jpeg_b64: Optional[str] = None  # Base64-encoded JPEG with YOLO bounding boxes drawn
    suppressed_db_events: list = field(default_factory=list)  # Events that WOULD have been written
    stage_timings_ms: dict = field(default_factory=dict)  # Per-stage wall-clock timing


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

        # Frame quality gate state
        self._last_frame_gray: Optional[object] = None  # Previous frame for motion comparison

        # Last structured analysis result (for fallback message fix)
        self._last_structured_result: dict = {}

        # Per-incident Gemini throttle: DISABLED (set to 0).
        # The global 8s floor (_GEMINI_MIN_INTERVAL in ai_client.py) and
        # per-camera 60s ceiling (GEMINI_INTERVAL_SEC in incident_builder.py)
        # are sufficient; this middle layer added nothing but extra dead time.
        self._last_vision_time: Optional[datetime] = None
        self._vision_throttle_seconds = 0

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
            from backend.config import settings

            # Configure from environment settings
            telegram = TelegramClient(bot_token=settings.telegram_bot_token)
            voice = VoiceNoteGenerator()
            sms = SMSClient(
                api_key=settings.ssl_wireless_api_key,
                api_secret=settings.ssl_wireless_api_secret,
                sender_id=settings.ssl_wireless_sid or "VisionOS",
            )

            self._alert_router = AlertRouter(
                telegram_client=telegram,
                voice_note_generator=voice,
                sms_client=sms,
            )

    # ── Frame Quality Gate ──────────────────────────────────────

    def _check_frame_quality(self, jpeg_bytes: bytes,
                              config: Optional[dict] = None) -> bool:
        """Check frame quality before sending to Gemini.

        All thresholds read from *config* with DEFAULTS fallbacks:
        1. Mean brightness below *brightness_gate_min* → too dark, skip
        2. Laplacian variance below *blur_gate_min* → too blurry, skip
        3. Motion area below *motion_percent_gate* → too little motion, skip

        All checks logged at DEBUG level.

        Args:
            jpeg_bytes: JPEG frame bytes.
            config: Optional runtime config dict (e.g. from config_store).

        Returns:
            True if frame passes all quality checks, False if it should be skipped.
        """
        brightness_min = config.get("brightness_gate_min", 30) if config else 30
        blur_min = config.get("blur_gate_min", 50) if config else 50
        px_diff = config.get("pixel_diff_threshold", 25) if config else 25
        motion_pct = config.get("motion_percent_gate", 2.0) if config else 2.0

        try:
            import cv2
            import numpy as np

            # Decode JPEG to numpy array
            np_arr = np.frombuffer(jpeg_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                logger.debug("Frame quality: failed to decode frame")
                return False

            # Check 1: Mean brightness
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness = cv2.mean(gray)[0]
            if mean_brightness < brightness_min:
                logger.debug(
                    "Frame quality: too dark (brightness=%.2f < %d) — skipping",
                    mean_brightness, brightness_min,
                )
                return False

            # Check 2: Blur (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < blur_min:
                logger.debug(
                    "Frame quality: too blurry (laplacian_var=%.2f < %d) — skipping",
                    laplacian_var, blur_min,
                )
                return False

            # Check 3: Motion area (compare with previous frame)
            if self._last_frame_gray is not None:
                diff = cv2.absdiff(self._last_frame_gray, gray)
                _, thresh = cv2.threshold(diff, px_diff, 255, cv2.THRESH_BINARY)
                motion_pixels = cv2.countNonZero(thresh)
                total_pixels = gray.shape[0] * gray.shape[1]
                motion_percent = (motion_pixels / total_pixels) * 100.0

                if motion_percent < motion_pct:
                    logger.debug(
                        "Frame quality: motion too small (%.2f%% < %.1f%%) — skipping",
                        motion_percent, motion_pct,
                    )
                    return False

            # Store current frame for next comparison
            self._last_frame_gray = gray

            return True

        except ImportError:
            # OpenCV not available — skip quality checks
            logger.debug("Frame quality: OpenCV not available, skipping checks")
            return True
        except Exception as exc:
            logger.debug("Frame quality check failed: %s", exc)
            return True  # Pass through on error (fail open)

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
                    dry_run=ctx.dry_run,
                )

            # Step 2: If GEMMA_CALL, run vision analysis
            person_results = []
            if action in (IncidentAction.GEMMA_CALL, IncidentAction.BURST):
                vision_result = await self._run_vision_analysis(ctx)

                # Short-circuit: no change detected — skip alerting entirely
                if vision_result.get("change_detected") is False:
                    logger.debug("No change detected for camera %s — skipping pipeline", ctx.camera_id)
                    return PipelineResult(
                        incident_id=self._incident_tracker.incident_id,
                        threat_level="LOW",
                        change_detected=False,
                        dry_run=ctx.dry_run,
                    )

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
                dry_run=ctx.dry_run,
            )

        except Exception as exc:
            logger.error(
                "Pipeline error for camera %s: %s",
                ctx.camera_id, exc, exc_info=True,
            )
            return PipelineResult(
                error=str(exc),
                threat_level="LOW",
                dry_run=ctx.dry_run if ctx else False,
            )

    async def _run_vision_analysis(self, ctx: PipelineContext) -> dict:
        """Run dual-layer Gemini analysis on the frame.

        Before calling Gemini, runs a frame quality gate:
        - Brightness check (mean < 30 → skip)
        - Blur check (Laplacian variance < 50 → skip)
        - Motion check (< 2% of frame → skip)

        Then runs structured analysis with the new JSON schema.
        Falls back to second-pass analysis if structured returns empty.

        Args:
            ctx: PipelineContext with frame data.

        Returns:
            Dict with analysis results (persons, threat_level, alert_message, etc.).
        """
        try:
            from backend.ai import analyse_frame_structured, analyse_frame

            if ctx.jpeg_bytes is None:
                return {"persons": [], "threat_level": "LOW", "alert_message": ""}

            # ── Frame Quality Gate ──────────────────────────────
            if not self._check_frame_quality(ctx.jpeg_bytes, config=ctx.config):
                # Frame failed quality checks — return empty result
                return {"persons": [], "threat_level": "LOW", "alert_message": ""}

            # ── Per-Incident Gemini Throttle ────────────────────
            throttle_sec = (
                ctx.config.get("per_incident_throttle_sec", self._vision_throttle_seconds)
                if ctx.config else self._vision_throttle_seconds
            )
            now = datetime.now(timezone.utc)
            if self._last_vision_time is not None and throttle_sec > 0:
                elapsed = (now - self._last_vision_time).total_seconds()
                if elapsed < throttle_sec:
                    logger.info(
                        "Throttled: skipping Gemini vision — only %.1fs since last call (min %ds)",
                        elapsed,
                        throttle_sec,
                    )
                    return {"persons": [], "threat_level": "LOW", "alert_message": ""}
            self._last_vision_time = now

            # ── Structured Analysis ─────────────────────────────
            structured = await analyse_frame_structured(
                jpeg_bytes=ctx.jpeg_bytes,
                config=ctx.config,
            )

            # Store for fallback message fix in _make_decision
            self._last_structured_result = structured

            # If structured returned empty (confidence < 0.6), skip
            if not structured:
                logger.debug("Structured analysis returned empty (low confidence)")
                return {"persons": [], "threat_level": "LOW", "alert_message": ""}

            # If structured returned no-change signal, skip
            if structured.get("change_detected") is False:
                logger.debug("Structured analysis returned no-change signal — skipping")
                return {"change_detected": False}

            # Call 2a only — person extraction for Re-ID (no text-only verdict call)
            persons_result = await analyse_frame(jpeg_bytes=ctx.jpeg_bytes,
                                                  config=ctx.config)

            result = persons_result or {}
            # Use structured's threat assessment (from image) as authoritative —
            # it's no longer overwritten by a text-only second-pass verdict
            result["threat_level"] = structured.get("threat_level", "LOW")
            result["alert_message"] = structured.get("description", "")
            result["action"] = structured.get("action", "LOG_ONLY")
            result["event_type"] = structured.get("event_type", "unknown")
            result["structured_confidence"] = structured.get("confidence", 0.0)
            result["structured_description"] = structured.get("description", "")
            result["action_required"] = structured.get("action_required", False)
            result["subject_count"] = structured.get("subject_count", 0)
            result["subject_description"] = structured.get("subject_description", "")
            result["change_detected"] = True
            return result

        except Exception as exc:
            logger.error("Vision analysis failed: %s", exc, exc_info=True)
            return {"persons": [], "threat_level": "LOW", "alert_message": ""}

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

            # Prefer real YOLO bboxes over AI-estimated bbox_normalized
            yolo_bboxes = [d.bbox for d in ctx.yolo_detections] if ctx.yolo_detections else []

            # Open a DB session for Re-ID lookups (pgvector similarity search)
            async with self._db_factory() as db:
                for idx, person in enumerate(person_results):
                    # Use YOLO bbox if available for this index, otherwise fall back to AI estimate
                    if idx < len(yolo_bboxes):
                        person["bbox"] = yolo_bboxes[idx]
                    person_uid, confidence = await self._reid_engine.identify(
                        db=db,
                        frame=frame,
                        person_result=person,
                        location_id=ctx.location_id,
                        user_id=ctx.user_id,
                        config=ctx.config,
                        camera_id=ctx.camera_id,
                    )
                    person["person_uid"] = person_uid
                    person["reid_confidence"] = confidence
                    person_ids.append(person_uid)
                # Only commit if NOT dry_run — dry_run skips all persistence
                if not ctx.dry_run:
                    await db.commit()
                else:
                    await db.rollback()
                    logger.debug("Dry run: rolled back Re-ID DB session for %s", ctx.camera_id)

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
        if ctx.config:
            self._repeat_sighting.set_config(ctx.config)
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
        if ctx.config:
            self._ghost_detector.set_config(ctx.config)
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

        Builds camera profile context string and prepends it to the prompt.

        Args:
            timeline: Incident timeline from tracker.
            ctx: PipelineContext.
            person_results: List of person dicts.

        Returns:
            Decision dict with threat_level, alert_message, etc.
        """
        try:
            from backend.ai import make_incident_decision

            # Build camera profile context (Step 4)
            camera_context = ""
            if ctx.camera_profile:
                profile = ctx.camera_profile
                camera_context = (
                    f"Camera: {profile.get('name', ctx.camera_id)}\n"
                    f"Location: {profile.get('location', ctx.location_id)}\n"
                    f"Type: {profile.get('mode', ctx.mode)}\n"
                    f"Rules: after_hours_alert={profile.get('after_hours_enabled', False)}, "
                    f"loitering_threshold={profile.get('loiter_threshold_sec', 0)}s\n"
                )

            context = {
                "camera_name": ctx.camera_id,
                "camera_mode": ctx.mode,
                "timestamp": ctx.timestamp.isoformat(),
                "location_type": ctx.location_id or "unknown",
                "is_business_hours": "unknown",
                "duration": len(timeline) if timeline else 0,
                "reid_result": "unknown",
                "is_known": False,
                "label": "unknown",
                "audio_context": str(ctx.yamnet_result) if ctx.yamnet_result else "none",
                "history": [],
                "camera_context": camera_context,
            }
            decision = await make_incident_decision(
                timeline=timeline,
                context=context,
            )
            return decision or {
                "threat_level": "LOW",
                "alert_message": "Incident closed",
            }
        except Exception as exc:
            logger.error("Incident decision failed: %s", exc, exc_info=True)
            # Use the structured description from the last analysis instead of hardcoded fallback
            fallback_description = self._last_structured_result.get(
                "description", ""
            )
            if not fallback_description:
                fallback_description = "No analysis available"
            return {
                "threat_level": "MEDIUM",
                "alert_message": f"Incident resolved: {fallback_description}",
            }

    async def _route_and_save(self, decision: dict, ctx: PipelineContext,
                               person_results: list) -> PipelineResult:
        """Route alert and save event to database.

        When dry_run=True, alert sends and DB writes are suppressed.
        Alerts and events that WOULD have been sent are returned in
        the suppressed_alerts / suppressed_db_events fields.

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

        # Build user dict — look up per-user telegram_chat_id from database
        from backend.config import settings as _settings
        telegram_chat_id = None
        if self._db_factory:
            try:
                from backend.storage.database import User as UserModel
                async with self._db_factory() as db:
                    from sqlalchemy import select
                    result = await db.execute(
                        select(UserModel).where(UserModel.id == ctx.user_id)
                    )
                    db_user = result.scalar_one_or_none()
                    if db_user and db_user.telegram_chat_id:
                        telegram_chat_id = db_user.telegram_chat_id
            except Exception as exc:
                logger.error("Failed to fetch user telegram_chat_id: %s", exc)
                # Fallback: use global env var
                telegram_chat_id = _settings.telegram_chat_id or None

        user = {
            "user_id": ctx.user_id,
            "telegram_chat_id": telegram_chat_id,
        }
        logger.info(
            "Alert routing: telegram_bot_token=%s, telegram_chat_id=%s",
            "SET" if _settings.telegram_bot_token else "MISSING",
            telegram_chat_id or "MISSING",
        )

        # Route alert — suppress on dry_run, collect what WOULD have been sent
        alert_sent = False
        suppressed_alerts = []
        if ctx.dry_run:
            logger.info(
                "Dry run: would route alert — threat=%s, message=%s, channel would be based on threat level",
                threat_level, alert_message,
            )
            suppressed_alerts.append({
                "threat_level": threat_level,
                "alert_message": alert_message,
                "person_ids": incident["person_ids"],
            })
        else:
            try:
                action = await self._alert_router.route_alert(
                    incident=incident,
                    user=user,
                    tier="household",  # From user config
                )
                alert_sent = action.channel != "log"
            except Exception as exc:
                logger.error("Alert routing failed: %s", exc, exc_info=True)

        # Save to database — suppress on dry_run
        suppressed_db_events = []
        if ctx.dry_run:
            logger.info(
                "Dry run: would save event — camera=%s, incident=%s, threat=%s",
                ctx.camera_id, self._incident_tracker.incident_id, threat_level,
            )
            suppressed_db_events.append({
                "camera_id": ctx.camera_id,
                "user_id": ctx.user_id,
                "incident_id": self._incident_tracker.incident_id,
                "threat_level": threat_level,
                "alert_message": alert_message,
            })
        else:
            try:
                if self._db_factory:
                    from backend.storage.crud import create_event
                    async with self._db_factory() as db:
                        await create_event(db, {
                            "camera_id": ctx.camera_id,
                            "user_id": ctx.user_id,
                            "location_id": ctx.location_id,
                            "incident_id": self._incident_tracker.incident_id,
                            "timestamp_start": ctx.timestamp,
                            "threat_level": threat_level,
                            "alert_sent": alert_sent,
                            "gemini_decision": {"alert_message": alert_message, "persons": person_results},
                        })
            except Exception as exc:
                logger.error("Failed to save incident event: %s", exc, exc_info=True)

        return PipelineResult(
            incident_id=self._incident_tracker.incident_id,
            threat_level=threat_level,
            alert_message=alert_message,
            alert_sent=alert_sent,
            person_ids=[p.get("person_uid", "") for p in person_results],
            dry_run=ctx.dry_run,
            suppressed_alerts=suppressed_alerts,
            suppressed_db_events=suppressed_db_events,
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