"""Common test fixtures for Vacuum Water Level integration tests."""

from __future__ import annotations

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# When Home Assistant is not installed, create minimal mock modules
# so that modules using lazy imports (TYPE_CHECKING) can still be
# imported and tested.
try:
    import homeassistant  # noqa: F401
except ImportError:
    # Create mock homeassistant package
    ha_mock = types.ModuleType("homeassistant")
    ha_core_mock = types.ModuleType("homeassistant.core")
    ha_core_mock.HomeAssistant = type("HomeAssistant", (), {})
    ha_core_mock.State = type("State", (), {})
    ha_core_mock.callback = lambda f: f
    ha_helpers_mock = types.ModuleType("homeassistant.helpers")
    ha_storage_mock = types.ModuleType("homeassistant.helpers.storage")
    class _MockStore:
        def __init__(self, *args, **kwargs):
            self.async_delay_save = MagicMock()
            self.async_load = AsyncMock(return_value=None)
    ha_storage_mock.Store = _MockStore
    ha_ent_reg_mock = types.ModuleType("homeassistant.helpers.entity_registry")
    ha_ent_reg_mock.async_get = MagicMock()
    ha_upd_coord_mock = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_upd_coord_mock.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {"__init__": lambda self, *a, **kw: None})
    ha_event_mock = types.ModuleType("homeassistant.helpers.event")
    ha_event_mock.async_track_state_change_event = MagicMock()
    ha_config_entries_mock = types.ModuleType("homeassistant.config_entries")
    ha_config_entries_mock.ConfigEntry = type("ConfigEntry", (), {})
    ha_config_entries_mock.ConfigFlow = type("ConfigFlow", (), {})
    ha_config_entries_mock.OptionsFlow = type("OptionsFlow", (), {})
    ha_data_flow_mock = types.ModuleType("homeassistant.data_entry_flow")
    ha_data_flow_mock.FlowResult = type("FlowResult", (), {})
    ha_selector_mock = types.ModuleType("homeassistant.helpers.selector")
    ha_selector_mock.EntitySelector = MagicMock
    ha_selector_mock.EntitySelectorConfig = type("EntitySelectorConfig", (), {})
    ha_selector_mock.NumberSelector = MagicMock
    ha_selector_mock.NumberSelectorConfig = type("NumberSelectorConfig", (), {})
    ha_selector_mock.NumberSelectorMode = type("NumberSelectorMode", (), {})
    ha_selector_mock.SelectOptionDict = dict
    ha_selector_mock.SelectSelector = MagicMock
    ha_selector_mock.SelectSelectorConfig = type("SelectSelectorConfig", (), {})

    ha_mock.core = ha_core_mock
    ha_mock.helpers = ha_helpers_mock
    ha_helpers_mock.storage = ha_storage_mock
    ha_helpers_mock.entity_registry = ha_ent_reg_mock
    ha_helpers_mock.update_coordinator = ha_upd_coord_mock
    ha_helpers_mock.event = ha_event_mock
    ha_helpers_mock.selector = ha_selector_mock
    ha_mock.config_entries = ha_config_entries_mock
    ha_mock.data_entry_flow = ha_data_flow_mock

    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.core"] = ha_core_mock
    sys.modules["homeassistant.helpers"] = ha_helpers_mock
    sys.modules["homeassistant.helpers.storage"] = ha_storage_mock
    sys.modules["homeassistant.helpers.entity_registry"] = ha_ent_reg_mock
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_upd_coord_mock
    sys.modules["homeassistant.helpers.event"] = ha_event_mock
    sys.modules["homeassistant.helpers.selector"] = ha_selector_mock
    sys.modules["homeassistant.config_entries"] = ha_config_entries_mock
    sys.modules["homeassistant.data_entry_flow"] = ha_data_flow_mock

    HomeAssistant = ha_core_mock.HomeAssistant
    Store = ha_storage_mock.Store

try:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
except ImportError:
    pass  # Already set up above

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
