"""Tests for refill detection logic.

Tests all priority paths for detecting water tank refills, including
the warning latch requirement to prevent false refills.
"""

import pytest
from custom_components.vacuum_water_level.detection import detect_refill


class TestRefillDetection:
    """Tests for refill detection priority logic."""

    def test_refill_via_clean_water_sensor_cleared_after_warning(self):
        """Test refill detected when sensor clears after a prior warning."""
        detected, source = detect_refill(
            clean_water_sensor_state=False,  # Sensor cleared
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "clean_water_sensor_cleared"

    def test_no_refill_when_sensor_clear_but_no_prior_warning(self):
        """Test no refill when sensor is clear but no warning was latched."""
        detected, source = detect_refill(
            clean_water_sensor_state=False,  # Sensor is clear
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=False,  # No prior warning
        )
        assert detected is False
        assert source == "clean_water_sensor"

    def test_no_refill_when_clean_water_sensor_still_on(self):
        """Test no refill when clean water sensor still indicates low."""
        detected, source = detect_refill(
            clean_water_sensor_state=True,
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is False
        assert source == "clean_water_sensor"

    def test_refill_via_dock_error_cleared_after_warning(self):
        """Test refill detected when dock error clears after a prior warning."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=False,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dock_error_cleared"

    def test_no_refill_when_dock_error_clear_but_no_prior_warning(self):
        """Test no refill when dock error clear but no warning was latched."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=False,
            manual_refill=False,
            warning_was_latched=False,
        )
        assert detected is False
        assert source == "dock_error_sensor"

    def test_no_refill_when_dock_error_still_active(self):
        """Test no refill when dock error still active."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=True,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is False
        assert source == "dock_error_sensor"

    def test_refill_via_manual_button(self):
        """Test refill detected via manual button."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=None,
            manual_refill=True,
            warning_was_latched=False,
        )
        assert detected is True
        assert source == "manual_refill"

    def test_no_refill_when_nothing_configured(self):
        """Test no refill when nothing is configured and no manual press."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=None,
            manual_refill=False,
            warning_was_latched=False,
        )
        assert detected is False
        assert source == "none"

    def test_priority_clean_water_sensor_over_dock_error(self):
        """Test that clean water sensor takes priority over dock error."""
        detected, source = detect_refill(
            clean_water_sensor_state=False,
            dock_error_state=True,
            manual_refill=False,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "clean_water_sensor_cleared"

    def test_priority_dock_error_over_manual(self):
        """Test that dock error takes priority over manual refill."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=False,
            manual_refill=True,
            warning_was_latched=True,
        )
        assert detected is True
        assert source == "dock_error_cleared"

    def test_refill_via_manual_without_sensors(self):
        """Test manual refill works when no sensors are configured."""
        detected, source = detect_refill(
            clean_water_sensor_state=None,
            dock_error_state=None,
            manual_refill=True,
            warning_was_latched=False,
        )
        assert detected is True
        assert source == "manual_refill"
