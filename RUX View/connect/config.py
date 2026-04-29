"""App Configuration — JSON-based persistent settings for Vision OS Connect.

Config is stored as a JSON file in %APPDATA%/VisionOS/config.json.
Provides a dataclass-based configuration model with load/save helpers.
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", "."), "VisionOS")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


@dataclass
class AppConfig:
    """Application configuration for Vision OS Connect client agent.

    All fields have sensible defaults so the app can start without
    a pre-existing config file.  The user is expected to fill in
    ``api_key``, ``camera_id``, ``camera_name``, and ``rtsp_url``
    via the Settings window before first use.

    Attributes:
        api_key: Firebase ID token or API key for backend auth.
        camera_id: Unique camera identifier assigned by the backend.
        camera_name: Human-readable camera label (e.g. "Front Gate").
        rtsp_url: RTSP stream URL (e.g. ``rtsp://admin:pass@192.168.1.100:554/stream1``).
        mode: Camera mode — one of ``indoor``, ``outdoor``, ``parking``, ``mixed``, ``shop``.
        backend_url: Backend API base URL.
        audio_enabled: Whether audio capture + YAMNet classification is active.
        auto_start: Whether to start processing automatically on launch.
        ignore_zones: List of ``[x, y, w, h]`` rectangles to mask out in motion detection.
    """

    api_key: str = ""
    camera_id: str = ""
    camera_name: str = ""
    rtsp_url: str = ""
    mode: str = "indoor"
    backend_url: str = "https://api.visionos.app"
    audio_enabled: bool = True
    auto_start: bool = False
    ignore_zones: list = None

    def __post_init__(self) -> None:
        """Ensure mutable defaults are initialised."""
        if self.ignore_zones is None:
            self.ignore_zones = []


def load_config() -> AppConfig:
    """Load configuration from the JSON file.

    Reads ``%APPDATA%/VisionOS/config.json`` and returns an
    ``AppConfig`` instance.  If the file does not exist or is
    malformed, returns an ``AppConfig`` with default values.

    Returns:
        AppConfig instance populated from the file (or defaults).
    """
    if not config_exists():
        logger.info("No config file found at %s — using defaults", CONFIG_FILE)
        return AppConfig()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Only consume keys that belong to AppConfig — ignore extras
        valid_keys = {f.name for f in AppConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        config = AppConfig(**filtered)
        logger.info("Config loaded from %s", CONFIG_FILE)
        return config

    except (json.JSONDecodeError, IOError, TypeError) as exc:
        logger.warning(
            "Failed to load config from %s: %s — using defaults",
            CONFIG_FILE,
            exc,
        )
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to the JSON file.

    Creates the ``%APPDATA%/VisionOS/`` directory if it does not
    exist, then writes the config as pretty-printed JSON.

    Args:
        config: AppConfig instance to persist.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2, default=str)
        logger.info("Config saved to %s", CONFIG_FILE)
    except IOError as exc:
        logger.exception("Failed to save config to %s: %s", CONFIG_FILE, exc)
        raise


def config_exists() -> bool:
    """Check whether a config file already exists on disk.

    Returns:
        True if ``%APPDATA%/VisionOS/config.json`` exists.
    """
    return os.path.isfile(CONFIG_FILE)
