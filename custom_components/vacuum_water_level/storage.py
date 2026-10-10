"""Storage handler for Vacuum Water Level integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION, STORAGE_MINOR_VERSION

_LOGGER = logging.getLogger(__name__)


class VacuumWaterStorage:
    """Manages persistent state for a vacuum water level instance."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the storage."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
        )
        self.data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load stored data."""
        stored = await self._store.async_load()
        if stored:
            self.data = stored
        else:
            self.data = {}
        return self.data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data to storage."""
        self.data = data
        await self._store.async_save(data)
