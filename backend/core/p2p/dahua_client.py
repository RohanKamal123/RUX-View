"""
dahua_client.py — EXPERIMENTAL, UNVERIFIED Dahua P2P cloud client.

Status: written from published reverse-engineering research, never run
against a real Dahua device or Dahua's live cloud service (no test
hardware or account available in this environment). Do not treat this as
working until it has been exercised against a real camera. Contrast with
backend/core/ingest/rtmp_ingest.py, which WAS verified end-to-end against
a real (synthetic) RTMP push in dev.

Why this exists: connection_type="dahua_p2p" on Camera (see
backend/storage/database.py) is the fallback for DVRs that don't support
RTMP push (backend/core/ingest/) -- this is the same auth model the DMSS
app uses (device serial number + username + password), for a customer
whose cameras/NVR already maintain an outbound connection to Dahua's own
P2P cloud (Easy4IP) rather than being reachable directly.

Source / prior art: no official Dahua P2P SDK is publicly available (it
requires a vendor developer agreement this project doesn't have). This
module is based on publicly-published, MIT-licensed reverse-engineering
work: https://github.com/khoanguyen-3fc/dh-p2p ("dh-p2p", MIT license).
That project itself states official PTCP documentation does not exist and
its protocol details come from packet analysis against KBiVMS (a Dahua
OEM client) — treat every detail below as "believed accurate per that
research," not as a documented spec.

Protocol shape (per dh-p2p's README):
  1. GET .../probe/p2psrv           -- reachability probe
  2. GET .../online/p2psrv/{SN}     -- resolve which P2P relay server a
                                        device with this serial is
                                        currently registered on
  3. GET .../info/device/{SN}       -- returns <Info> as base64(AES-256-OFB
                                        ciphertext) that decrypts to JSON
                                        containing "randsalt"; the AES key
                                        itself is not documented in the
                                        source material this was written
                                        from, so step 3 cannot be
                                        completed here (see
                                        resolve_device_salt() below)
  4. Device auth hash: MD5(f"{username}:Login to {randsalt}:{password}")
  5. PTCP tunnel: a proprietary protocol encapsulating TCP-like framing
     inside UDP for NAT traversal (24-byte header: sent/received byte
     counters, packet IDs, realm ID, followed by a variable body with
     packet type / data length / realm ID / payload). RTSP is then
     tunneled through an opened "realm". No further detail is
     reproduced here since the exact framing needs verification against
     a live device before it's safe to rely on -- see
     PTCPTunnel.open_realm() below.

What's implemented vs. stubbed:
  - probe_p2p_server() / resolve_relay_server(): plain HTTP GET calls,
    low risk, straightforward to get right -- implemented, but still
    never executed against Dahua's real cloud (no serial to test with).
  - resolve_device_salt(): NotImplementedError -- needs the AES key used
    for the <Info> payload, which isn't in the source material.
  - PTCPTunnel: NotImplementedError -- the UDP framing needs verification
    against real captured traffic before shipping; guessing byte layouts
    for a live network protocol risks producing something that looks
    like it works but silently corrupts data or never actually connects.

To finish this: either (a) get official Dahua P2P SDK access (vendor
developer agreement), or (b) get a real camera's serial + username +
password (a customer's, with their consent) and packet-capture a real
DMSS session against it to verify each step above before trusting this
code with real traffic.
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Per dh-p2p's README -- the Easy4IP cloud host DMSS/KBiVMS talk to.
EASY4IP_CLOUD_BASE = "https://openapi.easy4ip.com"


@dataclass
class RelayServerInfo:
    serial: str
    relay_host: Optional[str]
    online: bool


async def probe_p2p_server(base_url: str = EASY4IP_CLOUD_BASE) -> bool:
    """Check whether the P2P cloud service is reachable at all.

    Returns:
        True if the probe endpoint responded, False on any error.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/probe/p2psrv")
            return response.status_code < 500
    except Exception as exc:
        logger.warning("dahua_client: probe failed: %s", exc)
        return False


async def resolve_relay_server(serial: str, base_url: str = EASY4IP_CLOUD_BASE) -> RelayServerInfo:
    """Resolve which P2P relay server a device is currently registered on.

    Args:
        serial: The device's P2P serial number (same one entered in DMSS).

    Returns:
        RelayServerInfo. online=False if the device isn't currently
        reachable via the cloud (powered off, no internet, etc.) --
        this is expected/normal, not an error.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/online/p2psrv/{serial}")
            if response.status_code != 200:
                return RelayServerInfo(serial=serial, relay_host=None, online=False)
            # Response shape not fully verified -- treating any 200 as
            # "online" and logging the raw body for future verification
            # against a real device, rather than guessing a JSON schema.
            logger.info("dahua_client: relay lookup response for %s: %s", serial, response.text[:500])
            return RelayServerInfo(serial=serial, relay_host=base_url, online=True)
    except Exception as exc:
        logger.warning("dahua_client: relay lookup failed for %s: %s", serial, exc)
        return RelayServerInfo(serial=serial, relay_host=None, online=False)


def compute_login_hash(username: str, password: str, randsalt: str) -> str:
    """MD5(f"{username}:Login to {randsalt}:{password}") -- per dh-p2p's
    documented auth formula. Pure function, no network calls, safe to
    unit test without a real device."""
    payload = f"{username}:Login to {randsalt}:{password}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


async def resolve_device_salt(serial: str, base_url: str = EASY4IP_CLOUD_BASE) -> str:
    """Fetch and decrypt the device's login salt from /info/device/{SN}.

    NOT IMPLEMENTED: the <Info> payload is base64(AES-256-OFB ciphertext)
    and the AES key isn't documented in the source material this module
    was written from (see module docstring). Needs verification against
    a real device's response before guessing a key would be safe.
    """
    raise NotImplementedError(
        "resolve_device_salt: AES key for the /info/device/{SN} payload "
        "is not known -- see this module's docstring for what's needed "
        "to complete it."
    )


class PTCPTunnel:
    """NOT IMPLEMENTED: the PTCP (PhonyTCP) UDP tunnel that RTSP would run
    over. See this module's docstring -- byte-level framing needs
    verification against real captured traffic before it's safe to rely
    on for production camera credentials."""

    def __init__(self, serial: str, relay_host: str):
        self.serial = serial
        self.relay_host = relay_host

    async def open_realm(self) -> None:
        raise NotImplementedError(
            "PTCPTunnel.open_realm: PTCP framing is unverified -- see "
            "this module's docstring."
        )
