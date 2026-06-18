"""Tests for AudioCapture (Sprint 11.7).

All tests use mocking — no real microphone required.
AudioCapture uses PyAudio for audio input.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from connect.audio.audio_capture import AudioCapture


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
def mock_pyaudio() -> MagicMock:
    """Create a mock PyAudio instance."""
    pyaudio = MagicMock()
    stream = MagicMock()
    stream.is_active.return_value = True
    pyaudio.open.return_value = stream
    return pyaudio


# ═══════════════════════════════════════════════════════════════════════════════
# AudioCapture Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAudioCapture:
    """Tests for AudioCapture initialization and streaming."""

    def test_init_defaults(self) -> None:
        """Test default parameters."""
        capture = AudioCapture()
        assert capture._device_index == 0
        assert capture._sample_rate == 16000
        assert capture._chunk_duration == 8.0
        assert capture._rms_threshold == 0.02
        assert capture._frames_per_chunk == 128000  # 16000 * 8.0

    def test_init_custom_params(self) -> None:
        """Test custom parameters."""
        capture = AudioCapture(
            device_index=2,
            sample_rate=44100,
            chunk_duration=3.0,
            rms_threshold=0.05,
        )
        assert capture._device_index == 2
        assert capture._sample_rate == 44100
        assert capture._chunk_duration == 3.0
        assert capture._rms_threshold == 0.05
        assert capture._frames_per_chunk == 132300  # 44100 * 3.0

    def test_is_streaming_returns_false_initially(self, audio_capture: AudioCapture) -> None:
        """is_streaming should return False before start_stream."""
        assert audio_capture.is_streaming is False

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_start_stream_success(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test successful stream start."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        result = await audio_capture.start_stream()

        assert result is True
        assert audio_capture.is_streaming is True
        mock_pyaudio_instance.open.assert_called_once()

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_start_stream_failure(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test stream start failure."""
        mock_pyaudio_instance = MagicMock()
        mock_pyaudio_instance.open.side_effect = Exception("Device not found")
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        result = await audio_capture.start_stream()

        assert result is False
        assert audio_capture.is_streaming is False

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_returns_none_when_not_streaming(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """read_chunk should return None when stream is not active."""
        result = await audio_capture.read_chunk()
        assert result is None

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_returns_audio_data(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """read_chunk should return audio data above RMS threshold."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True

        # Generate audio data above RMS threshold
        audio_data = (np.ones(128000, dtype=np.float32) * 0.1).tobytes()
        mock_stream.read.return_value = audio_data
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 128000

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_returns_none_below_threshold(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """read_chunk should return None when audio is below RMS threshold."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True

        # Generate near-silent audio (below RMS threshold of 0.02)
        audio_data = (np.ones(128000, dtype=np.float32) * 0.001).tobytes()
        mock_stream.read.return_value = audio_data
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is None

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_stop_stream(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """Test stream stop."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        await audio_capture.start_stream()
        assert audio_capture.is_streaming is True

        await audio_capture.stop_stream()
        assert audio_capture.is_streaming is False

    def test_calculate_rms_silence(self, audio_capture: AudioCapture) -> None:
        """_calculate_rms should return 0 for silence."""
        audio = np.zeros(1000, dtype=np.float32)
        rms = audio_capture._calculate_rms(audio)
        assert rms == 0.0

    def test_calculate_rms_non_zero(self, audio_capture: AudioCapture) -> None:
        """_calculate_rms should return positive value for non-silent audio."""
        audio = np.ones(1000, dtype=np.float32) * 0.5
        rms = audio_capture._calculate_rms(audio)
        assert rms > 0.0
        assert rms == pytest.approx(0.5, rel=0.1)

    def test_calculate_rms_empty(self, audio_capture: AudioCapture) -> None:
        """_calculate_rms should return 0 for empty array."""
        audio = np.array([], dtype=np.float32)
        rms = audio_capture._calculate_rms(audio)
        assert rms == 0.0

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_pads_short_data(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """read_chunk should pad short audio data to expected length."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True

        # Generate short audio data (half the expected length)
        short_data = (np.ones(64000, dtype=np.float32) * 0.1).tobytes()
        mock_stream.read.return_value = short_data
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is not None
        assert len(result) == 128000  # Should be padded to full length

    @patch("connect.audio.audio_capture.pyaudio.PyAudio")
    async def test_read_chunk_truncates_long_data(
        self,
        mock_pyaudio_cls: MagicMock,
        audio_capture: AudioCapture,
    ) -> None:
        """read_chunk should truncate long audio data to expected length."""
        mock_pyaudio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_stream.is_active.return_value = True

        # Generate long audio data (double the expected length)
        long_data = (np.ones(256000, dtype=np.float32) * 0.1).tobytes()
        mock_stream.read.return_value = long_data
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_cls.return_value = mock_pyaudio_instance

        await audio_capture.start_stream()
        result = await audio_capture.read_chunk()

        assert result is not None
        assert len(result) == 128000  # Should be truncated to expected length
