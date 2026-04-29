"""
Vision OS — CDN Integration Module (Sprint 10.4)

Handles uploading, caching, signed URLs, and cache invalidation
for static assets, thumbnails, clips, and receipts via Google Cloud CDN + Storage.
"""

import os
import time
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode


@dataclass
class StorageUsage:
    """Storage usage metrics for a given prefix/path."""
    prefix: str = ""
    total_objects: int = 0
    total_bytes: int = 0
    total_mb: float = 0.0
    oldest_object: Optional[datetime] = None
    newest_object: Optional[datetime] = None


# Cache TTL constants (seconds)
CACHE_TTL_STATIC = 3600          # 1 hour
CACHE_TTL_THUMBNAIL = 86400      # 24 hours
CACHE_TTL_CLIP = 0               # no cache (signed URLs)
CACHE_TTL_RECEIPT = 0            # no cache (signed URLs)

# Default expiry for signed URLs
DEFAULT_SIGNED_URL_EXPIRY = 3600  # 1 hour

# Cloud Storage bucket name (configurable via env var)
STORAGE_BUCKET = os.getenv("VISIONOS_STORAGE_BUCKET", "vision-os-storage")
CDN_BASE_URL = os.getenv("VISIONOS_CDN_BASE_URL", "https://cdn.visionos.app")
GCS_BASE_URL = os.getenv("VISIONOS_GCS_BASE_URL", "https://storage.googleapis.com")
SIGNING_KEY = os.getenv("VISIONOS_CDN_SIGNING_KEY", "dev-signing-key")


class CDNManager:
    """
    Manages CDN uploads, signed URLs, cache invalidation, and storage introspection.

    Uses Google Cloud Storage + CDN under the hood. This implementation provides
    a mock/local-compatible interface that can be swapped for real GCS clients
    in production.
    """

    def __init__(self, bucket: str = STORAGE_BUCKET, cdn_base: str = CDN_BASE_URL):
        self.bucket = bucket
        self.cdn_base = cdn_base.rstrip("/")
        self.gcs_base = GCS_BASE_URL.rstrip("/")
        # In-memory store for dev/testing
        self._store: dict[str, bytes] = {}
        self._metadata: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------

    async def upload_static(self, file_path: str, content_type: str) -> str:
        """
        Upload a static asset (CSS, JS, image) and return its CDN URL.

        :param file_path: Relative path under static/, e.g. "css/style.css"
        :param content_type: MIME type, e.g. "text/css"
        :returns: Full CDN URL
        """
        object_path = f"static/{file_path.lstrip('/')}"
        # In production this would call gcs_client.blob(object_path).upload_from_string(...)
        self._store[object_path] = b""
        self._metadata[object_path] = {
            "content_type": content_type,
            "created": datetime.utcnow(),
            "cache_ttl": CACHE_TTL_STATIC,
        }
        return self.get_cdn_url(object_path)

    async def upload_thumbnail(
        self, camera_id: str, event_id: str, image_data: bytes
    ) -> str:
        """
        Upload an event thumbnail and return its CDN URL.

        Path: /thumbnails/{user_id}/{camera_id}/{event_id}.jpg

        :param camera_id: Camera identifier
        :param event_id: Event identifier
        :param image_data: JPEG bytes
        :returns: Full CDN URL
        """
        # In production user_id would come from auth context
        user_id = self._resolve_user_id()
        object_path = f"thumbnails/{user_id}/{camera_id}/{event_id}.jpg"
        self._store[object_path] = image_data
        self._metadata[object_path] = {
            "content_type": "image/jpeg",
            "created": datetime.utcnow(),
            "cache_ttl": CACHE_TTL_THUMBNAIL,
        }
        return self.get_cdn_url(object_path)

    async def upload_clip(
        self, camera_id: str, event_id: str, clip_data: bytes
    ) -> str:
        """
        Upload a video clip and return its CDN URL.

        Path: /clips/{user_id}/{camera_id}/{event_id}.mp4

        :param camera_id: Camera identifier
        :param event_id: Event identifier
        :param clip_data: MP4 bytes
        :returns: Full CDN URL
        """
        user_id = self._resolve_user_id()
        object_path = f"clips/{user_id}/{camera_id}/{event_id}.mp4"
        self._store[object_path] = clip_data
        self._metadata[object_path] = {
            "content_type": "video/mp4",
            "created": datetime.utcnow(),
            "cache_ttl": CACHE_TTL_CLIP,
        }
        return self.get_cdn_url(object_path)

    async def upload_receipt(
        self, user_id: str, payment_id: str, pdf_data: bytes
    ) -> str:
        """
        Upload a payment receipt PDF.

        Path: /receipts/{user_id}/{payment_id}.pdf
        """
        object_path = f"receipts/{user_id}/{payment_id}.pdf"
        self._store[object_path] = pdf_data
        self._metadata[object_path] = {
            "content_type": "application/pdf",
            "created": datetime.utcnow(),
            "cache_ttl": CACHE_TTL_RECEIPT,
        }
        return self.get_cdn_url(object_path)

    # ------------------------------------------------------------------
    # Signed URLs
    # ------------------------------------------------------------------

    async def get_signed_url(
        self, object_path: str, expires_in: int = DEFAULT_SIGNED_URL_EXPIRY
    ) -> str:
        """
        Generate a time-limited signed URL for private content.

        Uses HMAC-SHA256 signing compatible with Cloud CDN signed URLs.

        :param object_path: Path of the object (e.g. "thumbnails/u1/cam1/e1.jpg")
        :param expires_in: Seconds until URL expires
        :returns: Signed URL string
        """
        expires = int(time.time()) + expires_in
        url = f"{self.gcs_base}/{self.bucket}/{object_path.lstrip('/')}"

        # Build signing string: URL + Expires + KeyName
        signing_string = f"{url}\n{expires}\nvisionos-key"
        signature = hmac.new(
            SIGNING_KEY.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

        params = urlencode({
            "Expires": expires,
            "KeyName": "visionos-key",
            "Signature": signature_b64,
        })
        return f"{url}?{params}"

    # ------------------------------------------------------------------
    # Cache Invalidation
    # ------------------------------------------------------------------

    async def invalidate_cache(self, object_path: str) -> dict:
        """
        Invalidate the CDN cache for a single object.

        :param object_path: Path of the object to invalidate
        :returns: Status dict
        """
        # In production: call CDN cache invalidation API
        url = self.get_cdn_url(object_path)
        return {
            "status": "ok",
            "action": "invalidate_object",
            "object_path": object_path,
            "cdn_url": url,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def invalidate_prefix(self, prefix: str) -> dict:
        """
        Invalidate all objects under a given prefix.

        :param prefix: e.g. "thumbnails/u1/cam1"
        :returns: Status dict
        """
        matching = [
            path for path in self._store if path.startswith(prefix)
        ]
        return {
            "status": "ok",
            "action": "invalidate_prefix",
            "prefix": prefix,
            "objects_invalidated": len(matching),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # CDN URLs
    # ------------------------------------------------------------------

    def get_cdn_url(self, object_path: str) -> str:
        """
        Return the public CDN URL for a given object path.

        :param object_path: e.g. "static/css/style.css"
        :returns: Full CDN URL
        """
        return f"{self.cdn_base}/{object_path.lstrip('/')}"

    # ------------------------------------------------------------------
    # Object Management
    # ------------------------------------------------------------------

    async def delete_object(self, object_path: str) -> dict:
        """
        Delete an object from storage and invalidate CDN cache.

        :param object_path: Path of the object to delete
        :returns: Status dict
        """
        existed = object_path in self._store
        self._store.pop(object_path, None)
        self._metadata.pop(object_path, None)
        return {
            "status": "ok",
            "action": "delete_object",
            "object_path": object_path,
            "existed": existed,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def list_objects(
        self, prefix: str, limit: int = 100
    ) -> list[str]:
        """
        List object paths under a given prefix.

        :param prefix: e.g. "thumbnails"
        :param limit: Maximum number of paths to return
        :returns: List of object paths
        """
        matches = sorted(
            path for path in self._store if path.startswith(prefix)
        )
        return matches[:limit]

    # ------------------------------------------------------------------
    # Storage Usage
    # ------------------------------------------------------------------

    async def get_storage_usage(self, prefix: str = "") -> StorageUsage:
        """
        Compute storage usage for a given prefix.

        :param prefix: Optional prefix filter (e.g. "thumbnails")
        :returns: StorageUsage dataclass
        """
        matching = {
            path: data
            for path, data in self._store.items()
            if path.startswith(prefix)
        }

        total_bytes = sum(len(data) for data in matching.values())
        timestamps = [
            self._metadata[path]["created"]
            for path in matching
            if path in self._metadata and "created" in self._metadata[path]
        ]

        return StorageUsage(
            prefix=prefix,
            total_objects=len(matching),
            total_bytes=total_bytes,
            total_mb=round(total_bytes / (1024 * 1024), 2),
            oldest_object=min(timestamps) if timestamps else None,
            newest_object=max(timestamps) if timestamps else None,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_user_id(self) -> str:
        """
        Placeholder for auth context resolution.
        In production this would pull from the request's auth token/session.
        """
        return "default_user"
