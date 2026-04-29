"""
audio_only_incident.py — Audio-Only Incident Handler for Vision OS.

Handles audio triggers that have NO visual match. Creates audio-only
incidents, routes alerts for HIGH/EMERGENCY threats, and detects
blind-spot patterns (recurring audio-only incidents in same area).

Key Decisions:
- D005: Trigger-only (not continuous streaming)
- D020: Whisper transcript stored only 1-3 days
- D026: All calls async
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select

from backend.storage.database import AudioEvent

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────

BLIND_SPOT_THRESHOLD = 3  # Number of audio-only incidents to flag as blind spot
BLIND_SPOT_HOURS_BACK = 24

# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class AudioOnlyIncident:
    """An audio trigger with no matching visual incident."""

    incident_id: str
    camera_id: str
    location_id: str
    timestamp: datetime
    yamnet_class: str
    yamnet_confidence: float
    transcript: Optional[str] = None
    interpretation: Optional[str] = None
    threat_level: str = "MEDIUM"
    alert_sent: bool = False


# ── YAMNet Threat Mapping ─────────────────────────────────────

YAMNET_THREAT_MAP = {
    # HIGH threat sounds
    "Glass breaking": "HIGH",
    "Gunshot, gunfire": "HIGH",
    "Scream": "HIGH",
    "Explosion": "HIGH",
    "Fire engine, fire truck (siren)": "HIGH",
    "Police car (siren)": "HIGH",
    "Ambulance (siren)": "HIGH",
    "Burglar alarm": "HIGH",
    # MEDIUM threat sounds
    "Shout": "MEDIUM",
    "Yell": "MEDIUM",
    "Vehicle horn, car horn, honking": "MEDIUM",
    "Bicycle bell": "MEDIUM",
    "Alarm": "MEDIUM",
    "Doorbell": "MEDIUM",
    "Door": "MEDIUM",
    "Creak": "MEDIUM",
    "Vehicle alarm": "MEDIUM",
    # LOW threat sounds (default)
    "Speech": "LOW",
    "Conversation": "LOW",
    "Narration, monologue": "LOW",
    "Babbling": "LOW",
    "Footsteps": "LOW",
    "Walk, footsteps": "LOW",
    "Engine": "LOW",
    "Idling": "LOW",
    "Rain": "LOW",
    "Wind": "LOW",
    "Bird": "LOW",
    "Cat": "LOW",
    "Dog": "LOW",
}

SPEECH_CLASSES = {
    "Speech",
    "Conversation",
    "Narration, monologue",
    "Babbling",
    "Shout",
    "Yell",
}


# ── AudioOnlyHandler ───────────────────────────────────────────


class AudioOnlyHandler:
    """Handle audio triggers that have NO visual match.

    Creates audio-only incidents, routes alerts for HIGH threats,
    and detects blind-spot patterns.
    """

    def __init__(self, db_session_factory: Any, alert_router: Any):
        """Initialize audio-only handler.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            alert_router: AlertRouter instance for sending alerts.
        """
        self.db_session_factory = db_session_factory
        self.alert_router = alert_router

    async def handle_audio_only(
        self,
        camera_id: str,
        location_id: str,
        user_id: str,
        timestamp: datetime,
        yamnet_result: dict,
        transcript: Optional[str] = None,
        interpretation: Optional[str] = None,
    ) -> AudioOnlyIncident:
        """Handle an audio trigger with no visual match.

        Steps:
        1. Create audio-only incident
        2. If threat is HIGH or EMERGENCY: route alert immediately
        3. If speech detected: flag as "Sound detected, no visual — possible blind spot"
        4. Save to database

        Args:
            camera_id: Camera that detected the audio.
            location_id: Location of the camera.
            user_id: User who owns the camera.
            timestamp: When the audio was detected.
            yamnet_result: YAMNet classification result dict.
            transcript: Optional Bangla transcript.
            interpretation: Optional Gemini interpretation.

        Returns:
            AudioOnlyIncident with processing results.
        """
        yamnet_class = yamnet_result.get("class_name", "Unknown")
        yamnet_confidence = yamnet_result.get("confidence", 0.0)
        threat_level = self._get_threat_from_yamnet(yamnet_result)

        # Step 1: Create incident ID
        incident_id = (
            f"AUDIO_ONLY_{timestamp.strftime('%Y%m%d%H%M%S')}_{camera_id}"
        )

        # Step 2: Route alert if HIGH threat
        alert_sent = False
        if threat_level == "HIGH":
            alert_sent = await self._route_alert(
                camera_id, location_id, user_id, timestamp,
                yamnet_class, yamnet_confidence, transcript, interpretation,
            )

        # Step 3: Build alert message for speech detection
        alert_message = None
        if yamnet_class in SPEECH_CLASSES:
            alert_message = (
                f"Sound detected, no visual — possible blind spot. "
                f"Audio: {yamnet_class} ({yamnet_confidence:.2f})"
            )

        # Step 4: Save to database
        expires_at = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
        expires_at = expires_at.replace(hour=0, minute=0, second=0, microsecond=0)
        expires_at = expires_at + timedelta(days=3)

        async with self.db_session_factory() as session:
            audio_event = AudioEvent(
                camera_id=camera_id,
                user_id=user_id,
                timestamp=timestamp,
                yamnet_class=yamnet_class,
                yamnet_confidence=yamnet_confidence,
                whisper_transcript=transcript,
                gemini_interpretation=interpretation,
                threat_level=threat_level,
                has_visual_match=False,
                expires_at=expires_at,
            )
            session.add(audio_event)
            await session.flush()
            await session.commit()

        logger.info(
            "Audio-only incident created: %s (threat=%s, alert_sent=%s)",
            incident_id, threat_level, alert_sent,
        )

        return AudioOnlyIncident(
            incident_id=incident_id,
            camera_id=camera_id,
            location_id=location_id,
            timestamp=timestamp,
            yamnet_class=yamnet_class,
            yamnet_confidence=yamnet_confidence,
            transcript=transcript,
            interpretation=interpretation,
            threat_level=threat_level,
            alert_sent=alert_sent,
        )

    async def check_blind_spot_pattern(
        self,
        camera_id: str,
        location_id: str,
        hours_back: int = BLIND_SPOT_HOURS_BACK,
    ) -> dict:
        """Check if a camera has recurring audio-only incidents.

        Pattern: 3+ audio-only incidents in same area within 24h.

        Args:
            camera_id: Camera to check.
            location_id: Location of the camera.
            hours_back: How far back to check (default 24).

        Returns:
            Dict with pattern_detected, count, suggestion.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        async with self.db_session_factory() as session:
            # Count audio-only incidents (no visual match) for this camera
            result = await session.execute(
                select(func.count(AudioEvent.id)).where(
                    and_(
                        AudioEvent.camera_id == camera_id,
                        AudioEvent.timestamp >= cutoff,
                        AudioEvent.has_visual_match == False,  # noqa: E712
                    )
                )
            )
            count = result.scalar() or 0

        pattern_detected = count >= BLIND_SPOT_THRESHOLD

        suggestion = ""
        if pattern_detected:
            suggestion = (
                f"Camera {camera_id} has {count} audio-only incidents in the last "
                f"{hours_back}h. This may indicate a blind spot — consider adding "
                f"a camera covering this area."
            )
        elif count > 0:
            suggestion = (
                f"Camera {camera_id} has {count} audio-only incidents. "
                f"Monitor for blind spot patterns."
            )

        return {
            "pattern_detected": pattern_detected,
            "count": count,
            "suggestion": suggestion,
        }

    async def _route_alert(
        self,
        camera_id: str,
        location_id: str,
        user_id: str,
        timestamp: datetime,
        yamnet_class: str,
        yamnet_confidence: float,
        transcript: Optional[str],
        interpretation: Optional[str],
    ) -> bool:
        """Route an alert for a HIGH threat audio-only incident.

        Args:
            camera_id: Camera that detected the audio.
            location_id: Location of the camera.
            user_id: User who owns the camera.
            timestamp: When the audio was detected.
            yamnet_class: YAMNet class name.
            yamnet_confidence: YAMNet confidence score.
            transcript: Optional Bangla transcript.
            interpretation: Optional Gemini interpretation.

        Returns:
            True if alert was sent successfully.
        """
        try:
            # Build incident dict for alert router
            incident = {
                "threat_level": "HIGH",
                "alert_message": (
                    f"HIGH threat audio detected: {yamnet_class} "
                    f"(confidence: {yamnet_confidence:.2f})"
                ),
                "camera_name": camera_id,
                "timestamp": timestamp.isoformat(),
                "person_ids": [],
            }

            if transcript:
                incident["alert_message"] += f"\nTranscript: {transcript}"
            if interpretation:
                incident["alert_message"] += f"\nInterpretation: {interpretation}"

            # Build user dict
            user = {
                "user_id": user_id,
                "telegram_chat_id": None,  # Will be resolved by alert router
            }

            action = await self.alert_router.route_alert(incident, user, "household")
            return action.channel != "log" or "HIGH" in action.message

        except Exception as exc:
            logger.error("Failed to route audio-only alert: %s", exc, exc_info=True)
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
        return YAMNET_THREAT_MAP.get(class_name, "LOW")
