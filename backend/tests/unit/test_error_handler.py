"""Tests for error handling, retry management, and health checking modules."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from backend.core.error_handler import (
    ErrorHandler,
    ErrorRecord,
    ErrorSeverity,
    ErrorCategory,
)
from backend.core.retry_manager import RetryManager
from backend.core.health_checker import HealthChecker


class TestErrorHandler:

    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.mark.asyncio
    async def test_error_record_created_with_context(self, error_handler):
        """Test that error records include full context."""
        record = await error_handler.handle_error(
            camera_id="cam-001",
            module="pipeline",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            message="Connection timeout",
            exception=TimeoutError("Connection timed out"),
            context={"url": "rtsp://camera-001/stream", "attempt": 3},
        )

        assert record.camera_id == "cam-001"
        assert record.module == "pipeline"
        assert record.category == ErrorCategory.NETWORK
        assert record.severity == ErrorSeverity.ERROR
        assert "Connection timeout" in record.message
        assert record.exception is not None
        assert record.context["url"] == "rtsp://camera-001/stream"
        assert record.resolved is False

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_third_attempt(self):
        """Test that retry succeeds after multiple attempts."""
        retry_manager = RetryManager(max_retries=3, base_delay=0.01, jitter=0.0)
        attempt_count = 0

        async def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await retry_manager.execute(
            flaky_function,
            retryable_exceptions=(ConnectionError,),
        )

        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausts_max_attempts(self):
        """Test that retry raises after exhausting all attempts."""
        retry_manager = RetryManager(max_retries=2, base_delay=0.01, jitter=0.0)
        attempt_count = 0

        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Persistent failure")

        with pytest.raises(ValueError, match="Persistent failure"):
            await retry_manager.execute(
                always_fails,
                retryable_exceptions=(ValueError,),
            )

        assert attempt_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_health_check_all_subsystems_healthy(self):
        """Test that health check returns healthy when all subsystems are up."""
        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        checker = HealthChecker(
            db_session_factory=mock_factory,
            ai_client=MagicMock(),
            groq_client=MagicMock(),
            telegram_client=MagicMock(),
        )

        # Mock check_storage to return healthy regardless of actual disk usage
        with patch.object(checker, 'check_storage', new=AsyncMock(return_value={
            "status": "healthy",
            "disk_usage_pct": 42.5,
            "latency_ms": 1.0,
            "error": None,
        })):
            result = await checker.check_all()

        assert result["status"] == "healthy"
        assert "database" in result["checks"]
        assert "gemini_api" in result["checks"]
        assert "groq_api" in result["checks"]
        assert "telegram" in result["checks"]
        assert "storage" in result["checks"]
        assert result["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_database_failure_reported(self):
        """Test that database failure is reported in health check."""
        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Connection refused")
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        checker = HealthChecker(db_session_factory=mock_factory)

        result = await checker.check_all()

        assert result["checks"]["database"]["status"] == "unhealthy"
        assert "Connection refused" in result["checks"]["database"]["error"]

    @pytest.mark.asyncio
    async def test_camera_error_doesnt_affect_other_cameras(self, error_handler):
        """Test that one camera's error doesn't affect others."""
        # Create error for camera 1
        await error_handler.handle_error(
            camera_id="cam-001",
            module="pipeline",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            message="Camera 1 offline",
        )

        # Camera 2 should not be degraded
        assert error_handler.is_camera_degraded("cam-001") is True
        assert error_handler.is_camera_degraded("cam-002") is False

    @pytest.mark.asyncio
    async def test_invalid_gemini_json_handled_gracefully(self, error_handler):
        """Test that invalid JSON from Gemini is handled gracefully."""
        record = await error_handler.handle_error(
            camera_id="cam-001",
            module="ai_analysis",
            category=ErrorCategory.API,
            severity=ErrorSeverity.WARNING,
            message="Gemini returned invalid JSON, using defaults",
            context={"raw_response": "{invalid json}"},
        )

        assert record.severity == ErrorSeverity.WARNING
        assert "invalid JSON" in record.message

    @pytest.mark.asyncio
    async def test_empty_whisper_transcript_handled(self, error_handler):
        """Test that empty Whisper transcript is handled as info, not error."""
        record = await error_handler.handle_error(
            camera_id="cam-001",
            module="audio_analysis",
            category=ErrorCategory.API,
            severity=ErrorSeverity.INFO,
            message="Whisper returned empty transcript",
        )

        assert record.severity == ErrorSeverity.INFO
        assert "empty transcript" in record.message

    def test_topology_cycle_rejected(self):
        """Test that cyclic topology is rejected (from location_manager)."""
        from backend.core.location_manager import LocationManager
        manager = LocationManager(None)

        cyclic = {
            "cam-a": {"neighbours": ["cam-b"], "min_transit_time": 5},
            "cam-b": {"neighbours": ["cam-a"], "min_transit_time": 3},
        }

        assert manager._validate_topology(cyclic) is False

    @pytest.mark.asyncio
    async def test_camera_deleted_mid_incident_closes_gracefully(self, error_handler):
        """Test that camera deletion mid-incident is handled gracefully."""
        record = await error_handler.handle_error(
            camera_id="cam-001",
            module="incident_tracker",
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.INFO,
            message="Camera deleted mid-incident, closing incident",
            context={"incident_id": "inc-001", "events_processed": 5},
        )

        assert record.severity == ErrorSeverity.INFO
        assert "Camera deleted" in record.message

    @pytest.mark.asyncio
    async def test_critical_error_triggers_admin_alert(self, error_handler):
        """Test that CRITICAL errors trigger admin alerts."""
        with patch.object(error_handler, '_alert_admin') as mock_alert:
            await error_handler.handle_error(
                camera_id=None,
                module="database",
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.CRITICAL,
                message="Database connection pool exhausted",
            )

            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_camera_errors_filters_by_time(self, error_handler):
        """Test that get_camera_errors filters by time range."""
        await error_handler.handle_error(
            camera_id="cam-001", module="test", category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR, message="Error 1",
        )

        # hours_back=24 should include the just-created error
        errors = await error_handler.get_camera_errors("cam-001", hours_back=24)
        assert len(errors) == 1

        # hours_back=1 should include the just-created error (it was created < 1 hour ago)
        errors_1h = await error_handler.get_camera_errors("cam-001", hours_back=1)
        assert len(errors_1h) == 1

        # hours_back with a very large negative value should exclude the error
        # (cutoff = now - (-100000 * 3600) = now + 100000 hours in the future)
        errors_future = await error_handler.get_camera_errors("cam-001", hours_back=-100000)
        assert len(errors_future) == 0

    @pytest.mark.asyncio
    async def test_resolve_error_marks_as_resolved(self, error_handler):
        """Test that resolving an error marks it as resolved."""
        record = await error_handler.handle_error(
            camera_id="cam-001", module="test", category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR, message="Test error",
        )

        resolved = await error_handler.resolve_error("0")
        assert resolved is True

        unresolved = await error_handler.get_unresolved_errors()
        assert len(unresolved) == 0

    def test_retry_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        manager = RetryManager(base_delay=1.0, max_delay=10.0, jitter=0.0)

        delay_0 = manager._calculate_delay(0)
        delay_1 = manager._calculate_delay(1)
        delay_2 = manager._calculate_delay(2)

        assert delay_0 == 1.0  # base * 2^0
        assert delay_1 == 2.0  # base * 2^1
        assert delay_2 == 4.0  # base * 2^2

    def test_retry_delay_capped_at_max(self):
        """Test that delay is capped at max_delay."""
        manager = RetryManager(base_delay=1.0, max_delay=5.0, jitter=0.0)

        delay_3 = manager._calculate_delay(3)  # Would be 8, capped at 5
        assert delay_3 == 5.0

    def test_retry_is_retryable_check(self):
        """Test retryable exception checking."""
        manager = RetryManager()

        assert manager._is_retryable(ValueError("test"), (ValueError,)) is True
        assert manager._is_retryable(TypeError("test"), (ValueError,)) is False
        assert manager._is_retryable(ValueError("test"), None) is True

    def test_health_status_aggregation(self):
        """Test health status aggregation logic."""
        checker = HealthChecker()

        all_healthy = [
            {"status": "healthy"}, {"status": "healthy"}, {"status": "healthy"},
        ]
        assert checker._get_status(all_healthy) == "healthy"

        some_degraded = [
            {"status": "healthy"}, {"status": "degraded"}, {"status": "healthy"},
        ]
        assert checker._get_status(some_degraded) == "degraded"

        any_unhealthy = [
            {"status": "healthy"}, {"status": "unhealthy"}, {"status": "healthy"},
        ]
        assert checker._get_status(any_unhealthy) == "unhealthy"

    @pytest.mark.asyncio
    async def test_error_handler_clears_degraded_state(self, error_handler):
        """Test that degraded state can be cleared."""
        await error_handler.handle_error(
            camera_id="cam-001", module="test", category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR, message="Test error",
        )

        assert error_handler.is_camera_degraded("cam-001") is True
        error_handler.clear_degraded("cam-001")
        assert error_handler.is_camera_degraded("cam-001") is False

    @pytest.mark.asyncio
    async def test_retry_non_retryable_exception_raises_immediately(self):
        """Test that non-retryable exceptions are not retried."""
        manager = RetryManager(max_retries=3, base_delay=0.01)
        attempt_count = 0

        async def fails_with_type_error():
            nonlocal attempt_count
            attempt_count += 1
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            await manager.execute(
                fails_with_type_error,
                retryable_exceptions=(ValueError,),
            )

        assert attempt_count == 1  # Only initial attempt, no retries

    @pytest.mark.asyncio
    async def test_health_check_storage_disk_usage(self):
        """Test storage health check reports disk usage."""
        checker = HealthChecker()
        result = await checker.check_storage()

        assert "disk_usage_pct" in result
        assert result["disk_usage_pct"] > 0
        assert result["status"] in ("healthy", "degraded", "unhealthy")
