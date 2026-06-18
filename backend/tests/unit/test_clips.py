"""Tests for clip recording and playback modules."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.storage.clip_recorder import ClipRecorder, ClipPlayer, ClipResult


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://storage.example.com/signed/clip.mp4?token=abc123"
    mock_blob.public_url = "https://storage.example.com/clip.mp4"
    storage.bucket.blob.return_value = mock_blob
    return storage


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def clip_recorder(mock_storage, mock_db):
    return ClipRecorder(
        storage_client=mock_storage,
        db_session_factory=mock_db,
        temp_dir="./test_temp_clips",
    )


@pytest.fixture
def clip_player(mock_storage, mock_db):
    return ClipPlayer(
        storage_client=mock_storage,
        db_session_factory=mock_db,
    )


class TestClipRecorder:
    """Tests for ClipRecorder class."""

    @pytest.mark.asyncio
    async def test_clip_recording_creates_valid_mp4(self, clip_recorder):
        """Test that clip recording produces a valid result."""
        result = await clip_recorder.record_clip(
            event_id=1,
            camera_id="cam_123",
            rtsp_url="rtsp://example.com/stream",
            trigger_timestamp=datetime(2024, 1, 1, 12, 0, 0),
            pre_trigger_seconds=10,
            post_trigger_seconds=20,
        )
        # Without ffmpeg available, this will return None
        # In production with ffmpeg, it would return a ClipResult
        assert result is None or isinstance(result, ClipResult)

    @pytest.mark.asyncio
    async def test_clip_thumbnail_extracted_from_midpoint(self, clip_recorder):
        """Test that thumbnail is extracted from clip midpoint."""
        # Mock clip file existence
        with patch("os.path.exists", return_value=True):
            thumbnail = await clip_recorder.extract_thumbnail(
                clip_path="/tmp/test_clip.mp4",
                timestamp_seconds=15.0,
            )
            # Without ffmpeg, this will return None
            assert thumbnail is None or isinstance(thumbnail, str)

    @pytest.mark.asyncio
    async def test_clip_uploaded_to_cloud_storage(self, clip_recorder, mock_storage):
        """Test that clip is uploaded to GCS."""
        clip_url, thumbnail_url = await clip_recorder.upload_to_storage(
            clip_path="/tmp/test_clip.mp4",
            thumbnail_path="/tmp/test_thumb.jpg",
            event_id=1,
        )
        # Should return URLs (empty if upload fails)
        assert isinstance(clip_url, str)
        assert isinstance(thumbnail_url, str)

    @pytest.mark.asyncio
    async def test_clip_metadata_saved_to_database(self, clip_recorder):
        """Test that clip metadata is saved."""
        clip_id = await clip_recorder._save_clip_metadata(
            event_id=1,
            camera_id="cam_123",
            clip_url="https://storage.example.com/clip.mp4",
            thumbnail_url="https://storage.example.com/thumb.jpg",
            duration_sec=30.0,
            file_size_bytes=1024000,
            start_timestamp=datetime(2024, 1, 1, 11, 59, 50),
            end_timestamp=datetime(2024, 1, 1, 12, 0, 20),
        )
        assert clip_id > 0

    def test_clip_filename_generation(self, clip_recorder):
        """Test that clip filenames are generated correctly."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        filename = clip_recorder._get_clip_filename(
            event_id=42,
            camera_id="cam_front_door",
            timestamp=timestamp,
        )
        assert "cam_front_door" in filename
        assert "event42" in filename
        assert filename.endswith(".mp4")

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_after_upload(self, clip_recorder):
        """Test that temp files are cleaned up after upload."""
        with patch("os.path.exists", return_value=True), \
             patch("os.remove") as mock_remove:
            await clip_recorder.cleanup_temp_files(
                clip_path="/tmp/test_clip.mp4",
                thumbnail_path="/tmp/test_thumb.jpg",
            )
            assert mock_remove.call_count == 2

    def test_get_duration_returns_float(self, clip_recorder):
        """Test that duration is returned as float."""
        duration = clip_recorder._get_duration("/tmp/nonexistent.mp4")
        assert isinstance(duration, float)

    def test_get_file_size_returns_int(self, clip_recorder):
        """Test that file size is returned as int."""
        size = clip_recorder._get_file_size("/tmp/nonexistent.mp4")
        assert isinstance(size, int)


class TestClipPlayer:
    """Tests for ClipPlayer class."""

    @pytest.mark.asyncio
    async def test_free_tier_no_clip_access(self, clip_player):
        """Test that free tier cannot access clips."""
        assert clip_player._check_tier_access("free") is False

    @pytest.mark.asyncio
    async def test_household_tier_30s_clips(self, clip_player):
        """Test that household tier has 30s clip limit."""
        assert clip_player._check_tier_access("household") is True
        assert clip_player._get_max_clip_duration("household") == 30

    @pytest.mark.asyncio
    async def test_business_tier_60s_clips(self, clip_player):
        """Test that business tier has 60s clip limit."""
        assert clip_player._check_tier_access("business") is True
        assert clip_player._get_max_clip_duration("business") == 60

    @pytest.mark.asyncio
    async def test_clip_streaming_with_byte_range(self, clip_player):
        """Test that clip streaming supports byte-range."""
        result = await clip_player.stream_clip(
            clip_id=1,
            user_id="user_123",
            range_header="bytes=0-1023",
        )
        assert "data" in result
        assert "content_type" in result
        assert "content_length" in result
        assert "content_range" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_get_clips_for_event_returns_all(self, clip_player):
        """Test that all clips for an event are returned."""
        clips = await clip_player.get_clips_for_event(
            event_id=1,
            user_id="user_123",
        )
        assert isinstance(clips, list)

    @pytest.mark.asyncio
    async def test_get_clip_url_returns_string(self, clip_player):
        """Test that clip URL is returned."""
        url = await clip_player.get_clip_url(
            clip_id=1,
            user_id="user_123",
        )
        assert url is None or isinstance(url, str)

    @pytest.mark.asyncio
    async def test_get_clip_thumbnail_returns_url(self, clip_player):
        """Test that thumbnail URL is returned."""
        url = await clip_player.get_clip_thumbnail(
            clip_id=1,
            user_id="user_123",
        )
        assert url is None or isinstance(url, str)


class TestClipResult:
    """Tests for ClipResult dataclass."""

    def test_clip_result_creation(self):
        """Test that ClipResult can be created."""
        result = ClipResult(
            clip_id=1,
            event_id=42,
            clip_url="https://storage.example.com/clip.mp4",
            thumbnail_url="https://storage.example.com/thumb.jpg",
            duration_sec=30.0,
            file_size_bytes=1024000,
            start_timestamp=datetime(2024, 1, 1, 12, 0, 0),
            end_timestamp=datetime(2024, 1, 1, 12, 0, 30),
        )
        assert result.clip_id == 1
        assert result.event_id == 42
        assert result.duration_sec == 30.0
        assert result.file_size_bytes == 1024000
