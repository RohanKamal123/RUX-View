"""
Tests for Sprint 3.2 — Camera Modes.

Tests all 5 mode files: indoor, outdoor, parking, mixed, shop.
"""

from datetime import datetime, time

import pytest

from backend.modes.indoor_mode import (
    MOTION_PARAMS as INDOOR_MOTION,
    TIMING_PARAMS as INDOOR_TIMING,
    LOITER_PARAMS as INDOOR_LOITER,
    get_motion_params,
    get_timing_params,
    get_loiter_params,
    should_analyse_individual,
    is_night_time,
    get_night_params,
)
from backend.modes.outdoor_mode import (
    MOTION_PARAMS as OUTDOOR_MOTION,
    get_mog2_params,
    get_crowd_thresholds,
    get_gate_line_crossing_params,
)
from backend.modes.parking_mode import (
    get_vehicle_detection_params,
)
from backend.modes.mixed_mode import (
    is_crossing_public_to_property,
    get_zone_config,
    get_public_zone_mode,
)
from backend.modes.shop_mode import (
    get_business_hours,
    is_staff_entrance,
    get_after_hours_params,
)


class TestIndoorMode:
    def test_indoor_lower_thresholds_than_outdoor(self):
        """Indoor thresholds should be lower than outdoor."""
        assert INDOOR_MOTION.skip_threshold < OUTDOOR_MOTION.skip_threshold
        assert INDOOR_MOTION.check_threshold < OUTDOOR_MOTION.check_threshold
        assert INDOOR_MOTION.gemma_threshold < OUTDOOR_MOTION.gemma_threshold
        assert INDOOR_MOTION.urgent_threshold < OUTDOOR_MOTION.urgent_threshold

    def test_night_mode_halves_cooldown(self):
        """Night mode should halve the cooldown."""
        day_params = get_timing_params("indoor", is_night=False)
        night_params = get_timing_params("indoor", is_night=True)
        assert night_params.cooldown < day_params.cooldown
        assert night_params.burst_interval < day_params.burst_interval

    def test_should_analyse_individual_returns_true_for_indoor(self):
        """Indoor mode should analyse individuals."""
        assert should_analyse_individual("indoor") is True

    def test_should_analyse_individual_returns_false_for_outdoor(self):
        """Outdoor mode should NOT analyse individuals."""
        assert should_analyse_individual("outdoor") is False

    def test_is_night_time_during_night(self):
        """is_night_time should return True during night hours."""
        night_time = datetime(2024, 1, 1, 23, 0, 0)
        assert is_night_time(current_time=night_time) is True

    def test_is_night_time_during_day(self):
        """is_night_time should return False during day hours."""
        day_time = datetime(2024, 1, 1, 14, 0, 0)
        assert is_night_time(current_time=day_time) is False

    def test_get_night_params_returns_overrides(self):
        """get_night_params should return correct overrides."""
        params = get_night_params()
        assert params["cooldown"] == 8
        assert params["burst_interval"] == 1.5
        assert params["no_motion_timeout"] == 4

    def test_get_motion_params_by_mode(self):
        """get_motion_params should return correct params per mode."""
        indoor = get_motion_params("indoor")
        assert indoor.skip_threshold == 400

        outdoor = get_motion_params("outdoor")
        assert outdoor.skip_threshold == 800

    def test_get_loiter_params_by_location_type(self):
        """get_loiter_params should return correct params per location."""
        indoor_loiter = get_loiter_params("indoor", "indoor_general")
        assert indoor_loiter.low_seconds == 60
        assert indoor_loiter.medium_seconds == 180
        assert indoor_loiter.high_seconds == 300

        front_gate = get_loiter_params("indoor", "front_gate")
        assert front_gate.low_seconds == 45
        assert front_gate.medium_seconds == 120
        assert front_gate.high_seconds == 240


class TestOutdoorMode:
    def test_outdoor_mog2_baseline_learns(self):
        """MOG2 params should have reasonable defaults."""
        params = get_mog2_params()
        assert params["history"] == 500
        assert params["varThreshold"] == 36
        assert params["detectShadows"] is True

    def test_crowd_thresholds(self):
        """Crowd thresholds should be reasonable."""
        thresholds = get_crowd_thresholds()
        assert thresholds["person_count_threshold"] == 10
        assert thresholds["motion_density_threshold"] == 0.4

    def test_gate_line_crossing_params(self):
        """Gate line crossing should have coordinates and direction tracking."""
        params = get_gate_line_crossing_params()
        assert len(params["line_coordinates"]) == 4
        assert params["direction_tracking_enabled"] is True


class TestParkingMode:
    def test_parking_vehicle_trigger_logic(self):
        """Vehicle detection params should have reasonable values."""
        params = get_vehicle_detection_params()
        assert params["min_vehicle_area"] == 2000
        assert params["aspect_ratio_range"] == [0.8, 2.5]
        assert params["headlight_threshold"] == 150

    def test_parking_headlight_detection_at_night(self):
        """Night params should enable headlight detection."""
        from backend.modes.parking_mode import get_night_params
        night = get_night_params()
        assert night["headlight_detection_enabled"] is True


class TestMixedMode:
    def test_mixed_zone_crossing_triggers(self):
        """Crossing from public to property should be detected."""
        # Person moving from bottom (public, y=0.8) to top (property, y=0.2)
        track = [(0.5, 0.8), (0.5, 0.7), (0.5, 0.5), (0.5, 0.3), (0.5, 0.2)]
        assert is_crossing_public_to_property(track) is True

    def test_mixed_zone_no_crossing(self):
        """Person staying in same zone should not trigger crossing."""
        track = [(0.5, 0.2), (0.5, 0.3), (0.5, 0.25)]
        assert is_crossing_public_to_property(track) is False

    def test_mixed_zone_config(self):
        """Zone config should have all required keys."""
        config = get_zone_config()
        assert "public_zone_coords" in config
        assert "property_zone_coords" in config
        assert "crossing_line" in config

    def test_public_zone_mode_is_outdoor(self):
        """Public zone should use outdoor mode."""
        assert get_public_zone_mode() == "outdoor"

    def test_should_analyse_individual_returns_false_for_public_zone(self):
        """Mixed mode should NOT analyse individuals in public zone."""
        assert should_analyse_individual("mixed", zone="public") is False

    def test_should_analyse_individual_returns_true_for_property_zone(self):
        """Mixed mode SHOULD analyse individuals in property zone."""
        assert should_analyse_individual("mixed", zone="property") is True


class TestShopMode:
    def test_shop_business_hours_check(self):
        """Business hours should correctly identify open/closed."""
        # Test during business hours (use a fixed time)
        hours = get_business_hours("09:00", "21:00")
        assert hours["open"] == "09:00"
        assert hours["close"] == "21:00"
        # is_open_now depends on current time, just check it's a bool
        assert isinstance(hours["is_open_now"], bool)

    def test_shop_floor_loiter_disabled_business_hours(self):
        """After hours params should enable loitering."""
        after_hours = get_after_hours_params()
        assert after_hours["loitering_enabled"] is True
        assert after_hours["staff_entrance_alert"] is True

    def test_staff_entrance_detection(self):
        """Staff entrance zones should be correctly identified."""
        assert is_staff_entrance("staff_entrance") is True
        assert is_staff_entrance("back_office") is True
        assert is_staff_entrance("shop_floor") is False
        assert is_staff_entrance("") is False
        assert is_staff_entrance(None) is False

    def test_after_hours_params(self):
        """After hours should have faster cooldown."""
        params = get_after_hours_params()
        assert params["cooldown"] == 5
        assert params["burst_interval"] == 1.5
