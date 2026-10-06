"""Binary sensor platform for Vacuum Water Level integration.

Creates binary sensors for:
    - Water Low
    - Waste Tank Full
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_WASTE_FULL, BINARY_WATER_LOW, DOMAIN
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelEntity

BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key=BINARY_WATER_LOW,
        name="Water Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:water-alert",
    ),
    BinarySensorEntityDescription(
        key=BINARY_WASTE_FULL,
        name="Waste Tank Full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:trash-can-alert",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vacuum Water Level binary sensors from a config entry."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        VacuumWaterLevelBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelBinarySensor(VacuumWaterLevelEntity, BinarySensorEntity):
    """Binary sensor entity for Vacuum Water Level."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        key = self.entity_description.key

        if key == BINARY_WATER_LOW:
            is_low, _ = self.coordinator.get_water_low()
            return is_low

        if key == BINARY_WASTE_FULL:
            is_full, _ = self.coordinator.get_waste_full()
            return is_full

        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra state attributes."""
        key = self.entity_description.key

        if key == BINARY_WATER_LOW:
            _, source = self.coordinator.get_water_low()
            return {
                "detection_source": source,
                "remaining_pct": round(
                    self.coordinator.get_water_remaining_pct(), 1
                ),
                "remaining_ml": round(
                    self.coordinator.get_water_remaining_ml(), 1
                ),
                "threshold": self.coordinator.water_low_threshold,
            }

        if key == BINARY_WASTE_FULL:
            _, source = self.coordinator.get_waste_full()
            return {
                "detection_source": source,
                "fill_pct": round(self.coordinator.get_waste_pct(), 1),
                "fill_ml": round(self.coordinator.get_waste_ml(), 1),
                "threshold": self.coordinator.waste_full_threshold,
            }

        return None
