"""
voice_note.py — Emergency voice note generator using Kokoro-82M TTS.

Generates WAV from Kokoro, then converts to OGG Opus via ffmpeg.
Lazy-loads the Kokoro pipeline on first use.
"""

import logging
import subprocess
import io

logger = logging.getLogger(__name__)


class VoiceNoteGenerator:
    """Generate emergency voice notes using Kokoro-82M TTS."""

    def __init__(self):
        """Initialize voice note generator (lazy-loaded)."""
        self._pipeline = None

    def _load_pipeline(self):
        """Load Kokoro TTS pipeline on first use.

        Uses KPipeline(lang_code='a') for American English.
        """
        if self._pipeline is not None:
            return

        try:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code='a')
            logger.info("Kokoro TTS pipeline loaded successfully")
        except ImportError:
            logger.warning(
                "kokoro package not installed. Voice notes will use fallback."
            )
            self._pipeline = None

    async def generate_voice_note(self, camera_name: str, timestamp: str,
                                    threat_summary: str) -> bytes:
        """Generate an emergency voice note.

        Text template: "{camera_name}. {timestamp}. {threat_summary}."

        Args:
            camera_name: Name of the camera.
            timestamp: Incident timestamp string.
            threat_summary: Brief threat description.

        Returns:
            OGG Opus bytes for Telegram.
        """
        text = f"{camera_name}. {timestamp}. {threat_summary}."

        # Generate WAV
        wav_bytes = self._text_to_wav(text)

        # Convert to OGG Opus
        ogg_bytes = self._wav_to_ogg(wav_bytes)

        return ogg_bytes

    def _text_to_wav(self, text: str) -> bytes:
        """Convert text to WAV audio using Kokoro.

        Args:
            text: Text to synthesize.

        Returns:
            WAV bytes.
        """
        self._load_pipeline()

        if self._pipeline is None:
            # Fallback: generate a minimal silent WAV
            return self._generate_silent_wav(duration_sec=2.0)

        try:
            # Generate audio using Kokoro pipeline
            generator = self._pipeline(text, voice='af_heart')  # American female voice
            audio_chunks = []

            for result in generator:
                if hasattr(result, 'audio') and result.audio is not None:
                    audio_chunks.append(result.audio)

            if audio_chunks:
                import numpy as np
                full_audio = np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]
                return self._numpy_to_wav(full_audio, sample_rate=24000)

            return self._generate_silent_wav(duration_sec=2.0)

        except Exception as exc:
            logger.error("Kokoro TTS failed: %s", exc, exc_info=True)
            return self._generate_silent_wav(duration_sec=2.0)

    def _numpy_to_wav(self, audio_array, sample_rate: int = 24000) -> bytes:
        """Convert numpy audio array to WAV bytes.

        Args:
            audio_array: Float32 numpy array (-1.0 to 1.0).
            sample_rate: Sample rate in Hz.

        Returns:
            WAV bytes.
        """
        import numpy as np
        import struct

        # Convert to int16
        audio_int16 = (audio_array * 32767).astype(np.int16)

        # Build WAV header
        num_samples = len(audio_int16)
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample
        header = b"RIFF"
        header += struct.pack("<I", 36 + data_size)
        header += b"WAVE"
        header += b"fmt "
        header += struct.pack("<I", 16)  # chunk size
        header += struct.pack("<H", 1)  # PCM
        header += struct.pack("<H", 1)  # mono
        header += struct.pack("<I", sample_rate)
        header += struct.pack("<I", sample_rate * 2)  # byte rate
        header += struct.pack("<H", 2)  # block align
        header += struct.pack("<H", 16)  # bits per sample
        header += b"data"
        header += struct.pack("<I", data_size)

        return header + audio_int16.tobytes()

    def _generate_silent_wav(self, duration_sec: float = 2.0,
                              sample_rate: int = 24000) -> bytes:
        """Generate a silent WAV file as fallback.

        Args:
            duration_sec: Duration in seconds.
            sample_rate: Sample rate in Hz.

        Returns:
            WAV bytes.
        """
        import numpy as np
        import struct

        num_samples = int(sample_rate * duration_sec)
        audio_int16 = np.zeros(num_samples, dtype=np.int16)

        data_size = num_samples * 2
        header = b"RIFF"
        header += struct.pack("<I", 36 + data_size)
        header += b"WAVE"
        header += b"fmt "
        header += struct.pack("<I", 16)
        header += struct.pack("<H", 1)
        header += struct.pack("<H", 1)
        header += struct.pack("<I", sample_rate)
        header += struct.pack("<I", sample_rate * 2)
        header += struct.pack("<H", 2)
        header += struct.pack("<H", 16)
        header += b"data"
        header += struct.pack("<I", data_size)

        return header + audio_int16.tobytes()

    def _wav_to_ogg(self, wav_bytes: bytes) -> bytes:
        """Convert WAV to OGG Opus using ffmpeg.

        Args:
            wav_bytes: WAV audio bytes.

        Returns:
            OGG Opus bytes.
        """
        try:
            process = subprocess.run(
                [
                    "ffmpeg",
                    "-i", "pipe:0",
                    "-f", "ogg",
                    "-c:a", "libopus",
                    "-b:a", "24k",
                    "-y",
                    "pipe:1",
                ],
                input=wav_bytes,
                capture_output=True,
                timeout=30,
            )
            if process.returncode == 0 and len(process.stdout) > 0:
                return process.stdout

            logger.warning(
                "ffmpeg conversion failed (rc=%d, stderr=%s)",
                process.returncode,
                process.stderr[:200],
            )
            return wav_bytes  # Fallback to WAV
        except FileNotFoundError:
            logger.warning("ffmpeg not found. Returning WAV instead of OGG.")
            return wav_bytes
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timed out. Returning WAV instead of OGG.")
            return wav_bytes
        except Exception as exc:
            logger.error("ffmpeg conversion error: %s", exc, exc_info=True)
            return wav_bytes
