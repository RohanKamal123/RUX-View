"""Vision OS Connect — Main Application Orchestrator.

Coordinates all client modules:
- Camera: RTSP reader, frame selector, motion detector
- Audio: Audio capture, YAMNet sound classification
- Transport: WebSocket client, HTTPS trigger sender, SMS fallback
- Buffer: SQLite-backed offline queue

Trigger-only architecture (D005) — no continuous streaming.
All connections are outbound only (solves NAT — D009).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from connect.config import AppConfig, load_config, save_config
from connect.camera.rtsp_reader import RTSPReader
from connect.camera.frame_selector import select_best_frame
from connect.camera.motion_detector import MotionDetector, MotionResult
from connect.audio.audio_capture import AudioCapture
from connect.audio.yamnet_detector import YAMNetDetector, YAMNetResult
from connect.transport.trigger_sender import TriggerSender
from connect.transport.websocket_client import WebSocketClient, WSConfig
from connect.buffer.local_queue import LocalQueue

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_BURST_FRAMES = 8
MAIN_LOOP_INTERVAL = 0.1  # seconds between frame reads


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

        # ── Camera Modules ────────────────────────────────────────────────
        self._rtsp_reader = RTSPReader(
            rtsp_url=config.rtsp_url,
            camera_id=config.camera_id,
        )
        self._motion_detector = MotionDetector(
            mode=config.mode,
            ignore_zones=config.ignore_zones,
        )

        # ── Audio Modules ─────────────────────────────────────────────────
        self._audio_capture: Optional[AudioCapture] = None
        self._yamnet_detector: Optional[YAMNetDetector] = None
        if config.audio_enabled:
            self._audio_capture = AudioCapture()
            self._yamnet_detector = YAMNetDetector()

        # ── Transport Modules ─────────────────────────────────────────────
        self._trigger_sender = TriggerSender(
            backend_url=config.backend_url,
            user_token=config.api_key,
        )
        self._ws_client = WebSocketClient(
            config=WSConfig(server_url=f"{config.backend_url.rstrip('/')}/ws"),
            camera_id=config.camera_id,
            user_token=config.api_key,
        )

        # ── Buffer ────────────────────────────────────────────────────────
        self._local_queue = LocalQueue()

        # ── Internal State ────────────────────────────────────────────────
        self._main_loop_task: Optional[asyncio.Task] = None
        self._ws_receive_task: Optional[asyncio.Task] = None

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
            # 1. Connect to RTSP camera
            camera_ok = await self._rtsp_reader.connect()
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

            logger.info("VisionOSConnect started successfully")

        except Exception:
            self._running = False
            self._error = "startup_failed"
            logger.exception("Failed to start VisionOSConnect")
            raise

    async def stop(self) -> None:
        """Gracefully stop all modules and clean up resources.

        Stops in reverse order: main loop → WebSocket → audio → camera → buffer.
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

        # Disconnect WebSocket
        await self._ws_client.disconnect()

        # Stop audio capture
        if self._audio_capture is not None:
            await self._audio_capture.stop_stream()

        # Disconnect camera
        await self._rtsp_reader.disconnect()

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
        3. If motion triggers: process the trigger
        4. Yield control briefly to allow other tasks to run
        """
        logger.info("Main processing loop started")

        try:
            while self._running:
                # 1. Read frame
                frame_jpeg = await self._rtsp_reader.read_frame()
                if frame_jpeg is None:
                    # Camera may be disconnected — attempt reconnect
                    logger.debug("No frame received — camera may be disconnected")
                    await asyncio.sleep(1.0)
                    continue

                # 2. Run motion detection
                motion_result = await self._motion_detector.process(frame_jpeg)

                # 3. On trigger: process
                if motion_result.should_trigger:
                    await self._process_trigger(motion_result, frame_jpeg)

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
        frame_jpeg: bytes,
    ) -> None:
        """Handle a motion trigger event.

        Pipeline:
        1. Read a burst of frames from the camera
        2. Select the best frame (person-shaped contours preferred)
        3. Classify audio if audio capture is enabled
        4. Send the trigger to the backend (or queue if offline)

        Args:
            motion_result: MotionResult from the motion detector.
            frame_jpeg: The JPEG frame that triggered the motion event.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Read burst of frames
        burst_frames = await self._rtsp_reader.read_burst(DEFAULT_BURST_FRAMES)
        if burst_frames:
            # Include the trigger frame at the front
            all_frames = [frame_jpeg] + burst_frames
        else:
            all_frames = [frame_jpeg]

        # 2. Select best frame
        best_frame = select_best_frame(all_frames)

        # 3. Classify audio if enabled
        audio_result: Optional[YAMNetResult] = None
        if self._audio_capture is not None and self._yamnet_detector is not None:
            audio_chunk = await self._audio_capture.read_chunk()
            if audio_chunk is not None:
                try:
                    audio_result = await self._yamnet_detector.classify(audio_chunk)
                except Exception:
                    logger.exception("Audio classification failed during trigger")

        # 4. Build trigger payload
        trigger_data = {
            "type": "frame",
            "jpeg_bytes": best_frame,
            "motion_result": {
                "pixel_diff": motion_result.pixel_diff,
                "largest_contour_area": motion_result.largest_contour_area,
                "diff_category": motion_result.diff_category,
                "contour_count": motion_result.contour_count,
            },
            "camera_id": self._config.camera_id,
            "timestamp": timestamp,
        }

        # Include audio result if available
        if audio_result is not None:
            trigger_data["audio_result"] = {
                "class_name": audio_result.class_name,
                "class_id": audio_result.class_id,
                "confidence": audio_result.confidence,
                "should_trigger": audio_result.should_trigger,
            }

        # 5. Send to backend (or queue if offline)
        try:
            result = await self._trigger_sender.send_frame_trigger(
                jpeg_bytes=best_frame,
                motion_result=trigger_data["motion_result"],
                camera_id=self._config.camera_id,
                timestamp=timestamp,
            )

            if result.get("status") == "error":
                # Backend unreachable — queue locally
                logger.warning("Backend unreachable — queuing trigger locally")
                self._local_queue.enqueue(trigger_data)

        except Exception:
            logger.exception("Failed to send trigger — queuing locally")
            self._local_queue.enqueue(trigger_data)

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

    config = load_config()
    app = VisionOSConnect(config)

    try:
        await app.start()
        logger.info("VisionOS Connect is running. Press Ctrl+C to stop.")

        # Keep running until interrupted
        while app.status == "running":
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await app.stop()
        logger.info("VisionOS Connect shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
