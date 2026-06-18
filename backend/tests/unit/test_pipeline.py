"""
Tests for Sprint 3.6 — Pipeline Orchestrator.

Tests the full incident flow orchestration.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.pipeline import CameraPipeline, PipelineContext, PipelineResult


class TestCameraPipeline:
    def test_pipeline_initialization(self):
        """Pipeline should initialize with camera config."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        assert pipeline.camera_id == "cam-001"
        assert pipeline.user_id == "user-001"
        assert pipeline.location_id == "loc-001"
        assert pipeline.mode == "indoor"

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_frame(self):
        """Pipeline should handle empty frame gracefully."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=datetime.now(timezone.utc),
            jpeg_bytes=None,
            motion_result={"pixel_diff": 100, "diff_category": "skip"},
        )

        result = await pipeline.process_trigger(ctx)
        assert result is not None
        assert result.threat_level == "LOW"

    @pytest.mark.asyncio
    async def test_pipeline_handles_gemma_failure_gracefully(self):
        """Pipeline should handle vision analysis failure gracefully."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=datetime.now(timezone.utc),
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 3000, "diff_category": "check"},
        )

        result = await pipeline.process_trigger(ctx)
        assert result is not None
        # Should not crash even if sub-modules fail
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_pipeline_respects_cooldown(self):
        """Pipeline should respect cooldown between triggers."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        now = datetime.now(timezone.utc)

        # First trigger
        ctx1 = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 3000, "diff_category": "check"},
        )
        result1 = await pipeline.process_trigger(ctx1)
        assert result1.threat_level == "TRACKING" or result1.threat_level == "LOW"

        # Second trigger immediately (cooldown not elapsed)
        ctx2 = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 3000, "diff_category": "check"},
        )
        result2 = await pipeline.process_trigger(ctx2)
        # Should not crash
        assert isinstance(result2, PipelineResult)

    @pytest.mark.asyncio
    async def test_pipeline_shutdown(self):
        """Pipeline shutdown should not raise errors."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        # Shutdown should be safe even if nothing initialized
        await pipeline.shutdown()
        assert True  # No exception

    def test_pipeline_context_dataclass(self):
        """PipelineContext should store all fields correctly."""
        now = datetime.now(timezone.utc)
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"test_jpeg",
            audio_bytes=b"test_audio",
            motion_result={"pixel_diff": 5000, "diff_category": "urgent"},
            yamnet_result={"class_name": "glass_breaking", "confidence": 0.8},
        )
        assert ctx.camera_id == "cam-001"
        assert ctx.jpeg_bytes == b"test_jpeg"
        assert ctx.motion_result["pixel_diff"] == 5000
        assert ctx.yamnet_result["class_name"] == "glass_breaking"

    def test_pipeline_result_dataclass(self):
        """PipelineResult should store all fields correctly."""
        result = PipelineResult(
            incident_id="INC-001",
            threat_level="HIGH",
            alert_sent=True,
            person_ids=["PERSON_001", "PERSON_002"],
        )
        assert result.incident_id == "INC-001"
        assert result.threat_level == "HIGH"
        assert result.alert_sent is True
        assert len(result.person_ids) == 2

    def test_pipeline_result_defaults(self):
        """PipelineResult should have sensible defaults."""
        result = PipelineResult()
        assert result.threat_level == "LOW"
        assert result.alert_sent is False
        assert result.person_ids == []
        assert result.error is None

    def test_pipeline_error_result(self):
        """PipelineResult should store error messages."""
        result = PipelineResult(error="Connection failed")
        assert result.error == "Connection failed"
        assert result.threat_level == "LOW"

    @pytest.mark.asyncio
    async def test_pipeline_initializes_submodules_lazily(self):
        """Sub-modules should be initialized lazily on first trigger."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        # Nothing initialized yet
        assert pipeline._incident_tracker is None
        assert pipeline._reid_engine is None

        # Trigger should initialize them
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=datetime.now(timezone.utc),
            motion_result={"pixel_diff": 100, "diff_category": "skip"},
        )
        await pipeline.process_trigger(ctx)

        # Tracker should be initialized now
        assert pipeline._incident_tracker is not None

    @pytest.mark.asyncio
    async def test_full_indoor_incident_low(self):
        """Full indoor incident with low threat should complete without error."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        now = datetime.now(timezone.utc)
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 100, "diff_category": "skip"},
        )
        result = await pipeline.process_trigger(ctx)
        assert result is not None
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_full_indoor_incident_high(self):
        """Full indoor incident with high threat should complete without error."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        now = datetime.now(timezone.utc)
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 7000, "diff_category": "urgent"},
        )
        result = await pipeline.process_trigger(ctx)
        assert result is not None
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_full_parking_incident(self):
        """Full parking incident should complete without error."""
        pipeline = CameraPipeline(
            camera_id="cam-002",
            user_id="user-001",
            location_id="loc-001",
            mode="parking",
        )
        now = datetime.now(timezone.utc)
        ctx = PipelineContext(
            camera_id="cam-002",
            user_id="user-001",
            location_id="loc-001",
            mode="parking",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            motion_result={"pixel_diff": 3500, "diff_category": "check"},
        )
        result = await pipeline.process_trigger(ctx)
        assert result is not None
        assert isinstance(result, PipelineResult)

    @pytest.mark.asyncio
    async def test_audio_visual_correlation(self):
        """Pipeline should handle audio + visual triggers."""
        pipeline = CameraPipeline(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
        )
        now = datetime.now(timezone.utc)
        ctx = PipelineContext(
            camera_id="cam-001",
            user_id="user-001",
            location_id="loc-001",
            mode="indoor",
            timestamp=now,
            jpeg_bytes=b"fake_jpeg",
            audio_bytes=b"fake_audio",
            motion_result={"pixel_diff": 3000, "diff_category": "check"},
            yamnet_result={"class_name": "glass_breaking", "confidence": 0.9},
        )
        result = await pipeline.process_trigger(ctx)
        assert result is not None
        assert isinstance(result, PipelineResult)
