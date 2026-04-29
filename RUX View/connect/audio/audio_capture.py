"""Audio Capture — microphone/line-in chunk extraction with RMS gating.

Captures audio in configurable-length chunks from a PyAudio input device.
Uses RMS amplitude threshold to gate capture — silence is discarded.
YAMNet expects 16kHz float32 audio, so sample_rate defaults to 16000.
"""

import asyncio
import logging
from typing import Optional

import numpy as np
import pyaudio

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
FORMAT = pyaudio.paFloat32          # YAMNet expects float32
CHUNK_SIZE = 1024                   # PyAudio buffer size (frames per buffer)


class AudioCapture:
    """Capture audio chunks from microphone or camera audio line.

    Usage:
        capture = AudioCapture(device_index=0)
        await capture.start_stream()
        chunk = await capture.read_chunk()  # np.ndarray or None
        await capture.stop_stream()
    """

    def __init__(
        self,
        device_index: int = 0,
        sample_rate: int = 16000,
        chunk_duration: float = 8.0,
        rms_threshold: float = 0.02,
    ) -> None:
        """Initialize audio capture.

        Args:
            device_index: PyAudio device index to capture from.
            sample_rate: Sample rate in Hz (YAMNet expects 16kHz).
            chunk_duration: Seconds per audio chunk.
            rms_threshold: Minimum RMS amplitude to trigger capture.
                           Typical range: 0.01 (quiet) to 0.1 (loud).
        """
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._chunk_duration = chunk_duration
        self._rms_threshold = rms_threshold
        self._frames_per_chunk = int(sample_rate * chunk_duration)

        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None

    # ── Public API ───────────────────────────────────────────────────────────

    async def start_stream(self) -> bool:
        """Open PyAudio input stream.

        Initialises PyAudio and opens a non-blocking input stream
        on the configured device.

        Returns:
            True if stream opened successfully, False otherwise.
        """
        loop = asyncio.get_running_loop()

        def _open() -> bool:
            try:
                self._pyaudio = pyaudio.PyAudio()
                self._stream = self._pyaudio.open(
                    format=FORMAT,
                    channels=1,
                    rate=self._sample_rate,
                    input=True,
                    input_device_index=self._device_index,
                    frames_per_buffer=CHUNK_SIZE,
                    stream_callback=None,  # blocking read mode
                )
                logger.info(
                    "Audio stream opened: device=%d, rate=%d, chunk=%.1fs",
                    self._device_index,
                    self._sample_rate,
                    self._chunk_duration,
                )
                return True
            except Exception:
                logger.exception("Failed to open audio stream")
                self._cleanup()
                return False

        return await loop.run_in_executor(None, _open)

    async def read_chunk(self) -> Optional[np.ndarray]:
        """Read one chunk of audio data.

        Reads exactly ``frames_per_chunk`` float32 samples from the
        input stream.  If the RMS amplitude is below the configured
        threshold, returns None (silence gate).

        Returns:
            Numpy array of float32 samples (shape: [frames_per_chunk]),
            or None if the chunk is below the RMS threshold or the
            stream is not active.
        """
        if self._stream is None or not self._stream.is_active():
            logger.warning("Audio stream not active — cannot read chunk")
            return None

        loop = asyncio.get_running_loop()

        def _read() -> Optional[np.ndarray]:
            try:
                raw = self._stream.read(
                    self._frames_per_chunk,
                    exception_on_overflow=False,
                )
                audio_data = np.frombuffer(raw, dtype=np.float32).copy()

                # Trim/pad to exact expected length
                if len(audio_data) < self._frames_per_chunk:
                    pad = np.zeros(self._frames_per_chunk - len(audio_data),
                                   dtype=np.float32)
                    audio_data = np.concatenate([audio_data, pad])
                elif len(audio_data) > self._frames_per_chunk:
                    audio_data = audio_data[:self._frames_per_chunk]

                # RMS gate
                rms = self._calculate_rms(audio_data)
                if rms < self._rms_threshold:
                    logger.debug("Chunk below RMS threshold: %.4f < %.4f",
                                 rms, self._rms_threshold)
                    return None

                return audio_data

            except Exception:
                logger.exception("Error reading audio chunk")
                return None

        return await loop.run_in_executor(None, _read)

    async def stop_stream(self) -> None:
        """Close PyAudio stream and terminate PyAudio instance."""
        loop = asyncio.get_running_loop()

        def _stop() -> None:
            self._cleanup()
            logger.info("Audio stream closed")

        await loop.run_in_executor(None, _stop)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_streaming(self) -> bool:
        """Check if audio stream is active.

        Returns:
            True if the stream exists and is active.
        """
        return self._stream is not None and self._stream.is_active()

    # ── Internal: RMS Calculation ────────────────────────────────────────────

    @staticmethod
    def _calculate_rms(audio_data: np.ndarray) -> float:
        """Calculate RMS amplitude of audio chunk.

        Args:
            audio_data: Float32 numpy array of audio samples.

        Returns:
            RMS amplitude as a float.
        """
        if audio_data.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio_data ** 2)))

    # ── Internal: Cleanup ────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        """Release PyAudio resources."""
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
                self._stream.close()
            except Exception:
                logger.exception("Error closing audio stream")
            finally:
                self._stream = None

        if self._pyaudio is not None:
            try:
                self._pyaudio.terminate()
            except Exception:
                logger.exception("Error terminating PyAudio")
            finally:
                self._pyaudio = None
