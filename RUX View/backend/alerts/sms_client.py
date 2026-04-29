"""
sms_client.py — SSL Wireless SMS client for emergency fallback.

Only used for HIGH alerts during internet outage.
Cost: ~0.30 BDT per SMS.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class SMSClient:
    """SSL Wireless SMS client for emergency fallback."""

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        """Initialize SSL Wireless SMS client.

        Args:
            api_key: SSL Wireless API key.
            api_secret: SSL Wireless API secret.
            sender_id: SMS sender ID (approved).
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.sender_id = sender_id
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS via SSL Wireless API.

        Args:
            phone: Recipient phone number (Bangladesh format, e.g. 88017XXXXXXXX).
            message: SMS text content.

        Returns:
            True if sent successfully.
        """
        try:
            client = await self._get_client()
            # SSL Wireless API endpoint
            url = "https://sms.sslwireless.com/pushapi/dynamic/server.php"
            payload = {
                "api_key": self.api_key,
                "api_secret": self.api_secret,
                "sid": self.sender_id,
                "msisdn": phone,
                "csms_id": f"VO-{phone[:5]}",
                "sms": message,
            }
            response = await client.post(url, data=payload)
            result = response.text
            logger.info("SSL SMS response: %s", result[:200])
            # Check for success indicators in response
            return "SUCCESS" in result.upper() or "200" in result[:10]
        except Exception as exc:
            logger.error("SSL SMS send failed: %s", exc, exc_info=True)
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
