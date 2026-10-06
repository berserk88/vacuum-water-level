"""Tests for waste empty detection logic.

Tests all priority paths for detecting waste tank emptying, including
the warning latch requirement to prevent false empties.
"""

import pytest
from custom_components.vacuum_water_level.detection import detect_waste_empty


class TestWasteEmptyDetection:
    """Tests for waste empty detection priority logic."""

    def test_empty_via_dirty_water_sensor_cleared_after_warning(self):
        """Test waste empty detected when sensor clears after a prior warning."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dirty_water_sensor_cleared"

    def test_no_empty_when_sensor_clear_but_no_prior_warning(self):
        """Test no empty when sensor is clear but no warning was latched."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=False,
        )
        assert detected is False
        assert source == "dirty_water_sensor"

    def test_no_empty_when_dirty_water_sensor_still_on(self):
        """Test no empty when dirty water sensor still indicates full."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=True,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is False
        assert source == "dirty_water_sensor"

    def test_empty_via_dock_error_cleared_after_warning(self):
        """Test waste empty detected when dock error clears after a prior warning."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=False,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dock_full_error_cleared"

    def test_no_empty_when_dock_error_clear_but_no_prior_warning(self):
        """Test no empty when dock error clear but no warning was latched."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=False,
            manual_empty=False,
            warning_was_latched=False,
        )
        assert detected is False
        assert source == "dock_error_sensor"

    def test_no_empty_when_dock_error_still_active(self):
        """Test no empty when dock error still active."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=True,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is False
        assert source == "dock_error_sensor"

    def test_empty_via_manual_button(self):
        """Test waste empty detected via manual button."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            manual_empty=True,
            warning_was_latched=False,
        )
        assert detected is True
        assert source == "manual_empty"

    def test_no_empty_when_nothing_configured(self):
        """Test no empty when nothing configured."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            manual_empty=False,
            warning_was_latched=False,
        )
        assert detected is False
        assert source == "none"

    def test_priority_dirty_water_sensor_over_dock_error(self):
        """Test that dirty water sensor takes priority over dock error."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=False,
            dock_error_state=True,
            manual_empty=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dirty_water_sensor_cleared"

    def test_priority_dock_error_over_manual(self):
        """Test that dock error takes priority over manual empty."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=False,
            manual_empty=True,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dock_full_error_cleared"

    def test_empty_via_manual_without_sensors(self):
        """Test manual empty works when no sensors are configured."""
        detected, source = detect_waste_empty(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            manual_empty=True,
            warning_was_latched=False,
        )
        assert detected is True
        assert source == "manual_empty"
