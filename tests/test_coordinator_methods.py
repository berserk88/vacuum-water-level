"""Tests for coordinator-level behavior with mocked coordinator.

Tests the actual coordinator methods by instantiating a coordinator with
mocked storage and config, then calling methods directly.
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


def _make_coordinator(mock_hass, mock_config_entry, mock_storage):
    """Create a coordinator with mocked dependencies."""
    from custom_components.vacuum_water_level.coordinator import (
        VacuumWaterLevelCoordinator,
    )

    # Patch async_track_state_change_event to avoid HA event loop
    with patch(
        "custom_components.vacuum_water_level.coordinator.async_track_state_change_event",
        return_value=MagicMock(),
    ):
        coordinator = VacuumWaterLevelCoordinator(
            mock_hass, mock_config_entry, mock_storage
        )
    return coordinator


class TestReserveLearningSourceFilter:
    """Tests that reserve learning only happens from real sensor sources."""

    def test_reserve_not_updated_from_prediction(self, mock_hass, mock_config_entry, mock_storage):
        """Test that reserve is NOT updated when source is prediction_model."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        # Set up: prediction says water is low, no real sensor
        coord._cached_clean_water_sensor = None
        coord._cached_dock_error_raw = None
        coord.state.water_used_since_refill_ml = 100.0
        coord.state.clean_warning_latched = False

        # Mock get_water_low to return prediction source
        with patch.object(coord, "get_water_low", return_value=(True, "prediction_model")):
            coord._check_water_low_warning()

        # Warning should be latched
        assert coord.state.clean_warning_latched is True
        # Reserve should NOT be updated (still 0)
        assert coord.reserve.clean_reserve_ml == 0.0

    def test_reserve_updated_from_clean_sensor(self, mock_hass, mock_config_entry, mock_storage):
        """Test that reserve IS updated when source is clean_water_sensor."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_clean_water_sensor = True
        coord.state.water_used_since_refill_ml = 200.0
        coord.state.clean_warning_latched = False

        with patch.object(coord, "get_water_low", return_value=(True, "clean_water_sensor")):
            coord._check_water_low_warning()

        assert coord.state.clean_warning_latched is True
        # Reserve should be updated
        assert coord.reserve.clean_reserve_ml > 0.0

    def test_reserve_updated_from_dock_error(self, mock_hass, mock_config_entry, mock_storage):
        """Test that reserve IS updated when source is dock_error_sensor."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dock_error_raw = "clean water empty"
        coord.state.water_used_since_refill_ml = 180.0
        coord.state.clean_warning_latched = False

        with patch.object(coord, "get_water_low", return_value=(True, "dock_error_sensor")):
            coord._check_water_low_warning()

        assert coord.state.clean_warning_latched is True
        assert coord.reserve.clean_reserve_ml > 0.0

    def test_dirty_reserve_not_updated_from_prediction(self, mock_hass, mock_config_entry, mock_storage):
        """Test that dirty reserve is NOT updated from prediction."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dirty_water_sensor = None
        coord._cached_dock_error_raw = None
        coord.state.waste_collected_ml = 150.0
        coord.state.dirty_warning_latched = False

        with patch.object(coord, "get_waste_full", return_value=(True, "prediction_model")):
            coord._check_waste_full_warning()

        assert coord.state.dirty_warning_latched is True
        assert coord.reserve.dirty_reserve_ml == 0.0

    def test_dirty_reserve_updated_from_dirty_sensor(self, mock_hass, mock_config_entry, mock_storage):
        """Test that dirty reserve IS updated from dirty water sensor."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dirty_water_sensor = True
        coord.state.waste_collected_ml = 200.0
        coord.state.dirty_warning_latched = False

        with patch.object(coord, "get_waste_full", return_value=(True, "dirty_water_sensor")):
            coord._check_waste_full_warning()

        assert coord.state.dirty_warning_latched is True
        assert coord.reserve.dirty_reserve_ml > 0.0


class TestRefillDetectionInCoordinator:
    """Tests for coordinator refill detection with latches."""

    def test_no_refill_when_sensor_clear_no_latch(self, mock_hass, mock_config_entry, mock_storage):
        """Test no refill when sensor is clear but no prior warning."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_clean_water_sensor = False
        coord.state.clean_warning_latched = False
        coord.state.water_used_since_refill_ml = 100.0

        coord._check_refill()

        # Water used should not be reset
        assert coord.state.water_used_since_refill_ml == 100.0

    def test_refill_when_latch_and_sensor_clear(self, mock_hass, mock_config_entry, mock_storage):
        """Test refill triggered when warning was latched and sensor clears."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_clean_water_sensor = False
        coord.state.clean_warning_latched = True
        coord.state.water_used_since_refill_ml = 200.0

        coord._check_refill()

        # Water should be reset
        assert coord.state.water_used_since_refill_ml == 0.0
        assert coord.state.clean_warning_latched is False
        assert coord.state.last_refill is not None

    def test_no_refill_when_sensor_still_on(self, mock_hass, mock_config_entry, mock_storage):
        """Test no refill when sensor still indicates low."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_clean_water_sensor = True
        coord.state.clean_warning_latched = True
        coord.state.water_used_since_refill_ml = 200.0

        coord._check_refill()

        assert coord.state.water_used_since_refill_ml == 200.0


class TestRefillDuringActiveCleaning:
    """Tests that refill during active cleaning uses checkpointed usage."""

    def test_refill_during_cleaning_checkpoints_session(self, mock_hass, mock_config_entry, mock_storage):
        """Test that refill during active cleaning includes provisional usage."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        # Set up: cleaning in progress, sensor cleared, warning latched
        coord._cached_clean_water_sensor = False
        coord.state.clean_warning_latched = True
        coord.state.cleaning_in_progress = True
        coord.state.session_checkpointed = False
        coord.state.water_used_since_refill_ml = 0.0  # No completed sessions

        # Mock provisional usage
        coord._cached_area = 50.0
        coord._session_area_start = 0.0
        coord._cached_mop_mode = "on"
        coord._cached_mop_intensity = "medium"
        coord._session_wash_count = 1

        coord._check_refill()

        # After checkpoint, water_used should include provisional
        assert coord.state.water_used_since_refill_ml > 0.0
        # Session should be checkpointed
        assert coord.state.session_checkpointed is True
        # Warning latch should be cleared
        assert coord.state.clean_warning_latched is False

    def test_checkpotted_session_not_double_counted(self, mock_hass, mock_config_entry, mock_storage):
        """Test that a checkpointed session isn't counted again when it ends."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        # Session already checkpointed
        coord.state.cleaning_in_progress = True
        coord.state.session_checkpointed = True
        coord.state.water_used_since_refill_ml = 100.0  # From checkpoint

        # Simulate session ending
        coord._cached_area = 50.0
        coord._session_area_start = 0.0
        coord._cached_mop_mode = "on"
        coord._cached_mop_intensity = "medium"
        coord._session_wash_count = 1

        # Process cleaning cycle - should not double count
        # We need to simulate cleaning ending
        with patch.object(coord, "_is_cleaning", return_value=False):
            coord._process_cleaning_cycle()

        # Water used should still be 100 (not doubled)
        assert coord.state.water_used_since_refill_ml == 100.0
        # Session should be cleared
        assert coord.state.cleaning_in_progress is False
        assert coord.state.session_checkpointed is False


class TestDockErrorSpecificityInCoordinator:
    """Tests that dock errors are specific in the coordinator."""

    def test_clean_water_dock_error_triggers_water_low_only(self, mock_hass, mock_config_entry, mock_storage):
        """Test 'clean water empty' triggers water low but not waste full."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dock_error_raw = "clean water empty"
        coord._cached_clean_water_sensor = None
        coord._cached_dirty_water_sensor = None

        is_low, low_source = coord.get_water_low()
        is_full, full_source = coord.get_waste_full()

        assert is_low is True
        assert is_full is False  # Clean water error shouldn't trigger waste full

    def test_dirty_water_dock_error_triggers_waste_full_only(self, mock_hass, mock_config_entry, mock_storage):
        """Test 'dirty water full' triggers waste full but not water low."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dock_error_raw = "dirty water full"
        coord._cached_clean_water_sensor = None
        coord._cached_dirty_water_sensor = None

        is_low, _ = coord.get_water_low()
        is_full, _ = coord.get_waste_full()

        assert is_low is False  # Dirty water error shouldn't trigger water low
        assert is_full is True

    def test_unrelated_dock_error_triggers_neither(self, mock_hass, mock_config_entry, mock_storage):
        """Test unrelated dock error triggers neither water low nor waste full."""
        coord = _make_coordinator(mock_hass, mock_config_entry, mock_storage)

        coord._cached_dock_error_raw = "brush stuck"
        coord._cached_clean_water_sensor = None
        coord._cached_dirty_water_sensor = None

        is_low, _ = coord.get_water_low()
        is_full, _ = coord.get_waste_full()

        assert is_low is False
        assert is_full is False
