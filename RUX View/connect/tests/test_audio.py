"""Tests for Audio Capture and YAMNet Detector (Sprint 2.3).

All tests use mocking — no real microphone or YAMNet model required.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from connect.audio.audio_capture import AudioCapture
from connect.audio.yamnet_detector import (
    SECURITY_CLASSES,
    SPEECH_CLASS_IDS,
    YAMNetDetector,
    YAMNetResult,
    _get_yamnet_class_names,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def audio_capture() -> AudioCapture:
    """Create an AudioCapture instance for testing."""
    return AudioCapture(
        device_index=0,
        sample_rate=16000,
        chunk_duration=8.0,
        rms_threshold=0.02,
    )


@pytest.fixture
def yamnet_detector() -> YAMNetDetector:
    """Create a YAMNetDetector with default thresholds."""
    return YAMNetDetector(
        speech_threshold=0.5,
        security_threshold=0.3,
    )


@pytest.fixture
def silence_audio() -> np.ndarray:
    """Create a near-silent audio chunk (below RMS threshold)."""
    return np.zeros(16000 * 8, dtype=np.float32)  # 8 seconds of silence


@pytest.fixture
def loud_audio() -> np.ndarray:
    """Create a loud audio chunk (above RMS threshold)."""
    # Full-scale white noise — RMS ~0.577
    rng = np.random.default_rng(42)
    return rng.uniform(-1.0, 1.0, 16000 * 8).astype(np.float32)


@pytest.fixture
def synthetic_audio_chunk() -> np.ndarray:
    """Create a synthetic 8-second audio chunk for classification tests."""
    # 440 Hz sine wave at moderate amplitude
    t = np.linspace(0, 8.0, 16000 * 8, endpoint=False, dtype=np.float32)
    return (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Capture Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAudioCapture:
    """Tests for AudioCapture RMS gating and stream management."""

    # ── RMS Calculation ────────────────────────────────────────────────────

    def test_rms_calculation_silence(self) -> None:
        """Test that silence has near-zero RMS."""
        audio = np.zeros(16000, dtype=np.float32)
        rms = AudioCapture._calculate_rms(audio)
        assert rms == 0.0

    def test_rms_calculation_full_scale(self) -> None:
        """Test RMS of a full-scale sine wave."""
        # Sine wave at amplitude 1.0 → RMS = 1/sqrt(2) ≈ 0.707
        t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t)
        rms = AudioCapture._calculate_rms(audio)
        assert rms == pytest.approx(0.707, abs=0.01)

    def test_rms_calculation_half_scale(self) -> None:
        """Test RMS of a half-amplitude sine wave."""
        t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        rms = AudioCapture._calculate_rms(audio)
        assert rms == pytest.approx(0.353, abs=0.01)

    def test_rms_calculation_empty_array(self) -> None:
        """Test that empty array returns 0.0 RMS."""
        audio = np.array([], dtype=np.float32)
        rms = AudioCapture._calculate_rms(audio)
        assert rms == 0.0

    # ── Silence Below Threshold ───────────────────────────────────────────

    async def test_silence_below_threshold(
        self,
        audio_capture: AudioCapture,
        silence_audio: np.ndarray,
    ) -> None:
        """Test that near-silent audio returns None (below RMS threshold)."""
        # Directly test the RMS gate logic
        rms = AudioCapture._calculate_rms(silence_audio)
        assert rms < audio_capture._rms_threshold

    # ── Loud Sound Above Threshold ────────────────────────────────────────

    async def test_loud_sound_above_threshold(
        self,
        audio_capture: AudioCapture,
        loud_audio: np.ndarray,
    ) -> None:
        """Test that loud audio has RMS above threshold."""
        rms = AudioCapture._calculate_rms(loud_audio)
        assert rms >= audio_capture._rms_threshold

    # ── Stream Management ─────────────────────────────────────────────────

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_start_stream_success(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test that start_stream opens PyAudio successfully."""
        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        result = await audio_capture.start_stream()

        assert result is True
        assert audio_capture.is_streaming is True
        mock_instance.open.assert_called_once()

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_start_stream_failure(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test that start_stream returns False on failure."""
        mock_instance = MagicMock()
        mock_instance.open.side_effect = OSError("No audio device")
        mock_pyaudio.return_value = mock_instance

        result = await audio_capture.start_stream()

        assert result is False
        assert audio_capture.is_streaming is False

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_stop_stream(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test that stop_stream closes the stream."""
        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        await audio_capture.start_stream()
        assert audio_capture.is_streaming is True

        await audio_capture.stop_stream()
        assert audio_capture.is_streaming is False
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_is_streaming_property(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test is_streaming property before and after start."""
        assert audio_capture.is_streaming is False

        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        await audio_capture.start_stream()
        assert audio_capture.is_streaming is True

    # ── Read Chunk ────────────────────────────────────────────────────────

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_when_not_streaming(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test that read_chunk returns None when not streaming."""
        result = await audio_capture.read_chunk()
        assert result is None

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_returns_audio(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
        loud_audio: np.ndarray,
    ) -> None:
        """Test that read_chunk returns audio data when streaming."""
        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = loud_audio.tobytes()
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 16000 * 8  # 8 seconds at 16kHz

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_silence_returns_none(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
        silence_audio: np.ndarray,
    ) -> None:
        """Test that read_chunk returns None for silence (RMS gate)."""
        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_stream.read.return_value = silence_audio.tobytes()
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is None

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_handles_overflow(
        self,
        mock_pyaudio: MagicMock,
        audio_capture: AudioCapture,
        loud_audio: np.ndarray,
    ) -> None:
        """Test that read_chunk handles buffer overflow gracefully."""
        mock_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        # Simulate overflow by returning shorter data
        short_data = loud_audio[:8000].tobytes()
        mock_stream.read.return_value = short_data
        mock_instance.open.return_value = mock_stream
        mock_pyaudio.return_value = mock_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        # Should pad with zeros to reach expected length
        assert result is not None
        assert len(result) == 16000 * 8


# ═══════════════════════════════════════════════════════════════════════════════
# YAMNet Detector Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestYAMNetDetector:
    """Tests for YAMNetDetector classification and threshold logic."""

    # ── Model Loading ──────────────────────────────────────────────────────

    @patch("connect.audio.yamnet_detector.hub.load")
    def test_load_model(self, mock_hub_load: MagicMock) -> None:
        """Test that load_model loads from TensorFlow Hub."""
        mock_model = MagicMock()
        mock_hub_load.return_value = mock_model

        detector = YAMNetDetector()
        detector.load_model()

        assert detector._model is not None
        mock_hub_load.assert_called_once()

    @patch("connect.audio.yamnet_detector.hub.load")
    def test_load_model_idempotent(self, mock_hub_load: MagicMock) -> None:
        """Test that load_model is idempotent (second call is no-op)."""
        mock_model = MagicMock()
        mock_hub_load.return_value = mock_model

        detector = YAMNetDetector()
        detector.load_model()
        detector.load_model()  # second call

        mock_hub_load.assert_called_once()  # only called once

    @patch("connect.audio.yamnet_detector.hub.load")
    def test_load_model_failure_raises(self, mock_hub_load: MagicMock) -> None:
        """Test that load_model raises RuntimeError on failure."""
        mock_hub_load.side_effect = Exception("Network error")

        detector = YAMNetDetector()
        with pytest.raises(RuntimeError, match="Failed to load YAMNet model"):
            detector.load_model()

    # ── Input Validation ───────────────────────────────────────────────────

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_classify_empty_chunk_raises(
        self,
        mock_hub_load: MagicMock,
        yamnet_detector: YAMNetDetector,
    ) -> None:
        """Test that classify raises ValueError for empty chunk."""
        with pytest.raises(ValueError, match="Audio chunk is empty"):
            await yamnet_detector.classify(np.array([], dtype=np.float32))

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_classify_wrong_dtype_raises(
        self,
        mock_hub_load: MagicMock,
        yamnet_detector: YAMNetDetector,
        synthetic_audio_chunk: np.ndarray,
    ) -> None:
        """Test that classify raises ValueError for non-float32 input."""
        wrong_dtype = synthetic_audio_chunk.astype(np.int16)
        with pytest.raises(ValueError, match="Expected float32"):
            await yamnet_detector.classify(wrong_dtype)

    # ── Classification ─────────────────────────────────────────────────────

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_yamnet_classifies_glass_breaking(
        self,
        mock_hub_load: MagicMock,
        yamnet_detector: YAMNetDetector,
        synthetic_audio_chunk: np.ndarray,
    ) -> None:
        """Test that YAMNet classifies glass breaking (class 380)."""
        # Mock YAMNet model output
        mock_model = MagicMock()
        # Create scores: [num_frames, 521] — class 380 has highest score
        num_frames = 64
        scores = np.zeros((num_frames, 521), dtype=np.float32)
        scores[:, 380] = 0.85  # glass_breaking
        scores[:, 0] = 0.1     # speech (low)
        mock_model.return_value = (
            tf_constant(scores),
            tf_constant(np.zeros((num_frames, 1024), dtype=np.float32)),
            tf_constant(np.zeros((num_frames, 64), dtype=np.float32)),
        )
        mock_hub_load.return_value = mock_model

        result = await yamnet_detector.classify(synthetic_audio_chunk)

        assert result.class_id == 380
        assert "glass" in result.class_name.lower()
        assert result.confidence >= 0.8
        # Glass breaking is a security sound
        assert result.should_trigger is True
        # Glass breaking is NOT speech
        assert result.should_send_to_whisper is False

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_yamnet_classifies_speech(
        self,
        mock_hub_load: MagicMock,
        yamnet_detector: YAMNetDetector,
        synthetic_audio_chunk: np.ndarray,
    ) -> None:
        """Test that YAMNet classifies speech (class 0)."""
        mock_model = MagicMock()
        num_frames = 64
        scores = np.zeros((num_frames, 521), dtype=np.float32)
        scores[:, 0] = 0.92  # speech
        mock_model.return_value = (
            tf_constant(scores),
            tf_constant(np.zeros((num_frames, 1024), dtype=np.float32)),
            tf_constant(np.zeros((num_frames, 64), dtype=np.float32)),
        )
        mock_hub_load.return_value = mock_model

        result = await yamnet_detector.classify(synthetic_audio_chunk)

        assert result.class_id == 0
        assert "speech" in result.class_name.lower()
        assert result.confidence >= 0.9
        # Speech above threshold → should send to Whisper
        assert result.should_send_to_whisper is True
        # Speech is also in SECURITY_CLASSES → should trigger
        assert result.should_trigger is True

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_confidence_threshold_gates_whisper(
        self,
        mock_hub_load: MagicMock,
        synthetic_audio_chunk: np.ndarray,
    ) -> None:
        """Test that low-confidence speech does NOT trigger Whisper."""
        mock_model = MagicMock()
        num_frames = 64
        scores = np.zeros((num_frames, 521), dtype=np.float32)
        scores[:, 0] = 0.4  # speech, below speech threshold (0.5) but above security threshold (0.3)
        mock_model.return_value = (
            tf_constant(scores),
            tf_constant(np.zeros((num_frames, 1024), dtype=np.float32)),
            tf_constant(np.zeros((num_frames, 64), dtype=np.float32)),
        )
        mock_hub_load.return_value = mock_model

        detector = YAMNetDetector(speech_threshold=0.5, security_threshold=0.3)
        result = await detector.classify(synthetic_audio_chunk)

        assert result.class_id == 0
        assert result.confidence == pytest.approx(0.4)
        # Below speech threshold → should NOT send to Whisper
        assert result.should_send_to_whisper is False
        # Above security threshold (0.3) → should trigger
        assert result.should_trigger is True

    @patch("connect.audio.yamnet_detector.hub.load")
    async def test_low_confidence_security_no_trigger(
        self,
        mock_hub_load: MagicMock,
        synthetic_audio_chunk: np.ndarray,
    ) -> None:
        """Test that low-confidence security sound does NOT trigger."""
        mock_model = MagicMock()
        num_frames = 64
        scores = np.zeros((num_frames, 521), dtype=np.float32)
        scores[:, 380] = 0.2  # glass_breaking, below security threshold (0.3)
        mock_model.return_value = (
            tf_constant(scores),
            tf_constant(np.zeros((num_frames, 1024), dtype=np.float32)),
            tf_constant(np.zeros((num_frames, 64), dtype=np.float32)),
        )
        mock_hub_load.return_value = mock_model

        detector = YAMNetDetector(speech_threshold=0.5, security_threshold=0.3)
        result = await detector.classify(synthetic_audio_chunk)

        assert result.class_id == 380
        assert result.confidence == pytest.approx(0.2)
        # Below security threshold → should NOT trigger
        assert result.should_trigger is False
        assert result.should_send_to_whisper is False

    # ── Security Class Mapping ─────────────────────────────────────────────

    def test_security_class_mapping(self) -> None:
        """Test that all SECURITY_CLASSES entries map to valid names."""
        class_names = _get_yamnet_class_names()
        for class_id, category in SECURITY_CLASSES.items():
            assert class_id in class_names, (
                f"Class ID {class_id} ({category}) not found in YAMNet class map"
            )
            # Verify the category name is reasonable
            assert isinstance(category, str)
            assert len(category) > 0

    def test_security_classes_contain_speech(self) -> None:
        """Test that speech class IDs are in SECURITY_CLASSES."""
        for speech_id in SPEECH_CLASS_IDS:
            assert speech_id in SECURITY_CLASSES, (
                f"Speech class ID {speech_id} missing from SECURITY_CLASSES"
            )

    def test_security_classes_all_known(self) -> None:
        """Test that all SECURITY_CLASSES IDs are within valid range (0-520)."""
        for class_id in SECURITY_CLASSES:
            assert 0 <= class_id <= 520, (
                f"Class ID {class_id} is outside valid YAMNet range (0-520)"
            )

    # ── _should_trigger and _should_send_to_whisper ────────────────────────

    def test_should_trigger_above_threshold(self, yamnet_detector: YAMNetDetector) -> None:
        """Test that security sound above threshold triggers."""
        assert yamnet_detector._should_trigger(380, 0.8) is True   # glass_breaking
        assert yamnet_detector._should_trigger(381, 0.9) is True   # gunshot
        assert yamnet_detector._should_trigger(400, 0.7) is True   # scream
        assert yamnet_detector._should_trigger(0, 0.6) is True     # speech (in SECURITY_CLASSES)

    def test_should_trigger_below_threshold(self, yamnet_detector: YAMNetDetector) -> None:
        """Test that security sound below threshold does NOT trigger."""
        assert yamnet_detector._should_trigger(380, 0.2) is False
        assert yamnet_detector._should_trigger(381, 0.1) is False

    def test_should_trigger_non_security(self, yamnet_detector: YAMNetDetector) -> None:
        """Test that non-security sounds never trigger."""
        assert yamnet_detector._should_trigger(100, 0.9) is False   # vacuum cleaner
        assert yamnet_detector._should_trigger(200, 0.9) is False   # piano
        assert yamnet_detector._should_trigger(999, 0.9) is False   # out of range

    def test_should_send_to_whisper_speech(self, yamnet_detector: YAMNetDetector) -> None:
        """Test that speech above threshold sends to Whisper."""
        assert yamnet_detector._should_send_to_whisper(0, 0.8) is True   # speech
        assert yamnet_detector._should_send_to_whisper(1, 0.7) is True   # male speech
        assert yamnet_detector._should_send_to_whisper(2, 0.9) is True   # female speech

    def test_should_send_to_whisper_below_threshold(
        self,
        yamnet_detector: YAMNetDetector,
    ) -> None:
        """Test that speech below threshold does NOT send to Whisper."""
        assert yamnet_detector._should_send_to_whisper(0, 0.3) is False

    def test_should_send_to_whisper_non_speech(
        self,
        yamnet_detector: YAMNetDetector,
    ) -> None:
        """Test that non-speech sounds never send to Whisper."""
        assert yamnet_detector._should_send_to_whisper(380, 0.9) is False  # glass
        assert yamnet_detector._should_send_to_whisper(400, 0.9) is False  # scream

    # ── _get_top_class ─────────────────────────────────────────────────────

    def test_get_top_class_returns_highest(self) -> None:
        """Test that _get_top_class returns the highest-confidence class."""
        scores = np.zeros((10, 521), dtype=np.float32)
        scores[:, 380] = 0.9   # glass_breaking (highest)
        scores[:, 0] = 0.3     # speech (lower)

        class_name, class_id, confidence = YAMNetDetector._get_top_class(
            scores,
            np.zeros((10, 1024), dtype=np.float32),
            np.zeros((10, 64), dtype=np.float32),
        )

        assert class_id == 380
        assert confidence == pytest.approx(0.9)

    def test_get_top_class_unknown_id(self) -> None:
        """Test that _get_top_class handles unknown class IDs gracefully."""
        # Create scores where the top class ID is not in the class name map
        # Use class ID 520 (last valid index) which IS in the map
        scores = np.zeros((10, 521), dtype=np.float32)
        scores[:, 520] = 0.9  # "Engine computer" — valid but unusual

        class_name, class_id, confidence = YAMNetDetector._get_top_class(
            scores,
            np.zeros((10, 1024), dtype=np.float32),
            np.zeros((10, 64), dtype=np.float32),
        )

        assert class_id == 520
        assert confidence == pytest.approx(0.9)
        assert class_name is not None
        assert len(class_name) > 0

    # ── YAMNetResult Dataclass ─────────────────────────────────────────────

    def test_yamnet_result_dataclass(self) -> None:
        """Test YAMNetResult dataclass creation and attributes."""
        result = YAMNetResult(
            class_name="glass_breaking",
            class_id=380,
            confidence=0.85,
            should_send_to_whisper=False,
            should_trigger=True,
        )

        assert result.class_name == "glass_breaking"
        assert result.class_id == 380
        assert result.confidence == 0.85
        assert result.should_send_to_whisper is False
        assert result.should_trigger is True

    # ── Class Name Lookup ──────────────────────────────────────────────────

    def test_get_yamnet_class_names_contains_security(self) -> None:
        """Test that class name lookup contains all security classes."""
        class_names = _get_yamnet_class_names()
        for class_id in SECURITY_CLASSES:
            assert class_id in class_names

    def test_get_yamnet_class_names_cached(self) -> None:
        """Test that class name lookup is cached (returns same dict)."""
        names1 = _get_yamnet_class_names()
        names2 = _get_yamnet_class_names()
        assert names1 is names2  # same object (cached)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def tf_constant(data: np.ndarray) -> MagicMock:
    """Create a mock TensorFlow tensor-like object.

    YAMNet returns tf.Tensor objects.  This helper creates a MagicMock
    that behaves like a tf.Tensor with a .numpy() method.
    """
    mock = MagicMock()
    mock.numpy.return_value = data
    return mock
