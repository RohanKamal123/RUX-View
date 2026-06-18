"""
onvif_discovery.py — ONVIF camera auto-discovery.

Probes the local network for ONVIF-compatible cameras,
discovers all channel RTSP URIs, and returns camera
profiles without manual URL entry.

Probe ports: 80, 8080, 8000, 8899
Default credentials tried:
  Dahua:    admin / admin123
  Hikvision: admin / 12345
  Generic:  admin / admin, admin / (empty)

Usage:
    cameras = await discover_cameras("192.168.1")
    for cam in cameras:
        print(cam.rtsp_url, cam.brand, cam.channels)
"""

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

ONVIF_PORTS = [80, 8080, 8000, 8899]
ONVIF_PATH = "/onvif/device_service"
PROBE_TIMEOUT = 3.0

DEFAULT_CREDENTIALS = [
    ("admin", "admin123"),    # Dahua default
    ("admin", "12345"),       # Hikvision default
    ("admin", "admin"),       # Generic
    ("admin", ""),            # No password
    ("888888", "888888"),     # Some Dahua DVRs
]

ONVIF_GETDEVICEINFO = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <tds:GetDeviceInformation
      xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>
  </s:Body>
</s:Envelope>"""

ONVIF_GETPROFILES = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetProfiles
      xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>
  </s:Body>
</s:Envelope>"""

ONVIF_GETSTREAMURI = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetStreamUri
      xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:StreamSetup>
        <tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema"
          >RTP-Unicast</tt:Stream>
        <tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema">
          <tt:Protocol>RTSP</tt:Protocol>
        </tt:Transport>
      </trt:StreamSetup>
      <trt:ProfileToken>{token}</trt:ProfileToken>
    </trt:GetStreamUri>
  </s:Body>
</s:Envelope>"""


@dataclass
class DiscoveredCamera:
    ip: str
    port: int
    brand: str = "Unknown"
    model: str = ""
    username: str = ""
    password: str = ""
    rtsp_url: str = ""
    channels: list[str] = field(default_factory=list)
    onvif_url: str = ""


async def discover_cameras(
    subnet: str,
    log_callback=None,
) -> list[DiscoveredCamera]:
    """Discover ONVIF cameras on a subnet.

    Args:
        subnet: Network prefix e.g. "192.168.1"
        log_callback: Optional callable(message, level) for UI logs.

    Returns:
        List of DiscoveredCamera with RTSP URLs populated.
    """
    log = log_callback or (lambda m, l: logger.info(m))
    log(f"Scanning {subnet}.0/24 for cameras...", "info")

    # Probe all IPs in parallel (batches of 20)
    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    cameras = []

    for batch_start in range(0, len(ips), 20):
        batch = ips[batch_start:batch_start + 20]
        tasks = [_probe_ip(ip, log) for ip in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, DiscoveredCamera):
                cameras.append(r)

    log(f"Discovery complete — found {len(cameras)} camera(s)", "success")
    return cameras


async def _probe_ip(
    ip: str,
    log,
) -> Optional[DiscoveredCamera]:
    """Probe a single IP for ONVIF service on known ports."""
    for port in ONVIF_PORTS:
        if await _port_open(ip, port):
            camera = await _onvif_handshake(ip, port, log)
            if camera:
                return camera
    return None


async def _port_open(ip: str, port: int) -> bool:
    """Check if a TCP port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=0.5,
        )
        writer.close()
        return True
    except Exception:
        return False


async def _onvif_handshake(
    ip: str,
    port: int,
    log,
) -> Optional[DiscoveredCamera]:
    """Try ONVIF handshake with default credentials."""
    url = f"http://{ip}:{port}{ONVIF_PATH}"

    for username, password in DEFAULT_CREDENTIALS:
        try:
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    content=ONVIF_GETDEVICEINFO,
                    headers={"Content-Type": "application/soap+xml"},
                    auth=(username, password),
                )
                if resp.status_code not in (200, 401):
                    continue
                if resp.status_code == 401:
                    continue

                brand, model = _parse_device_info(resp.text)
                log(
                    f"Found {brand} {model} at {ip}:{port} "
                    f"(user: {username})",
                    "success",
                )

                camera = DiscoveredCamera(
                    ip=ip,
                    port=port,
                    brand=brand,
                    model=model,
                    username=username,
                    password=password,
                    onvif_url=url,
                )

                # Get all channel RTSP URLs
                channels = await _get_stream_urls(
                    client, url, username, password
                )
                if channels:
                    camera.channels = channels
                    camera.rtsp_url = channels[0]

                return camera

        except Exception:
            continue

    return None


async def _get_stream_urls(
    client: httpx.AsyncClient,
    url: str,
    username: str,
    password: str,
) -> list[str]:
    """Get all channel RTSP stream URLs via ONVIF."""
    try:
        resp = await client.post(
            url,
            content=ONVIF_GETPROFILES,
            headers={"Content-Type": "application/soap+xml"},
            auth=(username, password),
        )
        tokens = _parse_profile_tokens(resp.text)
        stream_urls = []
        for token in tokens:
            stream_resp = await client.post(
                url,
                content=ONVIF_GETSTREAMURI.format(token=token),
                headers={"Content-Type": "application/soap+xml"},
                auth=(username, password),
            )
            stream_url = _parse_stream_uri(stream_resp.text)
            if stream_url:
                stream_urls.append(stream_url)
        return stream_urls
    except Exception:
        return []


def _parse_device_info(xml: str) -> tuple[str, str]:
    """Extract brand and model from ONVIF GetDeviceInformation response."""
    brand = "Unknown"
    model = ""
    if "Dahua" in xml or "dahua" in xml:
        brand = "Dahua"
    elif "Hikvision" in xml or "hikvision" in xml:
        brand = "Hikvision"
    elif "Uniview" in xml:
        brand = "Uniview"
    try:
        import re
        m = re.search(r"<.*?Model>(.*?)</.*?Model>", xml)
        if m:
            model = m.group(1)
    except Exception:
        pass
    return brand, model


def _parse_profile_tokens(xml: str) -> list[str]:
    """Extract profile tokens from ONVIF GetProfiles response."""
    import re
    tokens = re.findall(r'token="([^"]+)"', xml)
    return tokens[:8]  # Max 8 channels


def _parse_stream_uri(xml: str) -> str:
    """Extract RTSP URI from ONVIF GetStreamUri response."""
    import re
    m = re.search(r"<.*?Uri>(rtsp://[^<]+)</.*?Uri>", xml)
    return m.group(1) if m else ""