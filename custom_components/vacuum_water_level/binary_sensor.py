"""Binary sensor platform for Vacuum Water Level integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BINARY_WATER_LOW, BINARY_WASTE_FULL
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelBaseEntity


@dataclass(frozen=True, kw_only=True)
class VacuumWaterBinarySensorDescription(BinarySensorEntityDescription):
    """Description for binary sensor entities."""

    value_key: str


BINARY_SENSOR_DESCRIPTIONS: tuple[VacuumWaterBinarySensorDescription, ...] = (
    VacuumWaterBinarySensorDescription(
        key=BINARY_WATER_LOW,
        value_key="water_low",
        translation_key="water_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:water-alert",
    ),
    VacuumWaterBinarySensorDescription(
        key=BINARY_WASTE_FULL,
        value_key="waste_tank_full",
        translation_key="waste_tank_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:water-boiler-alert",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        VacuumWaterLevelBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelBinarySensor(VacuumWaterLevelBaseEntity, BinarySensorEntity):
    """Binary sensor entity for vacuum water level."""

    entity_description: VacuumWaterBinarySensorDescription

    def __init__(
        self,
        coordinator: VacuumWaterLevelCoordinator,
        description: VacuumWaterBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if problem is active."""
        if not self.coordinator.data:
            return None
        return bool(self.coordinator.data.get(self.entity_description.value_key, False))
