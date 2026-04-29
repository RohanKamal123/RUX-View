import requests
import os
import logging

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")


def send_alert(snapshot_path: str, camera_name: str = "Camera"):
    """Send a Telegram photo alert. Runs synchronously — call from a thread."""
    if not os.path.exists(snapshot_path):
        log.warning(f"Snapshot not found: {snapshot_path}")
        return

    caption = f"🚨 Person detected\n📷 {camera_name}"

    try:
        with open(snapshot_path, "rb") as photo:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": photo},
                timeout=15
            )
        if resp.status_code == 200:
            log.info(f"Telegram alert sent for [{camera_name}]")
        else:
            log.warning(f"Telegram returned {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        log.error(f"Telegram alert failed: {e}")