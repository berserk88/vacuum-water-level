"""Sensor platform for Vacuum Water Level integration.

Creates sensors for:
    - Water remaining percentage
    - Water remaining mL
    - Water used since refill
    - Waste tank percentage
    - Waste tank mL
    - Last refill timestamp
    - Last waste empty timestamp
    - Prediction diagnostics
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_LAST_REFILL,
    SENSOR_LAST_WASTE_EMPTY,
    SENSOR_PREDICTION_DIAGNOSTICS,
    SENSOR_WATER_CONSUMPTION_RATE,
    SENSOR_DIRTY_WATER_FILL_RATE,
    SENSOR_WATER_REMAINING_ML,
    SENSOR_WATER_REMAINING_PCT,
    SENSOR_WATER_USED_SINCE_REFILL,
    SENSOR_WASTE_TANK_ML,
    SENSOR_WASTE_TANK_PCT,
)
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelEntity

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key=SENSOR_WATER_REMAINING_PCT,
        name="Water Remaining",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key=SENSOR_WATER_REMAINING_ML,
        name="Water Remaining Volume",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mL",
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key=SENSOR_WATER_USED_SINCE_REFILL,
        name="Water Used Since Refill",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mL",
        icon="mdi:water-minus",
    ),
    SensorEntityDescription(
        key=SENSOR_WASTE_TANK_PCT,
        name="Waste Tank Level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:trash-can-outline",
    ),
    SensorEntityDescription(
        key=SENSOR_WASTE_TANK_ML,
        name="Waste Tank Volume",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mL",
        icon="mdi:trash-can",
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_REFILL,
        name="Last Refill",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:water-plus",
    ),
    SensorEntityDescription(
        key=SENSOR_LAST_WASTE_EMPTY,
        name="Last Waste Empty",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:trash-can-remove",
    ),
    SensorEntityDescription(
        key=SENSOR_WATER_CONSUMPTION_RATE,
        name="Water Consumption Rate",
        native_unit_of_measurement="mL/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-speed",
    ),
    SensorEntityDescription(
        key=SENSOR_DIRTY_WATER_FILL_RATE,
        name="Dirty Water Fill Rate",
        native_unit_of_measurement="mL/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key=SENSOR_PREDICTION_DIAGNOSTICS,
        name="Prediction Diagnostics",
        icon="mdi:chart-line",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vacuum Water Level sensors from a config entry."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        VacuumWaterLevelSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelSensor(VacuumWaterLevelEntity, SensorEntity):
    """Sensor entity for Vacuum Water Level."""

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        key = self.entity_description.key

        if key == SENSOR_WATER_REMAINING_PCT:
            return round(self.coordinator.get_water_remaining_pct(), 1)

        if key == SENSOR_WATER_REMAINING_ML:
            return round(self.coordinator.get_water_remaining_ml(), 1)

        if key == SENSOR_WATER_USED_SINCE_REFILL:
            return round(self.coordinator.state.water_used_since_refill_ml, 1)

        if key == SENSOR_WASTE_TANK_PCT:
            return round(self.coordinator.get_waste_pct(), 1)

        if key == SENSOR_WASTE_TANK_ML:
            return round(self.coordinator.get_waste_ml(), 1)

        if key == SENSOR_LAST_REFILL:
            refill_str = self.coordinator.state.last_refill
            if refill_str:
                try:
                    return datetime.fromisoformat(refill_str)
                except (ValueError, TypeError):
                    return None
            return None

        if key == SENSOR_LAST_WASTE_EMPTY:
            empty_str = self.coordinator.state.last_waste_empty
            if empty_str:
                try:
                    return datetime.fromisoformat(empty_str)
                except (ValueError, TypeError):
                    return None
            return None

        if key == SENSOR_WATER_CONSUMPTION_RATE:
            return self.coordinator.get_water_consumption_rate()

        if key == SENSOR_DIRTY_WATER_FILL_RATE:
            return self.coordinator.get_dirty_water_fill_rate()

        if key == SENSOR_PREDICTION_DIAGNOSTICS:
            diag = self.coordinator.get_diagnostics()
            # Return a summary string for the sensor state
            return f"Water: {diag['water_model']['cycles_observed']} cycles, Waste: {diag['waste_model']['cycles_observed']} cycles"

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        key = self.entity_description.key

        if key == SENSOR_WATER_REMAINING_PCT:
            is_low, source = self.coordinator.get_water_low()
            return {
                "effective_capacity_ml": round(
                    self.coordinator.get_effective_clean_capacity(), 1
                ),
                "clean_reserve_ml": round(
                    self.coordinator.reserve.clean_reserve_ml, 1
                ),
                "water_low_threshold": self.coordinator.water_low_threshold,
                "is_water_low": is_low,
                "detection_source": source,
                "cycles_observed": self.coordinator.water_model.cycles_observed,
            }

        if key == SENSOR_WASTE_TANK_PCT:
            is_full, source = self.coordinator.get_waste_full()
            return {
                "effective_capacity_ml": round(
                    self.coordinator.get_effective_dirty_capacity(), 1
                ),
                "dirty_reserve_ml": round(
                    self.coordinator.reserve.dirty_reserve_ml, 1
                ),
                "waste_full_threshold": self.coordinator.waste_full_threshold,
                "is_waste_full": is_full,
                "detection_source": source,
                "cycles_observed": self.coordinator.waste_model.cycles_observed,
            }

        if key == SENSOR_WATER_USED_SINCE_REFILL:
            return {
                "area_ml_per_m2": self.coordinator.water_model.correction_factors.get(
                    "area_ml_per_m2", 2.0
                ),
                "learned_wash_volume_ml": self.coordinator.water_model.learned_wash_volume_ml,
                "pending_area_m2": self.coordinator.water_model.pending_area_m2,
                "pending_wash_count": self.coordinator.water_model.pending_wash_count,
                "last_mop_mode": self.coordinator.state.last_mop_mode,
                "last_mop_intensity": self.coordinator.state.last_mop_intensity,
            }

        if key == SENSOR_WASTE_TANK_ML:
            return {
                "waste_ratio": self.coordinator.waste_model.waste_ratio,
                "pending_usage_ml": self.coordinator.waste_model.pending_usage_ml,
            }

        if key == SENSOR_PREDICTION_DIAGNOSTICS:
            return self.coordinator.get_diagnostics()

        return None
