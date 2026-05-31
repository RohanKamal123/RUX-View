"""App Configuration — JSON-based persistent settings for Vision OS Connect.

Config is stored as a JSON file in %APPDATA%/VisionOS/config.json.
Provides a dataclass-based configuration model with load/save helpers.

Environment variable overrides (applied after loading from file):
    BACKEND_URL     → backend_url
    RTSP_URL        → rtsp_url
    CAMERA_ID       → camera_id
    CAMERA_NAME     → camera_name
    API_KEY         → api_key
    AUDIO_ENABLED   → audio_enabled (true/false)
    MOTION_THRESHOLD → motion_threshold (float)
    MOTION_MIN_AREA → motion_min_area (int)
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

# ── Dev Auth Token ─────────────────────────────────────────────────────────────
# When no api_key is provided (no config file or empty), use this dev token
# so the client can authenticate with the backend in development mode.
DEV_AUTH_TOKEN = "dev-token-001"


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
    ignore_zones: Optional[list] = None

    motion_threshold: float = 0.05
    motion_min_area: int = 8000

    def __post_init__(self) -> None:
        """Ensure mutable defaults are initialised."""
        if self.ignore_zones is None:
            self.ignore_zones = []


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Apply environment variable overrides to a config instance.

    Args:
        config: AppConfig instance to override.

    Returns:
        The same config instance with overridden fields.
    """
    env_overrides = {
        "backend_url": os.environ.get("BACKEND_URL") or os.environ.get("DASHBOARD_URL"),
        "rtsp_url": os.environ.get("RTSP_URL"),
        "camera_id": os.environ.get("CAMERA_ID"),
        "camera_name": os.environ.get("CAMERA_NAME"),
        "api_key": os.environ.get("API_KEY") or os.environ.get("AUTH_TOKEN"),
    }


    for field, value in env_overrides.items():
        if value is not None:
            setattr(config, field, value)
            logger.info("Config override from env: %s = %s", field, value)

    # Boolean override
    audio_env = os.environ.get("AUDIO_ENABLED")
    if audio_env is not None:
        config.audio_enabled = audio_env.lower() in ("1", "true", "yes")

    # Float override
    threshold_env = os.environ.get("MOTION_THRESHOLD")
    if threshold_env is not None:
        try:
            config.motion_threshold = float(threshold_env)
        except ValueError:
            logger.warning("Invalid MOTION_THRESHOLD value: %s", threshold_env)

    # Int override
    min_area_env = os.environ.get("MOTION_MIN_AREA")
    if min_area_env is not None:
        try:
            config.motion_min_area = int(min_area_env)
        except ValueError:
            logger.warning("Invalid MOTION_MIN_AREA value: %s", min_area_env)

    return config


def load_config() -> AppConfig:
    """Load configuration from the JSON file, then apply env overrides.

    Reads ``%APPDATA%/VisionOS/config.json`` and returns an
    ``AppConfig`` instance.  If the file does not exist or is
    malformed, returns an ``AppConfig`` with default values.

    Environment variables override any file-based values (see module docstring).

    If ``api_key`` is still empty after loading, defaults to ``dev-token-001``
    for development-mode authentication.

    Returns:
        AppConfig instance populated from the file (or defaults).
    """
    if not config_exists():
        logger.info("No config file found at %s — using defaults", CONFIG_FILE)
        config = AppConfig()
    else:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Only consume keys that belong to AppConfig — ignore extras
            valid_keys = {f.name for f in AppConfig.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            config = AppConfig(**filtered)
            logger.info("Config loaded from %s", CONFIG_FILE)

        except (json.JSONDecodeError, IOError, TypeError) as exc:
            logger.warning(
                "Failed to load config from %s: %s — using defaults",
                CONFIG_FILE,
                exc,
            )
            config = AppConfig()

    # Apply environment variable overrides
    config = _apply_env_overrides(config)

    # Dev auth token fallback
    if not config.api_key:
        config.api_key = DEV_AUTH_TOKEN
        logger.info("No API key configured — using dev auth token: %s", DEV_AUTH_TOKEN)

    return config



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
