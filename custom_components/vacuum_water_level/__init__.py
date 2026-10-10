"""The Vacuum Water Level integration.

Estimates clean water tank level and dirty/waste water tank fill level for
robot vacuums that do not expose actual tank levels. Uses adaptive learning
to improve estimates over time.

One config entry per vacuum. Each entry has its own storage, models, and entities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "button"]


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up Vacuum Water Level from a config entry.

    Creates a storage instance and coordinator for this vacuum, then
    forwards setup to the entity platforms.
    """
    from .const import DOMAIN
    from .coordinator import VacuumWaterLevelCoordinator
    from .storage import VacuumWaterStorage

    _LOGGER.debug(
        "Vacuum Water Level: Setting up entry %s for vacuum %s",
        config_entry.entry_id,
        config_entry.data.get("vacuum_entity"),
    )

    # Initialize storage
    storage = VacuumWaterStorage(hass, config_entry.entry_id)
    await storage.async_load()

    # Create coordinator
    coordinator = VacuumWaterLevelCoordinator(hass, config_entry, storage)

    # Set up coordinator (subscribe to state changes)
    await coordinator.async_setup()

    # Store coordinator and storage in hass data
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload a Vacuum Water Level config entry.

    Shuts down the coordinator, saves final state, and unloads platforms.
    """
    from .const import DOMAIN
    from .coordinator import VacuumWaterLevelCoordinator

    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Shut down coordinator (unsubscribes and persists)
    await coordinator.async_shutdown()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def async_reload_entry(hass, config_entry) -> None:
    """Reload a Vacuum Water Level config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
