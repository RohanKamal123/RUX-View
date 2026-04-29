"""Clip recording module for Vision OS.

Records short video clips around triggered events using ffmpeg.
Clips are stored in Google Cloud Storage with thumbnails extracted
from the clip midpoint.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import asyncio
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class ClipResult:
    """Result of a clip recording operation."""
    clip_id: int
    event_id: int
    clip_url: str
    thumbnail_url: str
    duration_sec: float
    file_size_bytes: int
    start_timestamp: datetime
    end_timestamp: datetime


class ClipRecorder:
    """Record video clips around triggered events.

    Connects to RTSP streams, buffers pre-trigger video, records
    post-trigger video, extracts thumbnails, and uploads to GCS.
    """

    def __init__(self, storage_client, db_session_factory,
                 temp_dir: str = "./temp_clips"):
        """Initialize clip recorder.

        Args:
            storage_client: Google Cloud Storage client
            db_session_factory: SQLAlchemy async session factory
            temp_dir: Temporary directory for clip processing
        """
        self.storage = storage_client
        self.db_session_factory = db_session_factory
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    async def record_clip(self, event_id: int, camera_id: str,
                           rtsp_url: str,
                           trigger_timestamp: datetime,
                           pre_trigger_seconds: int = 10,
                           post_trigger_seconds: int = 20) -> Optional[ClipResult]:
        """Record a video clip around a triggered event.

        Steps:
        1. Connect to RTSP stream
        2. Buffer pre_trigger_seconds of video before trigger
        3. Continue recording for post_trigger_seconds after trigger
        4. Extract thumbnail from clip midpoint
        5. Upload clip + thumbnail to Google Cloud Storage
        6. Save clip metadata to database
        7. Clean up temp files

        Args:
            event_id: Event ID to associate clip with
            camera_id: Camera ID
            rtsp_url: RTSP stream URL
            trigger_timestamp: Timestamp of the trigger event
            pre_trigger_seconds: Seconds before trigger to include
            post_trigger_seconds: Seconds after trigger to include

        Returns:
            ClipResult or None if recording failed
        """
        try:
            # Calculate clip boundaries
            start_time = trigger_timestamp.timestamp() - pre_trigger_seconds
            end_time = trigger_timestamp.timestamp() + post_trigger_seconds
            total_duration = pre_trigger_seconds + post_trigger_seconds

            # Generate filenames
            clip_filename = self._get_clip_filename(event_id, camera_id, trigger_timestamp)
            clip_path = os.path.join(self.temp_dir, clip_filename)
            thumbnail_filename = clip_filename.replace(".mp4", ".jpg")
            thumbnail_path = os.path.join(self.temp_dir, thumbnail_filename)

            # Record clip using ffmpeg
            success = await self._record_rtsp_clip(
                rtsp_url, clip_path, start_time, end_time
            )
            if not success:
                logger.error(f"Failed to record clip for event {event_id}")
                return None

            # Get clip metadata
            duration = self._get_duration(clip_path)
            file_size = self._get_file_size(clip_path)

            # Extract thumbnail from midpoint
            thumbnail_path = await self.extract_thumbnail(clip_path, duration / 2)

            # Upload to storage
            clip_url, thumbnail_url = await self.upload_to_storage(
                clip_path, thumbnail_path or "", event_id
            )

            # Save metadata to database
            clip_id = await self._save_clip_metadata(
                event_id=event_id,
                camera_id=camera_id,
                clip_url=clip_url,
                thumbnail_url=thumbnail_url,
                duration_sec=duration,
                file_size_bytes=file_size,
                start_timestamp=datetime.fromtimestamp(start_time),
                end_timestamp=datetime.fromtimestamp(end_time),
            )

            # Clean up temp files
            await self.cleanup_temp_files(clip_path, thumbnail_path or "")

            return ClipResult(
                clip_id=clip_id,
                event_id=event_id,
                clip_url=clip_url,
                thumbnail_url=thumbnail_url,
                duration_sec=duration,
                file_size_bytes=file_size,
                start_timestamp=datetime.fromtimestamp(start_time),
                end_timestamp=datetime.fromtimestamp(end_time),
            )

        except Exception as e:
            logger.error(f"Clip recording failed for event {event_id}: {e}")
            return None

    async def extract_thumbnail(self, clip_path: str,
                                 timestamp_seconds: float) -> Optional[str]:
        """Extract a thumbnail frame from the clip at given timestamp.

        Uses ffmpeg to extract a single frame.

        Args:
            clip_path: Path to the video clip
            timestamp_seconds: Timestamp in seconds to extract frame from

        Returns:
            Path to thumbnail file or None
        """
        try:
            thumbnail_path = clip_path.replace(".mp4", ".jpg")

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(timestamp_seconds),
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",
                thumbnail_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if os.path.exists(thumbnail_path):
                return thumbnail_path
            return None

        except Exception as e:
            logger.error(f"Thumbnail extraction failed: {e}")
            return None

    async def upload_to_storage(self, clip_path: str,
                                 thumbnail_path: str,
                                 event_id: int) -> tuple[str, str]:
        """Upload clip and thumbnail to Google Cloud Storage.

        Args:
            clip_path: Path to clip file
            thumbnail_path: Path to thumbnail file
            event_id: Associated event ID

        Returns:
            Tuple of (clip_url, thumbnail_url)
        """
        clip_url = ""
        thumbnail_url = ""

        try:
            # Upload clip
            clip_blob_name = f"clips/{event_id}/{os.path.basename(clip_path)}"
            clip_blob = self.storage.bucket.blob(clip_blob_name)
            clip_blob.upload_from_filename(clip_path)
            clip_url = clip_blob.public_url

            # Upload thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumb_blob_name = f"thumbnails/{event_id}/{os.path.basename(thumbnail_path)}"
                thumb_blob = self.storage.bucket.blob(thumb_blob_name)
                thumb_blob.upload_from_filename(thumbnail_path)
                thumbnail_url = thumb_blob.public_url

        except Exception as e:
            logger.error(f"Storage upload failed: {e}")

        return clip_url, thumbnail_url

    async def cleanup_temp_files(self, clip_path: str,
                                  thumbnail_path: str) -> None:
        """Delete temporary clip and thumbnail files.

        Args:
            clip_path: Path to clip file
            thumbnail_path: Path to thumbnail file
        """
        try:
            if os.path.exists(clip_path):
                os.remove(clip_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

    async def _record_rtsp_clip(self, rtsp_url: str, output_path: str,
                                 start_time: float, end_time: float) -> bool:
        """Record clip from RTSP stream using ffmpeg.

        Args:
            rtsp_url: RTSP stream URL
            output_path: Output file path
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            True if recording succeeded
        """
        duration = end_time - start_time

        cmd = [
            "ffmpeg", "-y",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"ffmpeg failed: {stderr.decode()}")
                return False

            return os.path.exists(output_path)

        except Exception as e:
            logger.error(f"RTSP recording failed: {e}")
            return False

    async def _save_clip_metadata(self, event_id: int, camera_id: str,
                                   clip_url: str, thumbnail_url: str,
                                   duration_sec: float, file_size_bytes: int,
                                   start_timestamp: datetime,
                                   end_timestamp: datetime) -> int:
        """Save clip metadata to database.

        Args:
            Various clip metadata fields

        Returns:
            Clip ID from database
        """
        # Placeholder - would insert into database
        return 1

    def _get_clip_filename(self, event_id: int,
                            camera_id: str,
                            timestamp: datetime) -> str:
        """Generate unique clip filename.

        Format: clips/{camera_id}/{date}/{event_id}_{timestamp}.mp4

        Args:
            event_id: Event ID
            camera_id: Camera ID
            timestamp: Trigger timestamp

        Returns:
            Formatted filename
        """
        date_str = timestamp.strftime("%Y%m%d")
        time_str = timestamp.strftime("%H%M%S")
        return f"clip_{camera_id}_{date_str}_{time_str}_event{event_id}.mp4"

    def _get_duration(self, clip_path: str) -> float:
        """Get video duration using ffprobe.

        Args:
            clip_path: Path to video file

        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                clip_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _get_file_size(self, clip_path: str) -> int:
        """Get file size in bytes.

        Args:
            clip_path: Path to file

        Returns:
            File size in bytes
        """
        try:
            return os.path.getsize(clip_path)
        except Exception:
            return 0


class ClipPlayer:
    """Serve video clips for playback.

    Provides signed URLs for clip playback, thumbnail access,
    and byte-range streaming support.
    """

    def __init__(self, storage_client, db_session_factory):
        """Initialize clip player.

        Args:
            storage_client: Google Cloud Storage client
            db_session_factory: SQLAlchemy async session factory
        """
        self.storage = storage_client
        self.db_session_factory = db_session_factory

    async def get_clip_url(self, clip_id: int,
                            user_id: str) -> Optional[str]:
        """Get signed URL for clip playback.

        Generates time-limited signed URL from GCS.

        Args:
            clip_id: Clip ID
            user_id: User ID for access control

        Returns:
            Signed URL string or None
        """
        try:
            # Generate signed URL with 1-hour expiry
            url = self.storage.bucket.blob(f"clips/{clip_id}/clip.mp4").generate_signed_url(
                version="v4",
                expiration=3600,
                method="GET",
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            return None

    async def get_clips_for_event(self, event_id: int,
                                   user_id: str) -> list[ClipResult]:
        """Get all clips for an event.

        Args:
            event_id: Event ID
            user_id: User ID for access control

        Returns:
            List of ClipResult
        """
        # Placeholder - would query database
        return []

    async def get_clip_thumbnail(self, clip_id: int,
                                  user_id: str) -> Optional[str]:
        """Get thumbnail URL for a clip.

        Args:
            clip_id: Clip ID
            user_id: User ID for access control

        Returns:
            Thumbnail URL string
        """
        try:
            url = self.storage.bucket.blob(
                f"thumbnails/{clip_id}/thumbnail.jpg"
            ).generate_signed_url(
                version="v4",
                expiration=3600,
                method="GET",
            )
            return url
        except Exception:
            return None

    async def stream_clip(self, clip_id: int, user_id: str,
                           range_header: Optional[str] = None) -> dict:
        """Stream clip with byte-range support for seeking.

        Args:
            clip_id: Clip ID
            user_id: User ID for access control
            range_header: HTTP Range header for byte-range requests

        Returns:
            Dict with data, content_type, content_length, content_range, status
        """
        # Placeholder - would fetch from GCS with byte-range support
        return {
            "data": b"",
            "content_type": "video/mp4",
            "content_length": 0,
            "content_range": "",
            "status": 200,
        }

    def _check_tier_access(self, tier: str) -> bool:
        """Check if tier has clip access.

        Args:
            tier: User tier ("free", "household", "business")

        Returns:
            True if tier has clip access
        """
        return tier in ("household", "business")

    def _get_max_clip_duration(self, tier: str) -> int:
        """Get max clip duration for tier.

        Args:
            tier: User tier

        Returns:
            Max clip duration in seconds
        """
        durations = {
            "free": 0,
            "household": 30,
            "business": 60,
        }
        return durations.get(tier, 0)
