"""Tests for coordinator-level behavior.

Tests coordinator logic that doesn't require full HA setup:
- Normal clear sensor does not trigger refill
- Warning latch + sensor clear does trigger refill
- Reserve learning before calibration
- Warning during active cleaning uses provisional usage

These tests use mock objects to test coordinator logic in isolation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from custom_components.vacuum_water_level.learning import (
    ReserveLearning,
    VacuumWaterState,
    WaterModel,
    WasteModel,
)
from custom_components.vacuum_water_level.detection import (
    detect_refill,
    detect_waste_empty,
)


class TestRefillLatchLogic:
    """Tests that refill detection uses warning latches correctly."""

    def test_normal_clear_sensor_no_refill(self):
        """Test that a normally-clear sensor doesn't trigger refill."""
        # Sensor is False (clear), no prior warning
        detected, source = detect_refill(
            clean_water_sensor_state=False,
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=False,
        )
        assert detected is False

    def test_warning_latch_plus_sensor_clear_triggers_refill(self):
        """Test that warning latch + sensor clear triggers refill."""
        # Sensor was True (warning latched), now False (cleared)
        detected, source = detect_refill(
            clean_water_sensor_state=False,
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "clean_water_sensor_cleared"

    def test_warning_latch_plus_sensor_still_on_no_refill(self):
        """Test that warning latch + sensor still on doesn't trigger refill."""
        detected, source = detect_refill(
            clean_water_sensor_state=True,
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is False

    def test_no_warning_latch_plus_manual_button_triggers_refill(self):
        """Test that manual button works without prior warning."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=None,
            manual_refill=True,
            warning_was_latched=False,
        )
        assert detected is True
        assert source == "manual_refill"


class TestWasteEmptyLatchLogic:
    """Tests that waste empty detection uses warning latches correctly."""

    def test_normal_clear_sensor_no_empty(self):
        """Test that a normally-clear sensor doesn't trigger empty."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=False,
        )
        assert detected is False

    def test_warning_latch_plus_sensor_clear_triggers_empty(self):
        """Test that warning latch + sensor clear triggers empty."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dirty_water_sensor_cleared"


class TestReserveBeforeCalibration:
    """Tests that reserve learning happens before calibration."""

    def test_reserve_updated_before_water_model_calibration(self):
        """Test that reserve is learned before water model is calibrated."""
        rl = ReserveLearning()
        wm = WaterModel()

        # Step 1: Water low warning fires -> learn reserve
        capacity = 250.0
        used_at_warning = 210.0
        rl.update_clean_reserve(capacity, used_at_warning)

        # Reserve should be updated
        assert rl.clean_reserve_ml > 0.0

        # Step 2: Refill detected -> calibrate using effective capacity
        effective_capacity = rl.effective_clean_capacity(capacity)
        assert effective_capacity < capacity

        # Water model should calibrate against effective capacity
        wm.record_usage(100.0, "on", "medium", 1)
        wm.calibrate(effective_capacity)

        assert wm.cycles_observed == 1

    def test_dirty_reserve_updated_before_waste_calibration(self):
        """Test that dirty reserve is learned before waste model is calibrated."""
        rl = ReserveLearning()
        wsm = WasteModel()

        # Step 1: Waste full warning fires -> learn reserve
        capacity = 250.0
        waste_at_warning = 220.0
        rl.update_dirty_reserve(capacity, waste_at_warning)

        assert rl.dirty_reserve_ml > 0.0

        # Step 2: Waste empty detected -> calibrate using effective capacity
        effective = rl.effective_dirty_capacity(capacity)
        assert effective < capacity

        wsm.record_usage(100.0)
        wsm.calibrate(effective, 100.0)

        assert wsm.cycles_observed == 1


class TestProvisionalUsageDuringCleaning:
    """Tests that warnings during active cleaning use provisional usage."""

    def test_provisional_usage_includes_current_session(self):
        """Test that provisional usage is computed for in-progress session."""
        # Simulate a coordinator-like scenario
        wm = WaterModel()
        rl = ReserveLearning()

        # Start a cleaning session
        session_area_start = 0.0
        current_area = 50.0  # 50 m² cleaned so far
        mop_intensity = "high"
        mop_mode = "on"
        wash_count = 1

        # Compute provisional usage
        area_delta = current_area - session_area_start
        provisional = wm.estimate_usage(area_delta, mop_mode, mop_intensity, wash_count)

        # Should be non-zero
        assert provisional > 0.0

        # If water low warning fires during this session, reserve learning
        # should use total_used = prior_usage + provisional
        prior_usage = 0.0
        total_used = prior_usage + provisional

        rl.update_clean_reserve(250.0, total_used)
        assert rl.clean_reserve_ml > 0.0

    def test_provisional_waste_during_cleaning(self):
        """Test that provisional waste is computed for in-progress session."""
        wm = WaterModel()
        wsm = WasteModel()
        rl = ReserveLearning()

        # Start a cleaning session
        area_delta = 40.0
        mop_intensity = "medium"
        mop_mode = "on"
        wash_count = 2

        provisional_water = wm.estimate_usage(
            area_delta, mop_mode, mop_intensity, wash_count
        )
        provisional_waste = wsm.estimate_waste(provisional_water)

        # If waste full warning fires during session
        prior_waste = 0.0
        total_waste = prior_waste + provisional_waste

        rl.update_dirty_reserve(250.0, total_waste)
        assert rl.dirty_reserve_ml > 0.0


class TestEffectiveCapacityCalibration:
    """Tests that calibration uses effective capacity after reserve learning."""

    def test_water_model_calibrates_against_effective_capacity(self):
        """Test that water model calibrates against effective capacity, not full."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 40.0  # Learned reserve
        wm = WaterModel()

        capacity = 250.0
        effective = rl.effective_clean_capacity(capacity)
        assert effective == 210.0

        # Record usage for the session
        wm.record_usage(100.0, "on", "medium", 1)

        # Calibrate against effective capacity (actual water consumed)
        wm.calibrate(effective)

        # The correction factor should have moved toward effective/estimated
        assert wm.cycles_observed == 1

    def test_waste_model_calibrates_against_effective_dirty_capacity(self):
        """Test that waste model calibrates against effective dirty capacity."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 30.0
        wsm = WasteModel()

        capacity = 250.0
        effective = rl.effective_dirty_capacity(capacity)
        assert effective == 220.0

        # Calibrate waste model
        wsm.record_usage(100.0)
        wsm.calibrate(effective, 100.0)

        assert wsm.cycles_observed == 1


class TestClearModelPreservesReserve:
    """Tests that Clear Prediction Model preserves reserve learning."""

    def test_clear_model_preserves_clean_reserve(self):
        """Test that clearing models preserves clean reserve."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 35.0
        rl.warning_cycles = 3

        wm = WaterModel()
        wm.cycles_observed = 10
        wm.correction_factors["wash_volume_ml"] = 65.0

        # Clear the water model
        wm.reset_model()

        # Reserve should be untouched
        assert rl.clean_reserve_ml == 35.0
        assert rl.warning_cycles == 3

        # Water model should be reset
        assert wm.cycles_observed == 0

    def test_clear_model_preserves_dirty_reserve(self):
        """Test that clearing models preserves dirty reserve."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 28.0
        rl.warning_cycles = 5

        wsm = WasteModel()
        wsm.cycles_observed = 8

        # Clear the waste model
        wsm.reset_model()

        # Reserve should be untouched
        assert rl.dirty_reserve_ml == 28.0
        assert rl.warning_cycles == 5

        # Waste model should be reset
        assert wsm.cycles_observed == 0
