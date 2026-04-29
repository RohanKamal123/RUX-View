"""Centralized error handling with structured logging for Vision OS.

Handles every failure mode gracefully with structured JSON logging,
error categorization, severity levels, and admin alerts for critical errors.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Callable, Any
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    NETWORK = "network"           # Connection timeouts, DNS failures
    API = "api"                   # Gemini/Whisper API errors
    DATABASE = "database"         # Connection pool, query failures
    AUTH = "auth"                 # Token expiry, invalid credentials
    VALIDATION = "validation"     # Invalid input data
    INTERNAL = "internal"         # Unexpected bugs
    RESOURCE = "resource"         # Memory, disk, rate limits


@dataclass
class ErrorRecord:
    """Structured error record with full context."""
    timestamp: datetime
    camera_id: Optional[str]
    module: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[str] = None
    context: dict = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class ErrorHandler:
    """Centralized error handling with structured logging.

    Features:
    - Structured JSON logging for all errors
    - Error categorization and severity levels
    - Camera-specific error tracking
    - Admin alerts for CRITICAL errors
    - Camera degradation marking
    """

    def __init__(self, logger=None):
        """Initialize error handler.

        Args:
            logger: Optional structured logger instance
        """
        self._logger = logger or logging.getLogger("visionos.errors")
        self._error_store: list[ErrorRecord] = []
        self._degraded_cameras: set[str] = set()

    async def handle_error(
        self,
        camera_id: Optional[str],
        module: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        message: str,
        exception: Optional[Exception] = None,
        context: Optional[dict] = None,
    ) -> ErrorRecord:
        """Handle an error with structured logging.

        Steps:
        1. Create ErrorRecord with full context
        2. Log with appropriate severity
        3. If CRITICAL: trigger alert to admin
        4. If camera-specific: mark camera as degraded
        5. Return ErrorRecord for tracking

        Args:
            camera_id: Camera UUID (None if not camera-specific)
            module: Module name where error occurred
            category: Error category
            severity: Error severity level
            message: Human-readable error message
            exception: Optional exception object
            context: Optional additional context dict

        Returns:
            ErrorRecord
        """
        record = ErrorRecord(
            timestamp=datetime.utcnow(),
            camera_id=camera_id,
            module=module,
            category=category,
            severity=severity,
            message=message,
            exception=str(exception) if exception else None,
            context=context or {},
        )

        # Store for tracking
        self._error_store.append(record)

        # Structured logging
        self._log_structured(record)

        # Mark camera as degraded if camera-specific error
        if camera_id and severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL):
            self._degraded_cameras.add(camera_id)

        # Alert admin for critical errors
        if self._should_alert_admin(severity):
            await self._alert_admin(record)

        return record

    async def get_camera_errors(
        self,
        camera_id: str,
        hours_back: int = 24,
    ) -> list[ErrorRecord]:
        """Get recent errors for a specific camera.

        Args:
            camera_id: Camera UUID
            hours_back: Number of hours to look back

        Returns:
            List of ErrorRecord for the camera
        """
        cutoff = datetime.utcnow().timestamp() - (hours_back * 3600)
        return [
            e for e in self._error_store
            if e.camera_id == camera_id
            and e.timestamp.timestamp() >= cutoff
        ]

    async def get_unresolved_errors(self) -> list[ErrorRecord]:
        """Get all unresolved errors across all cameras.

        Returns:
            List of unresolved ErrorRecord
        """
        return [e for e in self._error_store if not e.resolved]

    async def resolve_error(self, error_id: str) -> bool:
        """Mark an error as resolved.

        Args:
            error_id: Index-based error identifier

        Returns:
            True if resolved
        """
        try:
            idx = int(error_id)
            if 0 <= idx < len(self._error_store):
                self._error_store[idx].resolved = True
                self._error_store[idx].resolution_time = datetime.utcnow()
                return True
        except (ValueError, IndexError):
            pass
        return False

    def _log_structured(self, record: ErrorRecord) -> None:
        """Log error as structured JSON.

        Args:
            record: ErrorRecord to log
        """
        log_data = {
            "timestamp": record.timestamp.isoformat(),
            "camera_id": record.camera_id,
            "module": record.module,
            "category": record.category.value,
            "severity": record.severity.value,
            "message": record.message,
            "exception": record.exception,
            "context": record.context,
        }

        log_level = {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }.get(record.severity, logging.INFO)

        self._logger.log(log_level, json.dumps(log_data))

    def _should_alert_admin(self, severity: ErrorSeverity) -> bool:
        """Check if error severity warrants admin alert.

        Args:
            severity: Error severity level

        Returns:
            True if admin should be alerted
        """
        return severity in (ErrorSeverity.CRITICAL,)

    async def _alert_admin(self, record: ErrorRecord) -> None:
        """Send admin alert for critical errors.

        Args:
            record: ErrorRecord to alert about
        """
        # In production, this sends via Telegram/email/SMS
        alert_msg = (
            f"[VISIONOS CRITICAL] {record.module}: {record.message}\n"
            f"Camera: {record.camera_id or 'N/A'}\n"
            f"Category: {record.category.value}\n"
            f"Time: {record.timestamp.isoformat()}"
        )
        logger.critical(f"ADMIN ALERT: {alert_msg}")

    def is_camera_degraded(self, camera_id: str) -> bool:
        """Check if a camera is in degraded state.

        Args:
            camera_id: Camera UUID

        Returns:
            True if camera has unresolved errors
        """
        return camera_id in self._degraded_cameras

    def clear_degraded(self, camera_id: str) -> None:
        """Clear degraded state for a camera.

        Args:
            camera_id: Camera UUID
        """
        self._degraded_cameras.discard(camera_id)
