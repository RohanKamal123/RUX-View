"""
rtsp_discovery.py — RTSP Camera Discovery for Vision OS.

Discovers RTSP camera streams on the local network by scanning for open RTSP ports.
Provides async network scanning and RTSP connection testing capabilities.

Stack: Python + asyncio + socket
"""

import asyncio
import logging
import socket
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DiscoveredCamera:
    """Information about a discovered RTSP camera."""
    ip_address: str
    port: int
    rtsp_url: str
    is_accessible: bool = False
    stream_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class RTSPDiscovery:
    """Discovers RTSP cameras on the local network.

    Scans for devices with open RTSP ports and tests RTSP connections.
    Uses asyncio for efficient parallel scanning.
    """

    def __init__(self, timeout: float = 2.0, max_workers: int = 100):
        """Initialize RTSPDiscovery.

        Args:
            timeout: Seconds to wait for each connection attempt.
            max_workers: Maximum concurrent connection attempts.
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self._common_ports = [554, 8554, 1935]  # Common RTSP ports

    async def scan_network(self, subnet: str = "192.168.1.0/24") -> List[DiscoveredCamera]:
        """Scan the local network for RTSP cameras.

        Args:
            subnet: Network subnet to scan (e.g., "192.168.1.0/24").

        Returns:
            List of discovered cameras with open RTSP ports.
        """
        logger.info("Starting RTSP discovery on subnet: %s", subnet)

        ip_range = self._parse_subnet(subnet)
        if not ip_range:
            logger.error("Invalid subnet format: %s", subnet)
            return []

        all_tasks = []
        discovered_cameras = []

        # Create tasks for scanning each IP and port combination
        for ip in ip_range:
            for port in self._common_ports:
                task = asyncio.create_task(self._check_rtsp_port(ip, port))
                all_tasks.append(task)

                # Limit concurrent tasks
                if len(all_tasks) >= self.max_workers:
                    await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
                    all_tasks = [t for t in all_tasks if not t.done()]

        # Wait for remaining tasks
        if all_tasks:
            await asyncio.gather(*all_tasks)

        # Collect results
        for task in all_tasks:
            result = task.result()
            if result:
                discovered_cameras.append(result)

        logger.info("Discovery completed. Found %d potential RTSP cameras.", len(discovered_cameras))
        return discovered_cameras

    async def _check_rtsp_port(self, ip: str, port: int) -> Optional[DiscoveredCamera]:
        """Check if a specific IP:port has an open RTSP service.

        Args:
            ip: IP address to check.
            port: Port to check.

        Returns:
            DiscoveredCamera object if port is open, None otherwise.
        """
        try:
            # Use a simple TCP connection test first
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.timeout
            )

            # Close the connection
            writer.close()
            await writer.wait_closed()

            # Create basic RTSP URL
            rtsp_url = f"rtsp://{ip}:{port}"

            logger.debug("Found open RTSP port at %s:%d", ip, port)

            return DiscoveredCamera(
                ip_address=ip,
                port=port,
                rtsp_url=rtsp_url,
                is_accessible=False  # We'll test accessibility separately
            )

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            # Port is not open or not responding
            return None
        except Exception as e:
            logger.debug("Error checking %s:%d: %s", ip, port, e)
            return None

    def _parse_subnet(self, subnet: str) -> List[str]:
        """Parse subnet notation and generate list of IP addresses.

        Args:
            subnet: Subnet in CIDR notation (e.g., "192.168.1.0/24").

        Returns:
            List of IP addresses in the subnet.
        """
        try:
            if "/" not in subnet:
                # Single IP address
                return [subnet]

            network_part, prefix_len_str = subnet.split("/")
            prefix_len = int(prefix_len_str)

            # Simple implementation for /24 networks (common for local networks)
            if prefix_len == 24:
                base_ip = network_part.rstrip(".0")
                if not base_ip.endswith("."):
                    base_ip += "."

                ip_list = []
                for i in range(1, 255):  # Skip .0 and .255 (network and broadcast)
                    ip_list.append(f"{base_ip}{i}")
                return ip_list

            logger.warning("Only /24 subnets are supported. Using default 192.168.1.0/24")
            return [f"192.168.1.{i}" for i in range(1, 255)]

        except (ValueError, IndexError) as e:
            logger.error("Invalid subnet format: %s", e)
            return []

    async def test_rtsp_connections(self, cameras: List[DiscoveredCamera]) -> List[DiscoveredCamera]:
        """Test RTSP connections for a list of discovered cameras.

        Args:
            cameras: List of discovered cameras to test.

        Returns:
            List of cameras with updated accessibility status.
        """
        if not cameras:
            return []

        logger.info("Testing RTSP connections for %d cameras...", len(cameras))

        # Test connections in parallel with limited concurrency
        tasks = []
        for camera in cameras:
            task = asyncio.create_task(self._test_single_rtsp(camera))
            tasks.append(task)

            if len(tasks) >= self.max_workers:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = [t for t in tasks if not t.done()]

        if tasks:
            await asyncio.gather(*tasks)

        # Get results
        tested_cameras = []
        for task in tasks:
            result = task.result()
            if result:
                tested_cameras.append(result)

        logger.info("Connection testing completed. %d cameras are accessible.",
                   sum(1 for cam in tested_cameras if cam.is_accessible))

        return tested_cameras

    async def _test_single_rtsp(self, camera: DiscoveredCamera) -> DiscoveredCamera:
        """Test RTSP connection for a single camera.

        Args:
            camera: Camera to test.

        Returns:
            Updated camera object with accessibility status.
        """
        try:
            # Import OpenCV only when needed (it's a heavy dependency)
            import cv2

            # Try to open the RTSP stream with a short timeout
            cap = cv2.VideoCapture(camera.rtsp_url)

            # Set timeout (OpenCV doesn't have direct timeout, so we use a workaround)
            start_time = asyncio.get_event_loop().time()

            # Wait briefly for connection
            while (asyncio.get_event_loop().time() - start_time) < self.timeout:
                if cap.isOpened():
                    break
                await asyncio.sleep(0.1)

            if cap.isOpened():
                # Get stream information
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                codec_code = int(cap.get(cv2.CAP_PROP_FOURCC))
                codec = "".join([
                    chr((codec_code >> 0) & 0xFF),
                    chr((codec_code >> 8) & 0xFF),
                    chr((codec_code >> 16) & 0xFF),
                    chr((codec_code >> 24) & 0xFF),
                ])

                camera.is_accessible = True
                camera.stream_info = {
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "codec": codec,
                    "status": "connected"
                }

                logger.info("Successfully connected to RTSP stream: %s", camera.rtsp_url)
                logger.info("Stream info: %dx%d @ %.1f fps, codec: %s",
                          width, height, fps, codec)

                # Release the capture
                cap.release()
            else:
                camera.error = "Connection failed - stream not accessible"
                logger.debug("Failed to connect to RTSP stream: %s", camera.rtsp_url)

        except Exception as e:
            camera.error = f"Connection error: {str(e)}"
            logger.debug("Error testing RTSP connection to %s: %s", camera.rtsp_url, e)

        return camera

    async def discover_and_test(self, subnet: str = "192.168.1.0/24") -> List[DiscoveredCamera]:
        """Convenience method to discover and test cameras in one call.

        Args:
            subnet: Network subnet to scan.

        Returns:
            List of discovered and tested cameras.
        """
        discovered = await self.scan_network(subnet)
        if discovered:
            return await self.test_rtsp_connections(discovered)
        return []