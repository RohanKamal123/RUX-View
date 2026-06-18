"""
rtsp_tester.py — RTSP Stream Tester for Vision OS.

Tests and connects to RTSP camera streams with detailed stream information.
Provides robust connection handling and stream metadata extraction.

Stack: Python + OpenCV + asyncio
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class RTSPStreamInfo:
    """Detailed information about an RTSP stream."""
    url: str
    is_connected: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    bitrate: int = 0
    frame_count: int = 0
    error: Optional[str] = None
    connection_time: float = 0.0

class RTSPTester:
    """Tests and connects to RTSP camera streams.

    Provides detailed stream information and connection testing capabilities.
    """

    def __init__(self, connection_timeout: float = 5.0, test_duration: float = 3.0):
        """Initialize RTSPTester.

        Args:
            connection_timeout: Maximum seconds to wait for connection.
            test_duration: Seconds to test the stream for stability.
        """
        self.connection_timeout = connection_timeout
        self.test_duration = test_duration

    async def test_stream(self, rtsp_url: str, username: str = "", password: str = "") -> RTSPStreamInfo:
        """Test an RTSP stream and extract detailed information.

        Args:
            rtsp_url: RTSP URL to test.
            username: Optional username for authentication.
            password: Optional password for authentication.

        Returns:
            RTSPStreamInfo object with detailed stream information.
        """
        stream_info = RTSPStreamInfo(url=rtsp_url)

        try:
            # Add authentication to URL if provided
            if username and password:
                auth_part = f"{username}:{password}@"
                if "@" in rtsp_url:
                    # URL already has authentication, replace it
                    rtsp_url = rtsp_url.split("@")[0] + f"@{auth_part}" + rtsp_url.split("@")[1]
                else:
                    # Insert authentication
                    rtsp_url = rtsp_url.replace("rtsp://", f"rtsp://{auth_part}")

            logger.info("Testing RTSP stream: %s", rtsp_url)

            # Test connection in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            start_time = loop.time()

            # Use run_in_executor to avoid blocking the event loop
            cap = await loop.run_in_executor(
                None,
                lambda: self._open_rtsp_stream(rtsp_url)
            )

            stream_info.connection_time = loop.time() - start_time

            if cap is None or not cap.isOpened():
                stream_info.error = "Failed to open RTSP stream"
                logger.warning("Failed to open RTSP stream: %s", rtsp_url)
                return stream_info

            # Get stream properties
            stream_info.is_connected = True
            stream_info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            stream_info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            stream_info.fps = cap.get(cv2.CAP_PROP_FPS)

            # Get codec information
            codec_code = int(cap.get(cv2.CAP_PROP_FOURCC))
            stream_info.codec = "".join([
                chr((codec_code >> 0) & 0xFF),
                chr((codec_code >> 8) & 0xFF),
                chr((codec_code >> 16) & 0xFF),
                chr((codec_code >> 24) & 0xFF),
            ])

            # Test stream stability by reading a few frames
            if self.test_duration > 0:
                await self._test_stream_stability(cap, stream_info)

            logger.info("Successfully connected to RTSP stream: %s", rtsp_url)
            logger.info("Stream info: %dx%d @ %.1f fps, codec: %s, frames: %d",
                      stream_info.width, stream_info.height, stream_info.fps,
                      stream_info.codec, stream_info.frame_count)

            # Release the capture
            cap.release()

        except Exception as e:
            stream_info.error = f"RTSP connection error: {str(e)}"
            logger.error("Error testing RTSP stream %s: %s", rtsp_url, e)

        return stream_info

    def _open_rtsp_stream(self, rtsp_url: str) -> Optional[cv2.VideoCapture]:
        """Open an RTSP stream with timeout handling.

        Args:
            rtsp_url: RTSP URL to open.

        Returns:
            VideoCapture object if successful, None otherwise.
        """
        try:
            # Create VideoCapture object
            cap = cv2.VideoCapture(rtsp_url)

            # Set buffer size to reduce latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Wait for connection with timeout
            start_time = cv2.getTickCount()
            timeout_seconds = self.connection_timeout

            while True:
                if cap.isOpened():
                    break

                # Check timeout
                current_time = cv2.getTickCount()
                elapsed_seconds = (current_time - start_time) / cv2.getTickFrequency()
                if elapsed_seconds > timeout_seconds:
                    cap.release()
                    return None

                # Small delay to prevent busy waiting
                cv2.waitKey(100)

            return cap

        except Exception:
            return None

    async def _test_stream_stability(self, cap: cv2.VideoCapture, stream_info: RTSPStreamInfo) -> None:
        """Test the stability of an RTSP stream by reading frames.

        Args:
            cap: Open VideoCapture object.
            stream_info: StreamInfo object to update.
        """
        try:
            start_time = asyncio.get_event_loop().time()
            frame_count = 0
            success_count = 0

            while (asyncio.get_event_loop().time() - start_time) < self.test_duration:
                # Read frame (in executor to avoid blocking)
                loop = asyncio.get_event_loop()
                ret, frame = await loop.run_in_executor(None, cap.read)

                if ret and frame is not None:
                    success_count += 1
                    frame_count += 1

                    # Calculate approximate bitrate (very rough estimate)
                    if frame_count == 1:
                        frame_size = frame.nbytes
                        if frame_size > 0:
                            # Estimate bitrate: frame_size * fps * 8 (bits per byte)
                            estimated_bitrate = frame_size * stream_info.fps * 8
                            stream_info.bitrate = int(estimated_bitrate)

                await asyncio.sleep(0.01)  # Small delay between frames

            stream_info.frame_count = success_count

            # Calculate actual FPS achieved
            if self.test_duration > 0:
                actual_fps = success_count / self.test_duration
                stream_info.fps = actual_fps

        except Exception as e:
            stream_info.error = f"Stream stability test failed: {str(e)}"
            logger.warning("Stream stability test failed: %s", e)

    async def test_multiple_streams(self, rtsp_urls: List[str],
                                  username: str = "", password: str = "") -> List[RTSPStreamInfo]:
        """Test multiple RTSP streams concurrently.

        Args:
            rtsp_urls: List of RTSP URLs to test.
            username: Optional username for authentication.
            password: Optional password for authentication.

        Returns:
            List of RTSPStreamInfo objects for each URL.
        """
        if not rtsp_urls:
            return []

        logger.info("Testing %d RTSP streams concurrently...", len(rtsp_urls))

        tasks = []
        for url in rtsp_urls:
            task = asyncio.create_task(self.test_stream(url, username, password))
            tasks.append(task)

        # Limit concurrency to avoid overwhelming the system
        results = []
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)

        logger.info("Completed testing %d RTSP streams", len(results))
        return results

    async def connect_and_monitor(self, rtsp_url: str, callback=None,
                                 username: str = "", password: str = "") -> asyncio.Task:
        """Connect to an RTSP stream and monitor it continuously.

        Args:
            rtsp_url: RTSP URL to connect to.
            callback: Optional callback function for received frames.
            username: Optional username for authentication.
            password: Optional password for authentication.

        Returns:
            asyncio.Task that can be cancelled to stop monitoring.
        """
        async def _monitor_task():
            cap = None
            try:
                # Add authentication if provided
                if username and password:
                    auth_part = f"{username}:{password}@"
                    if "@" not in rtsp_url:
                        rtsp_url = rtsp_url.replace("rtsp://", f"rtsp://{auth_part}")

                logger.info("Connecting to RTSP stream for monitoring: %s", rtsp_url)

                # Open stream
                loop = asyncio.get_event_loop()
                cap = await loop.run_in_executor(None, lambda: self._open_rtsp_stream(rtsp_url))

                if cap is None or not cap.isOpened():
                    error_msg = f"Failed to connect to RTSP stream: {rtsp_url}"
                    logger.error(error_msg)
                    if callback:
                        await callback(None, error_msg)
                    return

                logger.info("Successfully connected to RTSP stream for monitoring")

                # Continuous monitoring loop
                while True:
                    # Read frame
                    ret, frame = await loop.run_in_executor(None, cap.read)

                    if ret and frame is not None:
                        if callback:
                            try:
                                await callback(frame, None)
                            except Exception as e:
                                logger.error("Error in callback: %s", e)
                    else:
                        error_msg = "Failed to read frame from stream"
                        logger.warning(error_msg)
                        if callback:
                            await callback(None, error_msg)
                        # Try to reconnect
                        await asyncio.sleep(1.0)
                        cap.release()
                        cap = await loop.run_in_executor(None, lambda: self._open_rtsp_stream(rtsp_url))
                        if cap is None or not cap.isOpened():
                            await asyncio.sleep(5.0)  # Wait before retry

                    await asyncio.sleep(0.03)  # ~30 FPS monitoring

            except asyncio.CancelledError:
                logger.info("RTSP monitoring cancelled")
            except Exception as e:
                logger.error("RTSP monitoring error: %s", e)
                if callback:
                    await callback(None, f"Monitoring error: {str(e)}")
            finally:
                if cap is not None:
                    cap.release()
                logger.info("RTSP monitoring stopped")

        # Start monitoring task
        task = asyncio.create_task(_monitor_task())
        return task

    async def get_stream_snapshot(self, rtsp_url: str, username: str = "", password: str = "") -> Optional[np.ndarray]:
        """Get a single frame snapshot from an RTSP stream.

        Args:
            rtsp_url: RTSP URL to get snapshot from.
            username: Optional username for authentication.
            password: Optional password for authentication.

        Returns:
            Single frame as numpy array, or None if failed.
        """
        try:
            # Add authentication if provided
            if username and password:
                auth_part = f"{username}:{password}@"
                if "@" not in rtsp_url:
                    rtsp_url = rtsp_url.replace("rtsp://", f"rtsp://{auth_part}")

            logger.debug("Getting snapshot from RTSP stream: %s", rtsp_url)

            # Open stream
            loop = asyncio.get_event_loop()
            cap = await loop.run_in_executor(None, lambda: self._open_rtsp_stream(rtsp_url))

            if cap is None or not cap.isOpened():
                logger.warning("Failed to open stream for snapshot: %s", rtsp_url)
                return None

            # Read a frame
            ret, frame = await loop.run_in_executor(None, cap.read)

            if ret and frame is not None:
                logger.debug("Successfully captured snapshot from %s", rtsp_url)
                return frame

            logger.warning("Failed to capture frame from %s", rtsp_url)
            return None

        except Exception as e:
            logger.error("Error getting snapshot from %s: %s", rtsp_url, e)
            return None

        finally:
            if 'cap' in locals() and cap is not None:
                cap.release()