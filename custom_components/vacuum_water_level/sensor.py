"""Sensor platform for Vacuum Water Level integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    SENSOR_WATER_REMAINING_PCT,
    SENSOR_WATER_REMAINING_ML,
    SENSOR_WATER_USED_SINCE_REFILL,
    SENSOR_WASTE_TANK_PCT,
    SENSOR_WASTE_TANK_ML,
    SENSOR_WATER_CONSUMPTION_RATE,
    SENSOR_DIRTY_WATER_FILL_RATE,
    SENSOR_LAST_REFILL,
    SENSOR_LAST_WASTE_EMPTY,
    SENSOR_PREDICTION_DIAGNOSTICS,
)
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelBaseEntity


@dataclass(frozen=True, kw_only=True)
class VacuumWaterSensorEntityDescription(SensorEntityDescription):
    """Description for vacuum water level sensor entities."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[VacuumWaterSensorEntityDescription, ...] = (
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WATER_REMAINING_PCT,
        value_key="water_remaining_pct",
        translation_key="water_remaining_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WATER_REMAINING_ML,
        value_key="water_remaining_ml",
        translation_key="water_remaining_ml",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WATER_USED_SINCE_REFILL,
        value_key="water_used_since_refill",
        translation_key="water_used_since_refill",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water-minus",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WASTE_TANK_PCT,
        value_key="waste_tank_pct",
        translation_key="waste_tank_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-alert-outline",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WASTE_TANK_ML,
        value_key="waste_tank_ml",
        translation_key="waste_tank_ml",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-boiler",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_WATER_CONSUMPTION_RATE,
        value_key="water_consumption_rate",
        translation_key="water_consumption_rate",
        native_unit_of_measurement="mL/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-speed",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_DIRTY_WATER_FILL_RATE,
        value_key="dirty_water_fill_rate",
        translation_key="dirty_water_fill_rate",
        native_unit_of_measurement="mL/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_LAST_REFILL,
        value_key="last_refill",
        translation_key="last_refill",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check-outline",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_LAST_WASTE_EMPTY,
        value_key="last_waste_empty",
        translation_key="last_waste_empty",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:delete-restore",
    ),
    VacuumWaterSensorEntityDescription(
        key=SENSOR_PREDICTION_DIAGNOSTICS,
        value_key="diagnostics",
        translation_key="prediction_diagnostics",
        icon="mdi:chart-timeline-variant",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        VacuumWaterLevelSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelSensor(VacuumWaterLevelBaseEntity, SensorEntity):
    """Sensor entity for vacuum water level."""

    entity_description: VacuumWaterSensorEntityDescription

    def __init__(
        self,
        coordinator: VacuumWaterLevelCoordinator,
        description: VacuumWaterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the value from coordinator data."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self.entity_description.value_key)
        if self.entity_description.key == SENSOR_PREDICTION_DIAGNOSTICS:
            return f"Model Cycle {self.coordinator.water_model.cycles_observed}"
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra diagnostics attributes."""
        if (
            self.entity_description.key == SENSOR_PREDICTION_DIAGNOSTICS
            and self.coordinator.data
        ):
            return self.coordinator.data.get("diagnostics", {})
        return None
