"""Base entity for Vacuum Water Level integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_VACUUM_ENTITY
from .coordinator import VacuumWaterLevelCoordinator


class VacuumWaterLevelBaseEntity(CoordinatorEntity[VacuumWaterLevelCoordinator]):
    """Base entity for vacuum water level sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VacuumWaterLevelCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_key = entity_key
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_key}"

        # Link to vacuum device in Home Assistant device registry
        vacuum_entity_id = coordinator.config_entry.options.get(
            CONF_VACUUM_ENTITY,
            coordinator.config_entry.data.get(CONF_VACUUM_ENTITY),
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"Vacuum Water Level ({vacuum_entity_id or 'Vacuum'})",
            manufacturer="Vacuum Water Level",
            model="Adaptive Water Estimator",
        )
