"""Build Verification Tests for VisionOS Connect Edge Agent.

These tests verify that all modules can be imported and their
core interfaces are correct. They run quickly and don't require
any external dependencies (no RTSP, no HTTP, no audio hardware).

Run these after every build to ensure the EXE will work.
"""

import importlib
import pkgutil
import sys
from typing import List

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Module Import Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModuleImports:
    """Verify all connect modules can be imported."""

    REQUIRED_MODULES = [
        "connect",
        "connect.config",
        "connect.camera.rtsp_reader",
        "connect.camera.frame_selector",
        "connect.camera.motion_detector",
        "connect.audio.audio_capture",
        "connect.transport.trigger_sender",
        "connect.buffer.local_queue",
    ]

    @pytest.mark.parametrize("module_name", REQUIRED_MODULES)
    def test_module_imports(self, module_name: str) -> None:
        """Test that each required module imports without error."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")

    def test_all_connect_modules_importable(self) -> None:
        """Test that every module in the connect package imports."""
        import connect

        failed = []
        for importer, modname, ispkg in pkgutil.walk_packages(
            connect.__path__, prefix="connect."
        ):
            # Skip tray_app — requires pystray which is only available in the built EXE
            if modname == "connect.ui.tray_app":
                continue
            try:
                importlib.import_module(modname)
            except ImportError as e:
                failed.append(f"{modname}: {e}")

        if failed:
            pytest.fail(f"Failed to import {len(failed)} modules:\n" + "\n".join(failed))


# ═══════════════════════════════════════════════════════════════════════════════
# Core Class Interface Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoreInterfaces:
    """Verify core classes have the expected interfaces."""

    def test_motion_detector_interface(self) -> None:
        """MotionDetector should have the expected methods."""
        from connect.camera.motion_detector import MotionDetector, MotionResult

        detector = MotionDetector()
        assert hasattr(detector, "detect")
        assert hasattr(detector, "set_roi")
        assert hasattr(detector, "reset_background")
        assert hasattr(detector, "get_motion_mask")
        assert hasattr(detector, "threshold")
        assert hasattr(detector, "min_area")

        # MotionResult dataclass
        mr = MotionResult(motion_detected=False, confidence=0.0, bounding_boxes=[], motion_area_pct=0.0)
        assert hasattr(mr, "motion_detected")
        assert hasattr(mr, "confidence")
        assert hasattr(mr, "bounding_boxes")
        assert hasattr(mr, "motion_area_pct")

    def test_rtsp_reader_interface(self) -> None:
        """RTSPReader should have the expected methods."""
        from connect.camera.rtsp_reader import RTSPReader, StreamInfo

        reader = RTSPReader("rtsp://test:554/stream", "cam-001")
        assert hasattr(reader, "connect")
        assert hasattr(reader, "read_frame")
        assert hasattr(reader, "reconnect")
        assert hasattr(reader, "release")
        assert hasattr(reader, "is_connected")
        assert hasattr(reader, "get_stream_info")
        assert hasattr(reader, "rtsp_url")
        assert hasattr(reader, "camera_id")

        # StreamInfo dataclass
        si = StreamInfo(width=0, height=0, fps=0.0, codec="", is_connected=False)
        assert hasattr(si, "width")
        assert hasattr(si, "height")
        assert hasattr(si, "fps")
        assert hasattr(si, "codec")
        assert hasattr(si, "is_connected")

    def test_trigger_sender_interface(self) -> None:
        """TriggerSender should have the expected methods."""
        from connect.transport.trigger_sender import TriggerSender, TriggerResponse

        sender = TriggerSender("https://api.test.com", "token")
        assert hasattr(sender, "send_frame_trigger")
        assert hasattr(sender, "send_audio_trigger")
        assert hasattr(sender, "check_health")
        assert hasattr(sender, "close")
        assert hasattr(sender, "api_base_url")
        assert hasattr(sender, "auth_token")

        # TriggerResponse dataclass
        tr = TriggerResponse(success=False, event_id=None, message="", status_code=0)
        assert hasattr(tr, "success")
        assert hasattr(tr, "event_id")
        assert hasattr(tr, "message")
        assert hasattr(tr, "status_code")

    def test_audio_capture_interface(self) -> None:
        """AudioCapture should have the expected methods."""
        from connect.audio.audio_capture import AudioCapture

        capture = AudioCapture()
        assert hasattr(capture, "start_stream")
        assert hasattr(capture, "read_chunk")
        assert hasattr(capture, "stop_stream")
        assert hasattr(capture, "is_streaming")

    def test_local_queue_interface(self) -> None:
        """LocalQueue should have the expected methods."""
        from connect.buffer.local_queue import LocalQueue

        queue = LocalQueue(db_path=":memory:")
        assert hasattr(queue, "enqueue")
        assert hasattr(queue, "dequeue_all")
        assert hasattr(queue, "flush_to_server")
        assert hasattr(queue, "count")
        assert hasattr(queue, "cleanup_expired")
        assert hasattr(queue, "close")
        queue.close()

    def test_frame_selector_interface(self) -> None:
        """Frame selector should have the expected functions."""
        from connect.camera.frame_selector import (
            _person_aspect_ratio,
            _score_frame,
            select_best_frame,
        )

        assert callable(select_best_frame)
        assert callable(_score_frame)
        assert callable(_person_aspect_ratio)


# ═══════════════════════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    """Verify configuration loading works."""

    def test_config_has_required_fields(self) -> None:
        """AppConfig should have the expected fields."""
        from connect.config import AppConfig

        config = AppConfig()
        assert hasattr(config, "api_key")
        assert hasattr(config, "camera_id")
        assert hasattr(config, "camera_name")
        assert hasattr(config, "rtsp_url")
        assert hasattr(config, "mode")
        assert hasattr(config, "backend_url")
        assert hasattr(config, "audio_enabled")
        assert hasattr(config, "auto_start")
        assert hasattr(config, "ignore_zones")
        assert hasattr(config, "motion_threshold")
        assert hasattr(config, "motion_min_area")
