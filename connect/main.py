"""Vision OS Connect — Main Application Orchestrator.

Coordinates all client modules:
- Camera: RTSP reader, frame selector, motion detector
- Audio: Audio capture, YAMNet sound classification
- Transport: WebSocket client, HTTPS trigger sender
- Buffer: SQLite-backed offline queue

Trigger-only architecture (D005) — no continuous streaming.
All connections are outbound only (solves NAT — D009).
"""

import asyncio
import base64
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from connect.config import AppConfig, load_config
from connect.config_sync import ClientConfigSync
from connect.camera.rtsp_reader import RTSPReader
from connect.camera.frame_selector import select_best_frame
from connect.camera.motion_detector import MotionDetector, MotionResult
from connect.audio.audio_capture import AudioCapture
from connect.transport.trigger_sender import TriggerSender
from connect.transport.websocket_client import WebSocketClient, WSConfig
from connect.buffer.local_queue import LocalQueue

if TYPE_CHECKING:
    from connect.audio.yamnet_detector import YAMNetDetector, YAMNetResult

# ── Lazy YAMNet import (graceful fallback if TensorFlow not available) ──
YAMNetDetector = None
YAMNetResult = None
_yamnet_import_error = None
try:
    from connect.audio.yamnet_detector import YAMNetDetector, YAMNetResult  # type: ignore
except ImportError as e:
    _yamnet_import_error = str(e)
    # Silently disable audio — no warning noise on startup
    logging.getLogger(__name__).debug(
        "YAMNet/TensorFlow not available: %s — audio classification disabled",
        _yamnet_import_error,
    )


logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MAIN_LOOP_INTERVAL = 0.1  # seconds between frame reads
MOTION_COOLDOWN = 30.0    # seconds to wait after a trigger before next check


class VisionOSConnect:
    """Main application class orchestrating all client modules.

    Usage:
        config = load_config()
        app = VisionOSConnect(config)
        await app.start()
        # ... runs until app.stop() is called ...
        await app.stop()
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialise all modules from the provided configuration.

        Args:
            config: AppConfig with camera, audio, transport, and buffer settings.
        """
        self._config = config
        self._running = False
        self._error: Optional[str] = None
        self._last_trigger_time = 0.0

        # ── Camera Modules ────────────────────────────────────────────────
        self._rtsp_reader = RTSPReader(
            rtsp_url=config.rtsp_url,
            camera_id=config.camera_id,
        )
        self._motion_detector = MotionDetector(
            threshold=config.motion_threshold,
            min_area=config.motion_min_area,
        )

        # ── Audio Modules ─────────────────────────────────────────────────
        self._audio_capture: Optional[AudioCapture] = None
        self._yamnet_detector: Optional[YAMNetDetector] = None
        if config.audio_enabled:
            self._audio_capture = AudioCapture()
            if YAMNetDetector is not None:
                self._yamnet_detector = YAMNetDetector()

        # ── Transport Modules ─────────────────────────────────────────────
        self._trigger_sender = TriggerSender(
            api_base_url=config.backend_url,
            auth_token=config.api_key,
        )
        # Convert http/https to ws/wss for WebSocket URL
        ws_base = config.backend_url.rstrip("/")
        if ws_base.startswith("https://"):
            ws_base = ws_base.replace("https://", "wss://")
        elif ws_base.startswith("http://"):
            ws_base = ws_base.replace("http://", "ws://")
        else:
            ws_base = f"ws://{ws_base}"
        self._ws_client = WebSocketClient(
            config=WSConfig(server_url=f"{ws_base}/ws"),
            camera_id=config.camera_id,
            user_token=config.api_key,
        )

        # ── Buffer ────────────────────────────────────────────────────────
        self._local_queue = LocalQueue()

        # ── Config Sync ──────────────────────────────────────────────────
        # Keeps motion_* / rtsp_* tunables in sync with the backend's
        # config_store (dashboard Tuning page) — see connect/config_sync.py.
        self._config_sync = ClientConfigSync(
            backend_url=config.backend_url,
            auth_token=config.api_key,
            motion_detector=self._motion_detector,
            rtsp_reader=self._rtsp_reader,
        )

        # ── Internal State ────────────────────────────────────────────────
        self._main_loop_task: Optional[asyncio.Task] = None
        self._ws_receive_task: Optional[asyncio.Task] = None
        self._config_sync_task: Optional[asyncio.Task] = None

        logger.info(
            "VisionOSConnect initialised (camera=%s, mode=%s, audio=%s)",
            config.camera_id,
            config.mode,
            "enabled" if config.audio_enabled else "disabled",
        )

    # ── Public API ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start all modules and begin processing.

        Pipeline:
        1. Connect to RTSP camera
        2. Start audio capture (if enabled)
        3. Connect WebSocket to backend
        4. Start the main processing loop
        5. If offline, queued events will be flushed when reconnected
        """
        if self._running:
            logger.warning("VisionOSConnect is already running")
            return

        self._running = True
        self._error = None

        try:
            # 1. Connect to RTSP camera (with 10s timeout)
            camera_ok = await self._rtsp_reader.connect(timeout=10.0)
            if not camera_ok:
                logger.warning("Camera connection failed — will retry in main loop")

            # 2. Start audio capture (if enabled)
            if self._audio_capture is not None:
                audio_ok = await self._audio_capture.start_stream()
                if not audio_ok:
                    logger.warning("Audio capture failed to start — continuing without audio")

            # 3. Connect WebSocket
            ws_ok = await self._ws_client.connect()
            if ws_ok:
                # Start receiving messages from backend
                self._ws_receive_task = asyncio.create_task(
                    self._ws_client.receive_messages(self._on_ws_message)
                )
            else:
                logger.warning("WebSocket connection failed — will retry")

            # 4. Start main processing loop
            self._main_loop_task = asyncio.create_task(self._main_loop())

            # 5. Attempt to flush any queued events from a previous session
            asyncio.create_task(self._flush_queued_events())

            # 6. Start background config sync (motion_*/rtsp_* tunables)
            self._config_sync_task = asyncio.create_task(self._config_sync.run_forever())

            logger.info("VisionOSConnect started successfully")

        except asyncio.CancelledError:
            logger.warning("Startup cancelled — cleaning up")
            self._running = False
            self._error = "startup_cancelled"
            # Re-raise so the caller (main()) can log the real error
            raise

        except Exception:
            self._running = False
            self._error = "startup_failed"
            logger.exception("Failed to start VisionOSConnect")
            raise

    async def stop(self) -> None:
        """Gracefully stop all modules and clean up resources.

        Stops in reverse order: main loop -> WebSocket -> audio -> camera -> buffer.
        """
        self._running = False
        logger.info("Stopping VisionOSConnect ...")

        # Cancel main loop
        if self._main_loop_task is not None:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
            self._main_loop_task = None

        # Cancel WebSocket receive task
        if self._ws_receive_task is not None:
            self._ws_receive_task.cancel()
            try:
                await self._ws_receive_task
            except asyncio.CancelledError:
                pass
            self._ws_receive_task = None

        # Cancel config sync task
        if self._config_sync_task is not None:
            self._config_sync_task.cancel()
            try:
                await self._config_sync_task
            except asyncio.CancelledError:
                pass
            self._config_sync_task = None
        await self._config_sync.close()

        # Disconnect WebSocket
        await self._ws_client.disconnect()

        # Stop audio capture
        if self._audio_capture is not None:
            await self._audio_capture.stop_stream()

        # Release camera
        await self._rtsp_reader.release()

        # Close buffer
        self._local_queue.close()

        # Close HTTP client
        await self._trigger_sender.close()

        logger.info("VisionOSConnect stopped")

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        """Return the current application status.

        Returns:
            One of ``"running"``, ``"stopped"``, or ``"error"``.
        """
        if self._error is not None:
            return "error"
        if self._running:
            return "running"
        return "stopped"

    @property
    def config(self) -> AppConfig:
        """Get the current application configuration."""
        return self._config

    # ── Internal: Main Processing Loop ───────────────────────────────────────

    async def _main_loop(self) -> None:
        """Main processing loop — runs until ``stop()`` is called.

        Each iteration:
        1. Read a frame from the RTSP stream
        2. Run motion detection on the frame
        3. If motion detected and cooldown elapsed: process the trigger
        4. Yield control briefly to allow other tasks to run
        """
        logger.info("Main processing loop started")

        try:
            while self._running:
                # 1. Read frame
                try:
                    frame = await self._rtsp_reader.read_frame()
                except ConnectionError:
                    logger.warning("Camera disconnected — attempting reconnect...")
                    reconnected = await self._rtsp_reader.reconnect()
                    if reconnected:
                        logger.info("Camera reconnected successfully")
                    else:
                        logger.warning("Camera reconnection failed — will retry")
                    await asyncio.sleep(2.0)
                    continue

                if frame is None:
                    # Camera may be disconnected — attempt reconnect
                    logger.debug("No frame received — camera may be disconnected")
                    await asyncio.sleep(1.0)
                    continue

                # 2. Run motion detection (off the event loop to avoid blocking)
                loop = asyncio.get_event_loop()
                motion_result: MotionResult = await loop.run_in_executor(
                    None, self._motion_detector.detect, frame
                )

                # 3. On motion trigger (with cooldown)
                now = asyncio.get_event_loop().time()
                if motion_result.motion_detected and (now - self._last_trigger_time) >= MOTION_COOLDOWN:
                    self._last_trigger_time = now
                    await self._process_trigger(motion_result, frame)

                # 4. Yield control
                await asyncio.sleep(MAIN_LOOP_INTERVAL)

        except asyncio.CancelledError:
            logger.debug("Main processing loop cancelled")
        except Exception:
            self._error = "main_loop_error"
            logger.exception("Main processing loop encountered an error")

    async def _process_trigger(
        self,
        motion_result: MotionResult,
        frame,
    ) -> None:
        """Handle a motion trigger event.

        Pipeline:
        1. Encode the frame as base64 JPEG
        2. Classify audio if audio capture is enabled
        3. Send the trigger to the backend (or queue if offline)

        Args:
            motion_result: MotionResult from the motion detector.
            frame: BGR numpy array from RTSPReader.
        """
        timestamp = datetime.now(timezone.utc).timestamp()

        # 1. Encode frame as JPEG then base64
        import cv2
        _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(jpeg_buffer.tobytes()).decode("ascii")

        # 2. Classify audio if enabled
        audio_result: Optional[YAMNetResult] = None
        if self._audio_capture is not None and self._yamnet_detector is not None:
            audio_chunk = await self._audio_capture.read_chunk()
            if audio_chunk is not None:
                try:
                    audio_result = await self._yamnet_detector.classify(audio_chunk)
                except Exception:
                    logger.exception("Audio classification failed during trigger")

        # 3. Send to backend (or queue if offline)
        try:
            response = await self._trigger_sender.send_frame_trigger(
                camera_id=self._config.camera_id,
                image_base64=image_base64,
                timestamp=timestamp,
            )

            if not response.success:
                # Backend unreachable — queue locally (log once, not every trigger)
                logger.warning("Backend unreachable — queuing trigger locally")
                self._local_queue.enqueue({
                    "type": "frame",
                    "camera_id": self._config.camera_id,
                    "image_base64": image_base64,
                    "timestamp": timestamp,
                    "motion_confidence": motion_result.confidence,
                    "motion_area_pct": motion_result.motion_area_pct,
                })

        except Exception:
            # Log once per batch — avoid flooding console
            logger.debug("Failed to send trigger — queuing locally")
            self._local_queue.enqueue({
                "type": "frame",
                "camera_id": self._config.camera_id,
                "image_base64": image_base64,
                "timestamp": timestamp,
                "motion_confidence": motion_result.confidence,
                "motion_area_pct": motion_result.motion_area_pct,
            })

    async def _flush_queued_events(self) -> None:
        """Flush any events queued from a previous session.

        Runs in the background after startup.  If the backend is
        still unreachable, events remain in the queue for the next
        flush attempt.
        """
        try:
            queued = self._local_queue.count()
            if queued > 0:
                logger.info("Flushing %d queued events from previous session ...", queued)
                sent = await self._local_queue.flush_to_server(self._trigger_sender)
                logger.info("Flushed %d/%d queued events", sent, queued)
        except Exception:
            logger.exception("Failed to flush queued events")

    # ── Internal: WebSocket Message Handler ──────────────────────────────────

    async def _on_ws_message(self, message: dict) -> None:
        """Handle an incoming WebSocket message from the backend.

        Currently handles:
        - ``ping``: Respond with ``pong``.
        - ``flush_queue``: Force-flush the local queue.
        - ``reload_config``: Reload configuration from disk.

        Args:
            message: Parsed JSON dict from the WebSocket.
        """
        msg_type = message.get("type", "")

        if msg_type == "ping":
            await self._ws_client.send_message({"type": "pong"})

        elif msg_type == "flush_queue":
            logger.info("Received flush_queue command from backend")
            await self._local_queue.flush_to_server(self._trigger_sender)

        elif msg_type == "reload_config":
            logger.info("Received reload_config command from backend")
            new_config = load_config()
            if new_config is not None:
                self._config = new_config
                logger.info("Configuration reloaded")

        else:
            logger.debug("Unhandled WebSocket message type: %s", msg_type)


# ── Entry Point ─────────────────────────────────────────────────────────────────

async def main() -> None:
    """Entry point for the Vision OS Connect client agent.

    Loads configuration, creates the orchestrator, and runs until
    interrupted.  This function is intended to be called from a
    ``asyncio.run(main())`` pattern or from the tray app.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        config = load_config()
        app = VisionOSConnect(config)

        try:
            await app.start()
            logger.info("VisionOS Connect is running. Press Ctrl+C to stop.")

            # Keep running until interrupted
            while app.status == "running":
                await asyncio.sleep(1)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Received shutdown signal")
        finally:
            await app.stop()
            logger.info("VisionOS Connect shutdown complete")

    except asyncio.CancelledError:
        logger.debug(
            "Main task was cancelled — possible startup failure. "
            "Check crash.log for details."
        )
        raise
    except Exception:
        logger.critical(
            "Unhandled exception in main(): %s",
            traceback.format_exc(),
        )
        raise



if __name__ == "__main__":
    # ── Crash-log wrapper ──────────────────────────────────────────────
    # Writes any unhandled exception to %APPDATA%\VisionOS\crash.log
    # and pauses the terminal so the user can read the error.
    # ────────────────────────────────────────────────────────────────────
    crash_log_dir = os.path.join(os.environ.get("APPDATA", "."), "VisionOS")
    crash_log_path = os.path.join(crash_log_dir, "crash.log")
    os.makedirs(crash_log_dir, exist_ok=True)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, Exception):
        with open(crash_log_path, "w", encoding="utf-8") as f:
            f.write(f"VisionOS Connect — CRASH REPORT\n")
            f.write(f"Time: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"{'='*60}\n")
            traceback.print_exc(file=f)
        # Also print to stderr so terminal shows it
        print(f"\n❌ VisionOS Connect crashed! See: {crash_log_path}", file=sys.stderr)
        traceback.print_exc()
        print(f"\nPress Enter to exit...", file=sys.stderr)
        try:
            input()
        except EOFError:
            pass
        sys.exit(1)
