"""SMS Sender — SSL Wireless SMS fallback for HIGH alerts during outage.

Sends SMS messages via the SSL Wireless API as a fallback channel
when the internet is down and a HIGH threat alert needs to be delivered.
Cost: ~0.30 BDT per SMS.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SSL_WIRELESS_API_URL = "https://sms.sslwireless.com/pushapi/dynamic/server.php"
DEFAULT_TIMEOUT = 15.0  # seconds


class SMSSender:
    """SSL Wireless SMS fallback for HIGH alerts during internet outage.

    Usage:
        sms = SMSSender(
            api_key="your_api_key",
            api_secret="your_api_secret",
            sender_id="VisionOS",
        )
        success = await sms.send_sms(
            phone="+8801712345678",
            message="VisionOS HIGH ALERT - Motion detected at Main Gate",
        )
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        sender_id: str,
    ) -> None:
        """Initialize SSL Wireless SMS client.

        Args:
            api_key: SSL Wireless API key.
            api_secret: SSL Wireless API secret.
            sender_id: Approved SMS sender ID (e.g. "VisionOS").
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._sender_id = sender_id
        self._client: Optional[httpx.AsyncClient] = None

    # ── Public API ───────────────────────────────────────────────────────────

    async def send_sms(self, phone: str, message: str) -> bool:
        """Send an SMS via the SSL Wireless API.

        Args:
            phone: Recipient phone number (e.g. ``+8801712345678``).
            message: SMS text content (max 160 characters recommended).

        Returns:
            True if the SMS was sent successfully.
        """
        client = await self._get_client()

        try:
            payload = {
                "api_key": self._api_key,
                "api_secret": self._api_secret,
                "senderid": self._sender_id,
                "msisdn": phone,
                "message": message,
            }

            response = await client.post(
                SSL_WIRELESS_API_URL,
                data=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()

            # SSL Wireless returns JSON with status
            result = response.json()
            status = result.get("status", "")

            if status.upper() in ("SUCCESS", "OK", "200"):
                logger.info(
                    "SMS sent to %s (sender=%s)",
                    phone,
                    self._sender_id,
                )
                return True
            else:
                logger.warning(
                    "SMS API returned non-success status: %s (phone=%s)",
                    status,
                    phone,
                )
                return False

        except httpx.TimeoutException:
            logger.warning("SMS send timed out (phone=%s)", phone)
            return False
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "SMS HTTP error (phone=%s): %d %s",
                phone,
                exc.response.status_code,
                exc.response.text,
            )
            return False
        except Exception:
            logger.exception("SMS send failed (phone=%s)", phone)
            return False

    # ── Internal: Client Management ──────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
