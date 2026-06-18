"""
Vision OS — Unit Tests for CDN Manager (Sprint 10.4)

Tests the CDN integration module including uploads, signed URLs,
cache invalidation, object management, and storage usage.
"""

import pytest
import time
from datetime import datetime

from backend.storage.cdn_manager import (
    CDNManager,
    StorageUsage,
    CACHE_TTL_STATIC,
    CACHE_TTL_THUMBNAIL,
    CACHE_TTL_CLIP,
    CACHE_TTL_RECEIPT,
    DEFAULT_SIGNED_URL_EXPIRY,
)


@pytest.fixture
def cdn() -> CDNManager:
    """Create a fresh CDNManager instance for each test."""
    return CDNManager(bucket="test-bucket", cdn_base="https://cdn.test.visionos.app")


# ------------------------------------------------------------------
# Uploads
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_static_returns_cdn_url(cdn: CDNManager):
    """upload_static should return a valid CDN URL."""
    url = await cdn.upload_static("css/style.css", "text/css")
    assert "cdn.test.visionos.app" in url
    assert "static/css/style.css" in url


@pytest.mark.asyncio
async def test_upload_thumbnail_stores_correctly(cdn: CDNManager):
    """upload_thumbnail should store image data and return correct path."""
    image_data = b"fake-jpeg-bytes"
    url = await cdn.upload_thumbnail("cam1", "evt001", image_data)
    assert "cdn.test.visionos.app" in url
    assert "thumbnails" in url
    assert "cam1" in url
    assert "evt001" in url


@pytest.mark.asyncio
async def test_upload_clip_stores_correctly(cdn: CDNManager):
    """upload_clip should store clip data and return correct path."""
    clip_data = b"fake-mp4-bytes"
    url = await cdn.upload_clip("cam1", "evt001", clip_data)
    assert "cdn.test.visionos.app" in url
    assert "clips" in url
    assert "cam1" in url
    assert "evt001" in url


# ------------------------------------------------------------------
# Signed URLs
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_signed_url_generates_valid_url(cdn: CDNManager):
    """get_signed_url should generate a URL with signing parameters."""
    signed = await cdn.get_signed_url("thumbnails/u1/cam1/e1.jpg")
    assert "Expires=" in signed
    assert "KeyName=" in signed
    assert "Signature=" in signed
    assert "storage.googleapis.com" in signed


@pytest.mark.asyncio
async def test_signed_url_expires_after_time(cdn: CDNManager):
    """Signed URL should have an expiration time."""
    signed = await cdn.get_signed_url("thumbnails/u1/cam1/e1.jpg", expires_in=60)
    # Parse the Expires parameter
    import urllib.parse
    parsed = urllib.parse.urlparse(signed)
    params = urllib.parse.parse_qs(parsed.query)
    expires = int(params["Expires"][0])
    now = int(time.time())
    assert expires > now  # should be in the future
    assert expires <= now + 61  # within ~1 minute


# ------------------------------------------------------------------
# Cache Invalidation
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalidate_cache_removes_object(cdn: CDNManager):
    """invalidate_cache should return success for an object path."""
    result = await cdn.invalidate_cache("static/css/style.css")
    assert result["status"] == "ok"
    assert result["action"] == "invalidate_object"
    assert "cdn.test.visionos.app" in result["cdn_url"]


@pytest.mark.asyncio
async def test_invalidate_prefix_removes_multiple(cdn: CDNManager):
    """invalidate_prefix should report count of matching objects."""
    # Upload a few objects under the same prefix
    await cdn.upload_thumbnail("cam1", "evt001", b"data1")
    await cdn.upload_thumbnail("cam1", "evt002", b"data2")
    await cdn.upload_thumbnail("cam1", "evt003", b"data3")

    result = await cdn.invalidate_prefix("thumbnails/default_user/cam1")
    assert result["status"] == "ok"
    assert result["objects_invalidated"] == 3


# ------------------------------------------------------------------
# CDN URLs
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cdn_url_returns_correct_path(cdn: CDNManager):
    """get_cdn_url should return the full CDN URL for a path."""
    url = cdn.get_cdn_url("static/js/app.js")
    assert url == "https://cdn.test.visionos.app/static/js/app.js"


# ------------------------------------------------------------------
# Object Management
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_removes_from_storage(cdn: CDNManager):
    """delete_object should remove the object and report existence."""
    await cdn.upload_static("css/style.css", "text/css")
    result = await cdn.delete_object("static/css/style.css")
    assert result["status"] == "ok"
    assert result["existed"] is True

    # Verify it's gone
    remaining = await cdn.list_objects("static/")
    assert "static/css/style.css" not in remaining


@pytest.mark.asyncio
async def test_delete_object_nonexistent(cdn: CDNManager):
    """delete_object should report false for non-existent objects."""
    result = await cdn.delete_object("nonexistent/path.txt")
    assert result["existed"] is False


@pytest.mark.asyncio
async def test_list_objects_returns_prefix_matches(cdn: CDNManager):
    """list_objects should return all objects under a prefix."""
    await cdn.upload_thumbnail("cam1", "evt001", b"data")
    await cdn.upload_thumbnail("cam2", "evt002", b"data")
    await cdn.upload_clip("cam1", "evt001", b"data")

    thumbnails = await cdn.list_objects("thumbnails/")
    assert len(thumbnails) == 2
    assert all("thumbnails" in p for p in thumbnails)

    clips = await cdn.list_objects("clips/")
    assert len(clips) == 1


# ------------------------------------------------------------------
# Storage Usage
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_storage_usage_calculates_correctly(cdn: CDNManager):
    """get_storage_usage should report accurate byte/mb counts."""
    await cdn.upload_static("css/style.css", "text/css")
    await cdn.upload_thumbnail("cam1", "evt001", b"thumb-data")
    await cdn.upload_clip("cam1", "evt001", b"clip-data-longer")

    usage = await cdn.get_storage_usage()
    assert usage.total_objects == 3
    assert usage.total_bytes > 0
    assert usage.total_mb > 0.0
    assert usage.oldest_object is not None
    assert usage.newest_object is not None


@pytest.mark.asyncio
async def test_get_storage_usage_with_prefix(cdn: CDNManager):
    """get_storage_usage should filter by prefix."""
    await cdn.upload_thumbnail("cam1", "evt001", b"data")
    await cdn.upload_static("css/style.css", "text/css")

    usage = await cdn.get_storage_usage(prefix="thumbnails/")
    assert usage.total_objects == 1
    assert usage.prefix == "thumbnails/"


# ------------------------------------------------------------------
# CDN Path Formats
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thumbnail_path_format(cdn: CDNManager):
    """Thumbnail paths should follow /thumbnails/{user}/{camera}/{event}.jpg."""
    url = await cdn.upload_thumbnail("camA", "evtX", b"data")
    assert "/thumbnails/" in url
    assert "/camA/" in url
    assert "/evtX.jpg" in url


@pytest.mark.asyncio
async def test_clip_path_format(cdn: CDNManager):
    """Clip paths should follow /clips/{user}/{camera}/{event}.mp4."""
    url = await cdn.upload_clip("camB", "evtY", b"data")
    assert "/clips/" in url
    assert "/camB/" in url
    assert "/evtY.mp4" in url


# ------------------------------------------------------------------
# Cache TTLs
# ------------------------------------------------------------------


def test_static_cache_ttl():
    """Static assets should have 1-hour cache TTL."""
    assert CACHE_TTL_STATIC == 3600


def test_thumbnail_cache_ttl():
    """Thumbnails should have 24-hour cache TTL."""
    assert CACHE_TTL_THUMBNAIL == 86400


def test_clip_cache_ttl():
    """Clips should have no cache."""
    assert CACHE_TTL_CLIP == 0


def test_receipt_cache_ttl():
    """Receipts should have no cache."""
    assert CACHE_TTL_RECEIPT == 0


# ------------------------------------------------------------------
# StorageUsage Dataclass
# ------------------------------------------------------------------


def test_storage_usage_defaults():
    """StorageUsage should have sensible defaults."""
    usage = StorageUsage()
    assert usage.total_objects == 0
    assert usage.total_bytes == 0
    assert usage.total_mb == 0.0
    assert usage.oldest_object is None
    assert usage.newest_object is None


def test_storage_usage_custom():
    """StorageUsage should accept custom values."""
    now = datetime.utcnow()
    usage = StorageUsage(
        prefix="test/",
        total_objects=5,
        total_bytes=1024,
        total_mb=1.0,
        oldest_object=now,
        newest_object=now,
    )
    assert usage.prefix == "test/"
    assert usage.total_objects == 5
    assert usage.total_bytes == 1024
