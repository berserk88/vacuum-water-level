"""Common test fixtures for Vacuum Water Level integration tests."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
except ImportError:
    HomeAssistant = None  # type: ignore
    Store = None  # type: ignore

from custom_components.vacuum_water_level.const import (
    CONF_AREA_ENTITY,
    CONF_CLEANING_ENTITY,
    CONF_CLEAN_TANK_CAPACITY,
    CONF_CLEAN_WATER_SENSOR,
    CONF_DIRTY_TANK_CAPACITY,
    CONF_DIRTY_WATER_SENSOR,
    CONF_DOCK_ERROR_ENTITY,
    CONF_MOP_INTENSITY_ENTITY,
    CONF_MOP_MODE_ENTITY,
    CONF_STATUS_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_WATER_LOW_THRESHOLD,
    CONF_WASTE_FULL_THRESHOLD,
    DEFAULT_CLEAN_TANK_CAPACITY,
    DEFAULT_DIRTY_TANK_CAPACITY,
    DEFAULT_WATER_LOW_THRESHOLD,
    DEFAULT_WASTE_FULL_THRESHOLD,
    DOMAIN,
)
from custom_components.vacuum_water_level.learning import (
    ReserveLearning,
    VacuumWaterState,
    WaterModel,
    WasteModel,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant) if HomeAssistant else MagicMock()
    hass.states = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_VACUUM_ENTITY: "vacuum.test_vacuum",
        CONF_CLEAN_TANK_CAPACITY: 250,
        CONF_DIRTY_TANK_CAPACITY: 250,
        CONF_WATER_LOW_THRESHOLD: 15,
        CONF_WASTE_FULL_THRESHOLD: 85,
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_config_entry_with_companions():
    """Create a mock config entry with companion entities configured."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_VACUUM_ENTITY: "vacuum.roborock_qrevo_maxv",
        CONF_CLEAN_TANK_CAPACITY: 250,
        CONF_DIRTY_TANK_CAPACITY: 250,
        CONF_WATER_LOW_THRESHOLD: 15,
        CONF_WASTE_FULL_THRESHOLD: 85,
    }
    entry.options = {
        CONF_CLEANING_ENTITY: "binary_sensor.roborock_qrevo_maxv_cleaning",
        CONF_AREA_ENTITY: "sensor.roborock_qrevo_maxv_cleaned_area",
        CONF_STATUS_ENTITY: "sensor.roborock_qrevo_maxv_status",
        CONF_MOP_MODE_ENTITY: "select.roborock_qrevo_maxv_mop_mode",
        CONF_MOP_INTENSITY_ENTITY: "select.roborock_qrevo_maxv_mop_intensity",
        CONF_DOCK_ERROR_ENTITY: "binary_sensor.roborock_qrevo_maxv_dock_error",
        CONF_CLEAN_WATER_SENSOR: "binary_sensor.roborock_qrevo_maxv_dock_clean_water_box",
        CONF_DIRTY_WATER_SENSOR: "binary_sensor.roborock_qrevo_maxv_dock_dirty_water_box",
    }
    return entry


@pytest.fixture
def water_model():
    """Create a fresh WaterModel."""
    return WaterModel()


@pytest.fixture
def waste_model():
    """Create a fresh WasteModel."""
    return WasteModel()


@pytest.fixture
def reserve_learning():
    """Create a fresh ReserveLearning."""
    return ReserveLearning()


@pytest.fixture
def runtime_state():
    """Create a fresh VacuumWaterState."""
    return VacuumWaterState()


@pytest.fixture
def mock_storage(mock_hass):
    """Create a mock storage instance."""
    try:
        from custom_components.vacuum_water_level.storage import VacuumWaterStorage
        storage = VacuumWaterStorage(mock_hass, "test_entry_id")
        storage._data = storage._default_data()
        return storage
    except ImportError:
        pytest.skip("Home Assistant not available for storage tests")
