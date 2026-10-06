"""Tests for binary sensor state transitions.

Tests the water low and waste tank full binary sensor detection logic,
including transitions between states.
"""

import pytest
from custom_components.vacuum_water_level.detection import (
    detect_water_low,
    detect_waste_full,
)


class TestWaterLowDetection:
    """Tests for water low binary sensor detection."""

    def test_water_low_via_clean_water_sensor(self):
        """Test water low detected via clean water box sensor."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=True,
            dock_error_state=None,
            predicted_remaining_pct=50.0,
            threshold_pct=15.0,
        )
        assert is_low is True
        assert source == "clean_water_sensor"

    def test_water_not_low_via_clean_water_sensor(self):
        """Test water not low via clean water box sensor."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=False,
            dock_error_state=None,
            predicted_remaining_pct=5.0,
            threshold_pct=15.0,
        )
        assert is_low is False
        assert source == "clean_water_sensor"

    def test_water_low_via_dock_error(self):
        """Test water low detected via dock error sensor (no water sensor)."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=True,
            predicted_remaining_pct=50.0,
            threshold_pct=15.0,
        )
        assert is_low is True
        assert source == "dock_error_sensor"

    def test_water_low_via_prediction(self):
        """Test water low detected via prediction model."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=None,
            predicted_remaining_pct=10.0,
            threshold_pct=15.0,
        )
        assert is_low is True
        assert source == "prediction_model"

    def test_water_not_low_via_prediction(self):
        """Test water not low via prediction model."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=None,
            predicted_remaining_pct=50.0,
            threshold_pct=15.0,
        )
        assert is_low is False
        assert source == "prediction_model"

    def test_water_low_at_exact_threshold(self):
        """Test water low at exact threshold boundary."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=None,
            predicted_remaining_pct=15.0,
            threshold_pct=15.0,
        )
        assert is_low is True  # <= threshold means low

    def test_water_low_priority_sensor_over_prediction(self):
        """Test that clean water sensor takes priority over prediction."""
        is_low, source = detect_water_low(
            clean_water_sensor_state=False,  # Sensor says not low
            dock_error_state=None,
            predicted_remaining_pct=5.0,  # Prediction says low
            threshold_pct=15.0,
        )
        assert is_low is False
        assert source == "clean_water_sensor"

    def test_water_low_transition_from_not_low_to_low(self):
        """Test transition from not low to low via prediction."""
        # First check: not low
        is_low_1, _ = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=None,
            predicted_remaining_pct=20.0,
            threshold_pct=15.0,
        )
        assert is_low_1 is False

        # Second check: now low (water was consumed)
        is_low_2, _ = detect_water_low(
            clean_water_sensor_state=None,
            dock_error_state=None,
            predicted_remaining_pct=10.0,
            threshold_pct=15.0,
        )
        assert is_low_2 is True

    def test_water_low_transition_from_low_to_not_low(self):
        """Test transition from low to not low (refill)."""
        # First: low via sensor
        is_low_1, _ = detect_water_low(
            clean_water_sensor_state=True,
            dock_error_state=None,
            predicted_remaining_pct=5.0,
            threshold_pct=15.0,
        )
        assert is_low_1 is True

        # After refill: sensor clears
        is_low_2, _ = detect_water_low(
            clean_water_sensor_state=False,
            dock_error_state=None,
            predicted_remaining_pct=100.0,
            threshold_pct=15.0,
        )
        assert is_low_2 is False


class TestWasteFullDetection:
    """Tests for waste tank full binary sensor detection."""

    def test_waste_full_via_dirty_water_sensor(self):
        """Test waste full detected via dirty water box sensor."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=True,
            dock_error_state=None,
            predicted_waste_pct=50.0,
            threshold_pct=85.0,
        )
        assert is_full is True
        assert source == "dirty_water_sensor"

    def test_waste_not_full_via_dirty_water_sensor(self):
        """Test waste not full via dirty water box sensor."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            predicted_waste_pct=95.0,
            threshold_pct=85.0,
        )
        assert is_full is False
        assert source == "dirty_water_sensor"

    def test_waste_full_via_dock_error(self):
        """Test waste full detected via dock error sensor."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=True,
            predicted_waste_pct=50.0,
            threshold_pct=85.0,
        )
        assert is_full is True
        assert source == "dock_error_sensor"

    def test_waste_full_via_prediction(self):
        """Test waste full detected via prediction model."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            predicted_waste_pct=90.0,
            threshold_pct=85.0,
        )
        assert is_full is True
        assert source == "prediction_model"

    def test_waste_not_full_via_prediction(self):
        """Test waste not full via prediction model."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            predicted_waste_pct=50.0,
            threshold_pct=85.0,
        )
        assert is_full is False
        assert source == "prediction_model"

    def test_waste_full_at_exact_threshold(self):
        """Test waste full at exact threshold boundary."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            predicted_waste_pct=85.0,
            threshold_pct=85.0,
        )
        assert is_full is True  # >= threshold means full

    def test_waste_full_priority_sensor_over_prediction(self):
        """Test that dirty water sensor takes priority over prediction."""
        is_full, source = detect_waste_full(
            dirty_water_sensor_state=False,  # Sensor says not full
            dock_error_state=None,
            predicted_waste_pct=95.0,  # Prediction says full
            threshold_pct=85.0,
        )
        assert is_full is False
        assert source == "dirty_water_sensor"

    def test_waste_full_transition_not_full_to_full(self):
        """Test transition from not full to full via prediction."""
        is_full_1, _ = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            predicted_waste_pct=50.0,
            threshold_pct=85.0,
        )
        assert is_full_1 is False

        is_full_2, _ = detect_waste_full(
            dirty_water_sensor_state=None,
            dock_error_state=None,
            predicted_waste_pct=90.0,
            threshold_pct=85.0,
        )
        assert is_full_2 is True

    def test_waste_full_transition_full_to_not_full(self):
        """Test transition from full to not full (empty)."""
        is_full_1, _ = detect_waste_full(
            dirty_water_sensor_state=True,
            dock_error_state=None,
            predicted_waste_pct=95.0,
            threshold_pct=85.0,
        )
        assert is_full_1 is True

        is_full_2, _ = detect_waste_full(
            dirty_water_sensor_state=False,
            dock_error_state=None,
            predicted_waste_pct=5.0,
            threshold_pct=85.0,
        )
        assert is_full_2 is False
