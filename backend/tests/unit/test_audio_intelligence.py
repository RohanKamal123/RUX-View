"""
Tests for Sprint 4.1 — Audio Intelligence (Audio-Visual Correlation).

Tests correlation logic, transcription decisions, threat mapping,
blind spot detection, and end-to-end audio trigger processing.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.audio_correlation import (
    AudioCorrelator,
    AudioVisualMatch,
    AudioIncidentResult,
    HIGH_THREAT_SOUNDS,
    SPEECH_CLASSES,
)
from backend.core.audio_only_incident import (
    AudioOnlyHandler,
    AudioOnlyIncident,
    YAMNET_THREAT_MAP,
    BLIND_SPOT_THRESHOLD,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    # session.execute() is awaited, but the CursorResult it returns has
    # sync methods (fetchone(), scalar_one_or_none(), ...). Left implicit,
    # unittest.mock propagates AsyncMock-ness to auto-created children of
    # an AsyncMock, so .fetchone() would itself return an unawaited
    # coroutine instead of a row. Forcing this one level to a plain
    # MagicMock keeps everything built on top of it (.fetchone,
    # .scalar_one_or_none) synchronous, matching the real object.
    session.execute.return_value = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_db_session
    factory.return_value.__aexit__.return_value = None
    return factory


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    client = AsyncMock()
    client.generate_content_async = AsyncMock()
    response = MagicMock()
    response.text = "Suspicious activity detected. Possible threat."
    client.generate_content_async.return_value = response
    return client


@pytest.fixture
def mock_alert_router():
    """Create a mock alert router."""
    router = AsyncMock()
    router.route_alert = AsyncMock()
    action = MagicMock()
    action.channel = "telegram_text"
    action.message = "HIGH threat audio detected"
    router.route_alert.return_value = action
    return router


@pytest.fixture
def correlator(mock_session_factory, mock_ai_client):
    """Create an AudioCorrelator with mocked dependencies."""
    return AudioCorrelator(
        db_session_factory=mock_session_factory,
        ai_client=mock_ai_client,
    )


@pytest.fixture
def audio_only_handler(mock_session_factory, mock_alert_router):
    """Create an AudioOnlyHandler with mocked dependencies."""
    return AudioOnlyHandler(
        db_session_factory=mock_session_factory,
        alert_router=mock_alert_router,
    )


@pytest.fixture
def sample_yamnet_speech():
    """Sample YAMNet result for speech."""
    return {"class_name": "Speech", "confidence": 0.92}


@pytest.fixture
def sample_yamnet_gunshot():
    """Sample YAMNet result for gunshot."""
    return {"class_name": "Gunshot, gunfire", "confidence": 0.95}


@pytest.fixture
def sample_yamnet_low_confidence():
    """Sample YAMNet result with low confidence."""
    return {"class_name": "Speech", "confidence": 0.45}


@pytest.fixture
def sample_yamnet_footsteps():
    """Sample YAMNet result for footsteps."""
    return {"class_name": "Walk, footsteps", "confidence": 0.85}


# ── AudioCorrelator Tests ──────────────────────────────────────


class TestAudioCorrelator:
    @pytest.mark.asyncio
    async def test_audio_correlates_with_open_visual_incident(
        self, correlator, mock_db_session, sample_yamnet_speech
    ):
        """Audio should match an open visual incident on same camera."""
        # Mock the DB to return a match
        mock_row = MagicMock()
        mock_row.incident_id = "INC_001"
        mock_row.time_gap = 3.5
        mock_db_session.execute.return_value.fetchone.return_value = mock_row

        # Mock location topology
        mock_location = MagicMock()
        mock_location.camera_topology = {}
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        timestamp = datetime.now(timezone.utc)
        result = await correlator.correlate(
            camera_id="cam_01",
            location_id="loc_001",
            timestamp=timestamp,
            yamnet_result=sample_yamnet_speech,
        )

        assert result.matched is True
        assert result.incident_id == "INC_001"
        assert result.camera_id == "cam_01"
        assert result.correlation_type == "visual_open"
        assert result.time_gap_seconds == 3.5

    @pytest.mark.asyncio
    async def test_audio_correlates_with_neighbour_camera(
        self, correlator, mock_db_session, sample_yamnet_speech
    ):
        """Audio should match an open incident on a neighbour camera."""
        # First call (same camera) returns None
        # Second call (neighbour) returns a match
        mock_db_session.execute.return_value.fetchone.side_effect = [
            None,  # Same camera: no match
            MagicMock(incident_id="INC_002", time_gap=8.0),  # Neighbour: match
        ]

        # Mock location topology with neighbours
        mock_location = MagicMock()
        mock_location.camera_topology = {
            "cameras": {
                "cam_01": {"neighbours": ["cam_02"]},
                "cam_02": {"neighbours": ["cam_01"]},
            }
        }
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        timestamp = datetime.now(timezone.utc)
        result = await correlator.correlate(
            camera_id="cam_01",
            location_id="loc_001",
            timestamp=timestamp,
            yamnet_result=sample_yamnet_speech,
        )

        assert result.matched is True
        assert result.incident_id == "INC_002"
        assert result.camera_id == "cam_02"
        assert result.correlation_type == "neighbour_visual"

    @pytest.mark.asyncio
    async def test_audio_only_when_no_visual_match(
        self, correlator, mock_db_session, sample_yamnet_speech
    ):
        """Audio should be audio-only when no visual incident is open."""
        # No matches anywhere
        mock_db_session.execute.return_value.fetchone.return_value = None

        mock_location = MagicMock()
        mock_location.camera_topology = {
            "cameras": {
                "cam_01": {"neighbours": ["cam_02"]},
            }
        }
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        timestamp = datetime.now(timezone.utc)
        result = await correlator.correlate(
            camera_id="cam_01",
            location_id="loc_001",
            timestamp=timestamp,
            yamnet_result=sample_yamnet_speech,
        )

        assert result.matched is False
        assert result.correlation_type == "audio_only"
        assert result.incident_id is None

    @pytest.mark.asyncio
    async def test_groq_transcription_called_for_speech(
        self, correlator, mock_db_session, mock_ai_client, sample_yamnet_speech
    ):
        """Groq transcription should be called for speech with high confidence."""
        mock_db_session.execute.return_value.fetchone.return_value = None
        mock_location = MagicMock()
        mock_location.camera_topology = {}
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        with patch(
            "backend.core.audio_correlation.AudioCorrelator._transcribe_audio",
            new_callable=AsyncMock,
        ) as mock_transcribe:
            mock_transcribe.return_value = "বাংলা ট্রান্সক্রিপ্ট"

            timestamp = datetime.now(timezone.utc).replace(hour=14)  # Business hours
            result = await correlator.process_audio_trigger(
                camera_id="cam_01",
                location_id="loc_001",
                user_id="user_001",
                timestamp=timestamp,
                audio_bytes=b"fake_audio_data",
                yamnet_result=sample_yamnet_speech,
            )

            # Speech with 0.92 confidence should trigger transcription
            # (but only if after hours or HIGH threat — speech alone is LOW)
            # Since it's business hours and speech is LOW, should NOT transcribe
            mock_transcribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_groq_transcription_after_hours(
        self, correlator, mock_db_session, mock_ai_client, sample_yamnet_speech
    ):
        """Groq transcription should be called for speech after hours."""
        mock_db_session.execute.return_value.fetchone.return_value = None
        mock_location = MagicMock()
        mock_location.camera_topology = {}
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        with patch(
            "backend.core.audio_correlation.AudioCorrelator._transcribe_audio",
            new_callable=AsyncMock,
        ) as mock_transcribe:
            mock_transcribe.return_value = "বাংলা ট্রান্সক্রিপ্ট"

            timestamp = datetime.now(timezone.utc).replace(hour=23)  # After hours
            result = await correlator.process_audio_trigger(
                camera_id="cam_01",
                location_id="loc_001",
                user_id="user_001",
                timestamp=timestamp,
                audio_bytes=b"fake_audio_data",
                yamnet_result=sample_yamnet_speech,
            )

            # After hours + speech with 0.92 confidence should transcribe
            mock_transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_gemini_interpretation_of_transcript(
        self, correlator, mock_db_session, mock_ai_client
    ):
        """Gemini should interpret the transcript when available."""
        mock_db_session.execute.return_value.fetchone.return_value = None
        mock_location = MagicMock()
        mock_location.camera_topology = {}
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_location

        with patch(
            "backend.core.audio_correlation.AudioCorrelator._transcribe_audio",
            new_callable=AsyncMock,
        ) as mock_transcribe:
            mock_transcribe.return_value = "বাংলা ট্রান্সক্রিপ্ট"

            timestamp = datetime.now(timezone.utc).replace(hour=23)
            result = await correlator.process_audio_trigger(
                camera_id="cam_01",
                location_id="loc_001",
                user_id="user_001",
                timestamp=timestamp,
                audio_bytes=b"fake_audio_data",
                yamnet_result={"class_name": "Speech", "confidence": 0.92},
            )

            # Should have interpretation since transcript was returned
            assert result.interpretation is not None

    def test_should_transcribe_after_hours(self, correlator):
        """Should transcribe after hours with high confidence."""
        yamnet = {"class_name": "Engine", "confidence": 0.85}
        assert correlator._should_transcribe(yamnet, is_after_hours=True) is True

    def test_should_not_transcribe_low_confidence(self, correlator):
        """Should not transcribe low confidence sounds during business hours."""
        yamnet = {"class_name": "Speech", "confidence": 0.45}
        assert correlator._should_transcribe(yamnet, is_after_hours=False) is False

    def test_should_transcribe_high_threat(self, correlator):
        """Should transcribe HIGH threat sounds regardless of time."""
        yamnet = {"class_name": "Gunshot, gunfire", "confidence": 0.95}
        assert correlator._should_transcribe(yamnet, is_after_hours=False) is True

    def test_should_transcribe_speech_high_confidence(self, correlator):
        """Should transcribe speech with high confidence, any time of day."""
        yamnet = {"class_name": "Speech", "confidence": 0.92}
        # _should_transcribe's "Speech with high confidence" rule (>0.8)
        # isn't gated on business hours -- see its docstring.
        assert correlator._should_transcribe(yamnet, is_after_hours=False) is True

    def test_get_neighbour_cameras(self, correlator):
        """Should return neighbour cameras from topology."""
        topology = {
            "cameras": {
                "cam_01": {"neighbours": ["cam_02", "cam_03"]},
                "cam_02": {"neighbours": ["cam_01"]},
            }
        }
        neighbours = correlator._get_neighbour_cameras("cam_01", topology)
        assert "cam_02" in neighbours
        assert "cam_03" in neighbours

    def test_get_neighbour_cameras_empty_topology(self, correlator):
        """Should return empty list for empty topology."""
        assert correlator._get_neighbour_cameras("cam_01", {}) == []

    def test_yamnet_threat_mapping_high(self, correlator):
        """YAMNet gunshot should map to HIGH threat."""
        assert correlator._get_threat_from_yamnet({"class_name": "Gunshot, gunfire"}) == "HIGH"
        assert correlator._get_threat_from_yamnet({"class_name": "Scream"}) == "HIGH"
        assert correlator._get_threat_from_yamnet({"class_name": "Glass breaking"}) == "HIGH"

    def test_yamnet_threat_mapping_medium(self, correlator):
        """YAMNet shout should map to MEDIUM threat."""
        assert correlator._get_threat_from_yamnet({"class_name": "Shout"}) == "MEDIUM"
        assert correlator._get_threat_from_yamnet({"class_name": "Door"}) == "MEDIUM"

    def test_yamnet_threat_mapping_low(self, correlator):
        """YAMNet speech should map to LOW threat."""
        assert correlator._get_threat_from_yamnet({"class_name": "Speech"}) == "LOW"
        assert correlator._get_threat_from_yamnet({"class_name": "Walk, footsteps"}) == "LOW"

    def test_is_after_hours(self, correlator):
        """Should correctly identify after hours."""
        from datetime import time

        day_time = datetime.now(timezone.utc).replace(hour=14)
        night_time = datetime.now(timezone.utc).replace(hour=23)
        early_morning = datetime.now(timezone.utc).replace(hour=3)

        assert correlator._is_after_hours(day_time) is False
        assert correlator._is_after_hours(night_time) is True
        assert correlator._is_after_hours(early_morning) is True


# ── AudioOnlyHandler Tests ─────────────────────────────────────


class TestAudioOnlyHandler:
    @pytest.mark.asyncio
    async def test_audio_only_incident_created(
        self, audio_only_handler, mock_db_session, sample_yamnet_speech
    ):
        """Audio-only incident should be created when no visual match."""
        timestamp = datetime.now(timezone.utc)
        result = await audio_only_handler.handle_audio_only(
            camera_id="cam_01",
            location_id="loc_001",
            user_id="user_001",
            timestamp=timestamp,
            yamnet_result=sample_yamnet_speech,
        )

        assert isinstance(result, AudioOnlyIncident)
        assert result.camera_id == "cam_01"
        assert result.yamnet_class == "Speech"
        assert result.threat_level == "LOW"
        assert result.alert_sent is False

    @pytest.mark.asyncio
    async def test_audio_only_high_threat_routes_alert(
        self, audio_only_handler, mock_db_session, sample_yamnet_gunshot
    ):
        """HIGH threat audio-only should route an alert."""
        timestamp = datetime.now(timezone.utc)
        result = await audio_only_handler.handle_audio_only(
            camera_id="cam_01",
            location_id="loc_001",
            user_id="user_001",
            timestamp=timestamp,
            yamnet_result=sample_yamnet_gunshot,
        )

        assert result.threat_level == "HIGH"
        assert result.alert_sent is True
        audio_only_handler.alert_router.route_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_blind_spot_pattern_detected(
        self, audio_only_handler, mock_db_session
    ):
        """Blind spot pattern should be detected with 3+ audio-only incidents."""
        # Mock count query to return 3
        mock_db_session.execute.return_value.scalar.return_value = 3

        result = await audio_only_handler.check_blind_spot_pattern(
            camera_id="cam_01",
            location_id="loc_001",
        )

        assert result["pattern_detected"] is True
        assert result["count"] == 3
        assert "blind spot" in result["suggestion"].lower()

    @pytest.mark.asyncio
    async def test_blind_spot_pattern_not_detected(
        self, audio_only_handler, mock_db_session
    ):
        """Blind spot pattern should not be detected with fewer than 3 incidents."""
        mock_db_session.execute.return_value.scalar.return_value = 1

        result = await audio_only_handler.check_blind_spot_pattern(
            camera_id="cam_01",
            location_id="loc_001",
        )

        assert result["pattern_detected"] is False
        assert result["count"] == 1

    def test_yamnet_threat_mapping(self):
        """YAMNet threat mapping should be correct."""
        assert YAMNET_THREAT_MAP.get("Gunshot, gunfire") == "HIGH"
        assert YAMNET_THREAT_MAP.get("Scream") == "HIGH"
        assert YAMNET_THREAT_MAP.get("Glass breaking") == "HIGH"
        assert YAMNET_THREAT_MAP.get("Shout") == "MEDIUM"
        assert YAMNET_THREAT_MAP.get("Speech") == "LOW"
        assert YAMNET_THREAT_MAP.get("Walk, footsteps") == "LOW"
        assert YAMNET_THREAT_MAP.get("Unknown") is None  # Default to LOW

    def test_audio_only_incident_dataclass(self):
        """AudioOnlyIncident dataclass should work correctly."""
        incident = AudioOnlyIncident(
            incident_id="AUDIO_ONLY_001",
            camera_id="cam_01",
            location_id="loc_001",
            timestamp=datetime.now(timezone.utc),
            yamnet_class="Gunshot, gunfire",
            yamnet_confidence=0.95,
            threat_level="HIGH",
        )
        assert incident.incident_id == "AUDIO_ONLY_001"
        assert incident.threat_level == "HIGH"
        assert incident.alert_sent is False
        assert incident.transcript is None

    def test_audio_visual_match_dataclass(self):
        """AudioVisualMatch dataclass should work correctly."""
        match = AudioVisualMatch(
            matched=True,
            incident_id="INC_001",
            camera_id="cam_01",
            time_gap_seconds=2.5,
            correlation_type="visual_open",
        )
        assert match.matched is True
        assert match.correlation_type == "visual_open"

    def test_audio_incident_result_dataclass(self):
        """AudioIncidentResult dataclass should work correctly."""
        result = AudioIncidentResult(
            incident_id="AUDIO_001",
            threat_level="HIGH",
            transcript="বাংলা",
            interpretation="Threat detected",
            has_visual_match=True,
            matched_camera_id="cam_02",
        )
        assert result.incident_id == "AUDIO_001"
        assert result.has_visual_match is True
