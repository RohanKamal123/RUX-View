"""
audio_correlation.py — Audio-Visual Correlation for Vision OS.

Correlates audio triggers (YAMNet classified) with open visual incidents
within configurable time windows. Supports same-camera and neighbour-camera
matching. Falls back to audio-only when no visual incident is open.

Key Decisions:
- D003: Groq Whisper-compatible API for Bangla transcription (NOT OpenAI Whisper)
- D005: Trigger-only (not continuous streaming)
- D020: Whisper transcript stored only 1-3 days
- D026: All calls async
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.storage.database import AudioEvent, Event

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────

SAME_CAMERA_WINDOW_SECONDS = 10
NEIGHBOUR_CAMERA_WINDOW_SECONDS = 15
TRANSCRIPT_RETENTION_DAYS = 3

# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class AudioVisualMatch:
    """Result of correlating an audio trigger with visual incidents."""

    matched: bool
    incident_id: Optional[str] = None
    camera_id: Optional[str] = None
    time_gap_seconds: Optional[float] = None
    correlation_type: str = "none"
    # correlation_type values: "visual_open" / "neighbour_visual" / "audio_only"


@dataclass
class AudioIncidentResult:
    """Result of processing an audio trigger end-to-end."""

    incident_id: str
    threat_level: str = "LOW"  # LOW/MEDIUM/HIGH
    transcript: Optional[str] = None
    interpretation: Optional[str] = None
    has_visual_match: bool = False
    matched_camera_id: Optional[str] = None


# ── HIGH Threat YAMNet classes ────────────────────────────────

HIGH_THREAT_SOUNDS = {
    "Glass breaking",
    "Gunshot, gunfire",
    "Scream",
    "Explosion",
    "Fire engine, fire truck (siren)",
    "Police car (siren)",
    "Ambulance (siren)",
    "Burglar alarm",
}

SPEECH_CLASSES = {
    "Speech",
    "Conversation",
    "Narration, monologue",
    "Babbling",
    "Shout",
    "Yell",
}


# ── AudioCorrelator ────────────────────────────────────────────


class AudioCorrelator:
    """Correlate audio triggers with visual incidents.

    Matches audio triggers to open visual incidents within configurable
    time windows. Supports same-camera and neighbour-camera correlation.
    """

    def __init__(self, db_session_factory: Any, ai_client: Any):
        """Initialize audio correlator.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            ai_client: AI client for Gemini interpretation.
        """
        self.db_session_factory = db_session_factory
        self.ai_client = ai_client

    async def correlate(
        self,
        camera_id: str,
        location_id: str,
        timestamp: datetime,
        yamnet_result: dict,
    ) -> AudioVisualMatch:
        """Check if audio trigger correlates with an open visual incident.

        Steps:
        1. Query open incidents on same camera within ±10s window
        2. If no match, query neighbour cameras within ±15s window
        3. If no match, return audio_only

        Args:
            camera_id: Camera that detected the audio.
            location_id: Location of the camera.
            timestamp: When the audio was detected.
            yamnet_result: YAMNet classification result dict.

        Returns:
            AudioVisualMatch with correlation result.
        """
        async with self.db_session_factory() as session:
            # Step 1: Check same camera within ±10s
            match = await self._find_open_incident(
                session, camera_id, timestamp, SAME_CAMERA_WINDOW_SECONDS
            )
            if match:
                return AudioVisualMatch(
                    matched=True,
                    incident_id=match["incident_id"],
                    camera_id=camera_id,
                    time_gap_seconds=match["time_gap"],
                    correlation_type="visual_open",
                )

            # Step 2: Check neighbour cameras within ±15s
            topology = await self._get_location_topology(session, location_id)
            neighbour_cameras = self._get_neighbour_cameras(camera_id, topology)

            for neighbour_id in neighbour_cameras:
                match = await self._find_open_incident(
                    session, neighbour_id, timestamp, NEIGHBOUR_CAMERA_WINDOW_SECONDS
                )
                if match:
                    return AudioVisualMatch(
                        matched=True,
                        incident_id=match["incident_id"],
                        camera_id=neighbour_id,
                        time_gap_seconds=match["time_gap"],
                        correlation_type="neighbour_visual",
                    )

            # Step 3: No match — audio only
            return AudioVisualMatch(
                matched=False,
                correlation_type="audio_only",
            )

    async def process_audio_trigger(
        self,
        camera_id: str,
        location_id: str,
        user_id: str,
        timestamp: datetime,
        audio_bytes: Optional[bytes],
        yamnet_result: dict,
    ) -> AudioIncidentResult:
        """Process an audio trigger end-to-end.

        Steps:
        1. Correlate with visual incidents
        2. If speech detected AND (after hours OR HIGH threat): transcribe via Groq
        3. If transcript available: interpret via Gemini
        4. Save audio_event to database
        5. Return AudioIncidentResult

        Args:
            camera_id: Camera that detected the audio.
            location_id: Location of the camera.
            user_id: User who owns the camera.
            timestamp: When the audio was detected.
            audio_bytes: Raw audio bytes for transcription (optional).
            yamnet_result: YAMNet classification result dict.

        Returns:
            AudioIncidentResult with processing results.
        """
        # Step 1: Correlate with visual incidents
        visual_match = await self.correlate(camera_id, location_id, timestamp, yamnet_result)

        # Determine threat level from YAMNet
        threat_level = self._get_threat_from_yamnet(yamnet_result)

        # Step 2: Check if we should transcribe
        is_after_hours = self._is_after_hours(timestamp)
        should_transcribe = self._should_transcribe(yamnet_result, is_after_hours)

        transcript = None
        interpretation = None

        if should_transcribe and audio_bytes:
            try:
                # Step 2: Transcribe via Groq
                transcript = await self._transcribe_audio(audio_bytes)
            except Exception as exc:
                logger.error("Transcription failed: %s", exc, exc_info=True)

        # Step 3: Interpret transcript via Gemini
        if transcript:
            visual_context = None
            if visual_match.matched and visual_match.incident_id:
                visual_context = {"incident_id": visual_match.incident_id}

            try:
                interpretation = await self._interpret_transcript(
                    transcript, yamnet_result, visual_context
                )
            except Exception as exc:
                logger.error("Interpretation failed: %s", exc, exc_info=True)

        # Step 4: Save audio_event to database
        incident_id = f"AUDIO_{timestamp.strftime('%Y%m%d%H%M%S')}_{camera_id}"
        expires_at = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
        expires_at = expires_at.replace(hour=0, minute=0, second=0, microsecond=0)
        expires_at = expires_at.replace(day=expires_at.day + TRANSCRIPT_RETENTION_DAYS)

        async with self.db_session_factory() as session:
            audio_event = AudioEvent(
                camera_id=camera_id,
                user_id=user_id,
                timestamp=timestamp,
                yamnet_class=yamnet_result.get("class_name", "Unknown"),
                yamnet_confidence=yamnet_result.get("confidence", 0.0),
                whisper_transcript=transcript,
                gemini_interpretation=interpretation,
                threat_level=threat_level,
                has_visual_match=visual_match.matched,
                expires_at=expires_at,
            )
            session.add(audio_event)
            await session.flush()
            await session.commit()

        # Step 5: Return result
        return AudioIncidentResult(
            incident_id=incident_id,
            threat_level=threat_level,
            transcript=transcript,
            interpretation=interpretation,
            has_visual_match=visual_match.matched,
            matched_camera_id=visual_match.camera_id,
        )

    async def _transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe audio using Groq Whisper-compatible API.

        Uses whisper-large-v3-turbo for fast, accurate Bangla transcription.

        Args:
            audio_bytes: Raw audio bytes (WAV, MP3, etc.).

        Returns:
            Bangla transcript text or None if failed.
        """
        try:
            from backend.ai.groq_client import transcribe_audio as groq_transcribe

            transcript = await groq_transcribe(audio_bytes)
            return transcript if transcript else None
        except Exception as exc:
            logger.error("Groq transcription failed: %s", exc, exc_info=True)
            return None

    async def _interpret_transcript(
        self,
        transcript: str,
        yamnet_result: dict,
        visual_context: Optional[dict],
    ) -> str:
        """Interpret transcript using Gemini 2.0 Flash.

        Args:
            transcript: Bangla transcript text.
            yamnet_result: YAMNet classification result dict.
            visual_context: Optional visual incident context.

        Returns:
            English interpretation string.
        """
        try:
            from backend.ai.ai_client import answer_query

            # Build a prompt for interpretation
            yamnet_class = yamnet_result.get("class_name", "Unknown")
            confidence = yamnet_result.get("confidence", 0.0)

            context_parts = [
                f"Audio class: {yamnet_class} (confidence: {confidence:.2f})",
                f"Transcript: {transcript}",
            ]
            if visual_context:
                context_parts.append(f"Visual context: {visual_context}")

            context_str = "\n".join(context_parts)

            prompt = (
                f"You are a security analyst interpreting audio from a CCTV system in Bangladesh.\n\n"
                f"{context_str}\n\n"
                f"Provide a brief English interpretation of what this audio means for security. "
                f"Is this a threat? What action should be taken? Be concise."
            )

            interpretation = await self.ai_client.generate_content_async(prompt)
            result = interpretation.text.strip() if hasattr(interpretation, "text") else str(interpretation).strip()
            return result
        except Exception as exc:
            logger.error("Gemini interpretation failed: %s", exc, exc_info=True)
            return f"Audio detected: {yamnet_result.get('class_name', 'Unknown sound')}"

    def _should_transcribe(self, yamnet_result: dict, is_after_hours: bool) -> bool:
        """Check if audio should be transcribed based on YAMNet class + time.

        Transcribe if:
        - Speech detected AND confidence > 0.8
        - Any HIGH threat sound (glass breaking, gunshot, scream)
        - After hours AND any sound > 0.7 confidence

        Args:
            yamnet_result: YAMNet classification result dict.
            is_after_hours: Whether the current time is after business hours.

        Returns:
            True if audio should be transcribed.
        """
        class_name = yamnet_result.get("class_name", "")
        confidence = yamnet_result.get("confidence", 0.0)

        # HIGH threat sounds always get transcribed
        if class_name in HIGH_THREAT_SOUNDS:
            return True

        # Speech with high confidence
        if class_name in SPEECH_CLASSES and confidence > 0.8:
            return True

        # After hours: any sound with high confidence
        if is_after_hours and confidence > 0.7:
            return True

        return False

    def _get_threat_from_yamnet(self, yamnet_result: dict) -> str:
        """Map YAMNet class to threat level.

        glass_breaking/gunshot/scream → HIGH
        shout/vehicle_alarm → MEDIUM
        speech/footsteps/engine → LOW

        Args:
            yamnet_result: YAMNet classification result dict.

        Returns:
            Threat level string: "HIGH", "MEDIUM", or "LOW".
        """
        class_name = yamnet_result.get("class_name", "")

        if class_name in HIGH_THREAT_SOUNDS:
            return "HIGH"

        # MEDIUM threat sounds
        medium_threats = {
            "Shout",
            "Yell",
            "Vehicle horn, car horn, honking",
            "Bicycle bell",
            "Alarm",
            "Doorbell",
            "Door",
            "Creak",
        }
        if class_name in medium_threats:
            return "MEDIUM"

        # Default to LOW
        return "LOW"

    def _get_neighbour_cameras(self, camera_id: str, topology: dict) -> list[str]:
        """Get neighbouring cameras from topology config.

        Args:
            camera_id: The camera to find neighbours for.
            topology: Location topology dict with camera adjacency info.

        Returns:
            List of neighbour camera IDs.
        """
        if not topology:
            return []

        # Topology format: {"cameras": {"cam_01": {"neighbours": ["cam_02", "cam_03"]}, ...}}
        cameras = topology.get("cameras", {})
        camera_config = cameras.get(camera_id, {})
        neighbours = camera_config.get("neighbours", [])

        # Also check reverse adjacency
        for cam_id, config in cameras.items():
            if cam_id != camera_id and camera_id in config.get("neighbours", []):
                if cam_id not in neighbours:
                    neighbours.append(cam_id)

        return neighbours

    def _is_after_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is outside typical business hours (22:00-06:00).

        Args:
            timestamp: The time to check.

        Returns:
            True if after hours (night time).
        """
        hour = timestamp.hour
        return hour < 6 or hour >= 22

    async def _find_open_incident(
        self,
        session: AsyncSession,
        camera_id: str,
        timestamp: datetime,
        window_seconds: int,
    ) -> Optional[dict]:
        """Find an open incident on a camera within a time window.

        Args:
            session: Database session.
            camera_id: Camera to check.
            timestamp: Reference timestamp.
            window_seconds: Time window in seconds.

        Returns:
            Dict with incident_id and time_gap, or None.
        """
        from sqlalchemy import text

        # Use a time-based window query
        stmt = text("""
            SELECT id, incident_id,
                   EXTRACT(EPOCH FROM (:ts - timestamp_start)) AS time_gap
            FROM events
            WHERE camera_id = :camera_id
              AND timestamp_start BETWEEN (:ts - INTERVAL ':window seconds')
                                     AND (:ts + INTERVAL ':window seconds')
              AND threat_level IS NOT NULL
            ORDER BY ABS(EXTRACT(EPOCH FROM (:ts - timestamp_start)))
            LIMIT 1
        """)

        result = await session.execute(
            stmt,
            {
                "camera_id": camera_id,
                "ts": timestamp,
                "window": window_seconds,
            },
        )
        row = result.fetchone()
        if row:
            return {
                "incident_id": row.incident_id,
                "time_gap": abs(float(row.time_gap)) if row.time_gap else None,
            }
        return None

    async def _get_location_topology(
        self, session: AsyncSession, location_id: str
    ) -> dict:
        """Get camera topology for a location.

        Args:
            session: Database session.
            location_id: Location to get topology for.

        Returns:
            Topology dict or empty dict.
        """
        from backend.storage.database import Location

        result = await session.execute(
            select(Location).where(Location.id == location_id)
        )
        location = result.scalar_one_or_none()
        if location and location.camera_topology:
            return location.camera_topology
        return {}
