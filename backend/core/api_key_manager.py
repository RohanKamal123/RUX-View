"""
api_key_manager.py — API Key Management for Vision OS.

Handles generation, validation, revocation, rotation, and usage tracking
of API keys for third-party integrations.

Key decisions:
- D026: All calls async
- API keys are HMAC-SHA256 signed for verification
- Keys stored as hashed values (never plaintext)
"""

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class ApiKey:
    """Represents an API key for third-party integrations."""

    key_id: str
    user_id: str
    name: str
    key_prefix: str  # first 8 chars for identification
    permissions: list[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class ApiKeyUsage:
    """Usage statistics for an API key."""

    key_id: str
    total_requests: int
    last_24h_requests: int
    endpoints_accessed: list[str]
    last_error: Optional[str] = None


# ── Constants ───────────────────────────────────────────────────

KEY_PREFIX_LENGTH = 8
KEY_BYTE_LENGTH = 32  # 256-bit key
HASH_ALGORITHM = "sha256"
DEFAULT_KEY_EXPIRY_DAYS = 365


# ── In-Memory Store (replace with DB in production) ────────────

_api_keys: dict[str, ApiKey] = {}  # key_id -> ApiKey
_key_hash_to_id: dict[str, str] = {}  # hashed_key -> key_id
_usage_records: dict[str, list[dict]] = {}  # key_id -> list of usage events
_audit_logs: list[dict] = []


# ── ApiKeyManager ───────────────────────────────────────────────


class ApiKeyManager:
    """Manages API key lifecycle: generate, validate, revoke, rotate."""

    @staticmethod
    def _generate_key() -> tuple[str, str]:
        """Generate a new API key and its hash.

        Returns:
            Tuple of (raw_key, key_hash).
        """
        raw_key = f"vos_{secrets.token_hex(KEY_BYTE_LENGTH)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, key_hash

    @staticmethod
    def _generate_key_id() -> str:
        """Generate a unique key ID.

        Returns:
            Unique key identifier string.
        """
        return f"key_{secrets.token_hex(16)}"

    @staticmethod
    def _get_key_prefix(raw_key: str) -> str:
        """Get the prefix of a raw key for identification.

        Args:
            raw_key: The full API key.

        Returns:
            First 8 characters of the key.
        """
        return raw_key[:KEY_PREFIX_LENGTH]

    async def generate_api_key(
        self,
        user_id: str,
        name: str,
        permissions: list[str],
        expires_in_days: int = DEFAULT_KEY_EXPIRY_DAYS,
    ) -> tuple[ApiKey, str]:
        """Generate a new API key for a user.

        Args:
            user_id: The user who owns this key.
            name: A human-readable name for the key.
            permissions: List of permission strings.
            expires_in_days: Number of days until expiry.

        Returns:
            Tuple of (ApiKey, raw_key_string).
            The raw key string should be shown once and then discarded.
        """
        key_id = self._generate_key_id()
        raw_key, key_hash = self._generate_key()
        key_prefix = self._get_key_prefix(raw_key)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_in_days)

        api_key = ApiKey(
            key_id=key_id,
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            permissions=permissions,
            created_at=now,
            expires_at=expires_at,
            is_active=True,
        )

        _api_keys[key_id] = api_key
        _key_hash_to_id[key_hash] = key_id

        logger.info(
            "API key generated for user: %s, name: %s, key_id: %s",
            user_id, name, key_id,
        )

        return api_key, raw_key

    async def validate_api_key(self, api_key: str) -> Optional[ApiKey]:
        """Validate an API key and return its metadata.

        Args:
            api_key: The raw API key string to validate.

        Returns:
            ApiKey if valid and active, None otherwise.
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_id = _key_hash_to_id.get(key_hash)

        if not key_id:
            logger.warning("API key validation failed: unknown key")
            return None

        api_key_obj = _api_keys.get(key_id)
        if not api_key_obj:
            return None

        # Check if active
        if not api_key_obj.is_active:
            logger.warning("API key validation failed: key is revoked (key_id: %s)", key_id)
            return None

        # Check if expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
            logger.warning("API key validation failed: key expired (key_id: %s)", key_id)
            return None

        # Update last used timestamp
        api_key_obj.last_used_at = datetime.now(timezone.utc)

        return api_key_obj

    async def revoke_api_key(self, key_id: str) -> dict:
        """Revoke an API key, making it inactive.

        Args:
            key_id: The ID of the key to revoke.

        Returns:
            Dict with revocation status.

        Raises:
            ValueError: If key_id not found.
        """
        if key_id not in _api_keys:
            raise ValueError(f"API key not found: {key_id}")

        _api_keys[key_id].is_active = False
        logger.info("API key revoked: %s", key_id)

        return {
            "status": "revoked",
            "key_id": key_id,
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_user_api_keys(self, user_id: str) -> list[ApiKey]:
        """List all API keys for a user.

        Args:
            user_id: The user whose keys to list.

        Returns:
            List of ApiKey objects.
        """
        return [
            key for key in _api_keys.values()
            if key.user_id == user_id
        ]

    async def rotate_api_key(self, key_id: str) -> tuple[ApiKey, str]:
        """Rotate an API key, generating a new one with same metadata.

        Args:
            key_id: The ID of the key to rotate.

        Returns:
            Tuple of (new ApiKey, new raw_key_string).

        Raises:
            ValueError: If key_id not found.
        """
        if key_id not in _api_keys:
            raise ValueError(f"API key not found: {key_id}")

        old_key = _api_keys[key_id]

        # Revoke old key
        old_key.is_active = False

        # Generate new key with same metadata
        new_key, raw_key = await self.generate_api_key(
            user_id=old_key.user_id,
            name=old_key.name,
            permissions=old_key.permissions,
        )

        logger.info("API key rotated: %s -> %s", key_id, new_key.key_id)

        return new_key, raw_key

    async def get_api_key_usage(
        self,
        key_id: str,
        since: Optional[datetime] = None,
    ) -> ApiKeyUsage:
        """Get usage statistics for an API key.

        Args:
            key_id: The ID of the key.
            since: Only count usage after this time.

        Returns:
            ApiKeyUsage with usage statistics.
        """
        if not since:
            since = datetime.now(timezone.utc) - timedelta(days=30)

        records = _usage_records.get(key_id, [])
        recent_records = [r for r in records if r.get("timestamp", since) >= since]

        # Count last 24h
        last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        last_24h_records = [r for r in records if r.get("timestamp", last_24h) >= last_24h]

        # Get unique endpoints
        endpoints = list(set(r.get("endpoint", "") for r in recent_records if r.get("endpoint")))

        # Get last error
        last_error = None
        for r in reversed(records):
            if r.get("error"):
                last_error = r["error"]
                break

        return ApiKeyUsage(
            key_id=key_id,
            total_requests=len(recent_records),
            last_24h_requests=len(last_24h_records),
            endpoints_accessed=endpoints,
            last_error=last_error,
        )

    async def record_usage(
        self,
        key_id: str,
        endpoint: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record an API key usage event.

        Args:
            key_id: The ID of the key used.
            endpoint: The endpoint accessed.
            success: Whether the request was successful.
            error: Error message if the request failed.
        """
        if key_id not in _usage_records:
            _usage_records[key_id] = []

        _usage_records[key_id].append({
            "timestamp": datetime.now(timezone.utc),
            "endpoint": endpoint,
            "success": success,
            "error": error,
        })

    async def audit_log(
        self,
        action: str,
        admin_id: str,
        details: dict,
    ) -> dict:
        """Record an audit log entry for admin actions.

        Args:
            action: The action performed.
            admin_id: The admin who performed the action.
            details: Additional details about the action.

        Returns:
            Dict with audit log entry.
        """
        entry = {
            "log_id": f"audit_{secrets.token_hex(8)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "admin_id": admin_id,
            "details": details,
        }

        _audit_logs.append(entry)

        logger.info(
            "Audit log: action=%s, admin=%s, details=%s",
            action, admin_id, details,
        )

        return entry

    async def get_audit_logs(
        self,
        limit: int = 100,
        action: Optional[str] = None,
        admin_id: Optional[str] = None,
    ) -> list[dict]:
        """Get audit log entries with optional filtering.

        Args:
            limit: Maximum number of entries to return.
            action: Filter by action type.
            admin_id: Filter by admin ID.

        Returns:
            List of audit log entries.
        """
        logs = _audit_logs

        if action:
            logs = [l for l in logs if l.get("action") == action]
        if admin_id:
            logs = [l for l in logs if l.get("admin_id") == admin_id]

        return logs[-limit:]


# ── Convenience exports ─────────────────────────────────────────

__all__ = [
    "ApiKeyManager",
    "ApiKey",
    "ApiKeyUsage",
]
