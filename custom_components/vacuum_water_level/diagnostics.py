"""Diagnostics support for Vacuum Water Level."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VacuumWaterLevelCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry_id": entry.entry_id,
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "coordinator_data": coordinator.data,
        "water_model": coordinator.water_model.to_dict(),
        "waste_model": coordinator.waste_model.to_dict(),
        "reserve_learning": coordinator.reserve.to_dict(),
        "runtime_state": coordinator.state.to_dict(),
    }
