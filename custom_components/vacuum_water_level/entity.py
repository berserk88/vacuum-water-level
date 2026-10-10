"""Base entity for Vacuum Water Level integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VacuumWaterLevelCoordinator


class VacuumWaterLevelEntity(CoordinatorEntity):
    """Base entity for Vacuum Water Level.

    All entities belong to a synthetic device representing the water tracking
    for a specific vacuum.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VacuumWaterLevelCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: The data coordinator.
            description: Entity description.
        """
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the synthetic device."""
        vacuum_name = self.coordinator.vacuum_entity_id
        # Try to get the vacuum's friendly name
        vacuum_state = self.hass.states.get(self.coordinator.vacuum_entity_id)
        if vacuum_state and vacuum_state.name:
            vacuum_name = vacuum_state.name

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=f"Vacuum Water Level - {vacuum_name}",
            manufacturer="Vacuum Water Level",
            model="Water Level Tracker",
            sw_version="1.0.0",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success or True
