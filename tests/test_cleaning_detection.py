"""Tests for cleaning state detection priority.

Tests that the priority-based cleaning detection correctly follows:
    1. Dedicated cleaning binary sensor
    2. Status sensor
    3. Vacuum state
    4. Fallback
"""

import pytest
from custom_components.vacuum_water_level.detection import (
    detect_cleaning,
    detect_mop_washing,
)


class TestCleaningDetectionPriority:
    """Tests for cleaning state detection priority order."""

    def test_priority_1_cleaning_binary_sensor_true(self):
        """Test cleaning detected via dedicated binary sensor (True)."""
        result = detect_cleaning(
            cleaning_entity_state=True,
            status_entity_value="charging",
            vacuum_state="docked",
        )
        assert result is True

    def test_priority_1_cleaning_binary_sensor_false(self):
        """Test cleaning not detected via dedicated binary sensor (False)."""
        result = detect_cleaning(
            cleaning_entity_state=False,
            status_entity_value="cleaning",
            vacuum_state="cleaning",
        )
        assert result is False

    def test_priority_2_status_sensor(self):
        """Test cleaning detected via status sensor when no binary sensor."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value="cleaning",
            vacuum_state="docked",
        )
        assert result is True

    def test_priority_2_status_sensor_mopping(self):
        """Test cleaning detected via status sensor 'mopping'."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value="mopping",
            vacuum_state="docked",
        )
        assert result is True

    def test_priority_2_status_sensor_not_cleaning(self):
        """Test cleaning not detected via status sensor 'charging'."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value="charging",
            vacuum_state="docked",
        )
        assert result is False

    def test_priority_3_vacuum_state(self):
        """Test cleaning detected via vacuum state when no binary/status."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value=None,
            vacuum_state="cleaning",
        )
        assert result is True

    def test_priority_3_vacuum_state_docked(self):
        """Test cleaning not detected via vacuum state 'docked'."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value=None,
            vacuum_state="docked",
        )
        assert result is False

    def test_priority_4_fallback(self):
        """Test fallback returns False when nothing is configured."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value=None,
            vacuum_state=None,
        )
        assert result is False

    def test_priority_order_binary_over_status(self):
        """Test that binary sensor takes priority over status."""
        result = detect_cleaning(
            cleaning_entity_state=False,  # Binary sensor says not cleaning
            status_entity_value="cleaning",  # Status says cleaning
            vacuum_state="cleaning",  # Vacuum says cleaning
        )
        assert result is False  # Binary sensor wins

    def test_priority_order_status_over_vacuum(self):
        """Test that status sensor takes priority over vacuum state."""
        result = detect_cleaning(
            cleaning_entity_state=None,
            status_entity_value="charging",  # Status says not cleaning
            vacuum_state="cleaning",  # Vacuum says cleaning
        )
        assert result is False  # Status sensor wins


class TestMopWashingDetection:
    """Tests for mop washing detection."""

    def test_washing_detected_via_status(self):
        """Test mop washing detected via status sensor."""
        result = detect_mop_washing(
            status_entity_value="washing",
            vacuum_state=None,
        )
        assert result is True

    def test_washing_detected_via_vacuum_state(self):
        """Test mop washing detected via vacuum state."""
        result = detect_mop_washing(
            status_entity_value=None,
            vacuum_state="mop_washing",
        )
        assert result is True

    def test_washing_not_detected_for_cleaning(self):
        """Test that 'cleaning' status doesn't trigger washing detection."""
        result = detect_mop_washing(
            status_entity_value="cleaning",
            vacuum_state=None,
        )
        assert result is False

    def test_washing_not_detected_for_none(self):
        """Test that None doesn't trigger washing detection."""
        result = detect_mop_washing(
            status_entity_value=None,
            vacuum_state=None,
        )
        assert result is False

    def test_washing_detected_status_wash_keyword(self):
        """Test washing detected when 'wash' is in status."""
        result = detect_mop_washing(
            status_entity_value="auto_washing",
            vacuum_state=None,
        )
        assert result is True
