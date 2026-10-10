"""Diagnostics support for Vacuum Water Level integration.

Provides diagnostic download for troubleshooting.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "entry": {
            "title": config_entry.title,
            "data": config_entry.data,
            "options": config_entry.options,
        },
        "diagnostics": coordinator.get_diagnostics(),
    }
