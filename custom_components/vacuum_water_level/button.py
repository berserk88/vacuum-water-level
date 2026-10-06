"""Button platform for Vacuum Water Level integration.

Creates buttons for:
    - Refilled (manual refill trigger)
    - Waste Tank Emptied (manual empty trigger)
    - Clear Prediction Model (reset adaptive models)
"""

from __future__ import annotations

import logging

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BUTTON_CLEAR_MODEL, BUTTON_REFILLED, BUTTON_WASTE_EMPTIED, DOMAIN
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelEntity

_LOGGER = logging.getLogger(__name__)

BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key=BUTTON_REFILLED,
        name="Refilled",
        icon="mdi:water-plus",
    ),
    ButtonEntityDescription(
        key=BUTTON_WASTE_EMPTIED,
        name="Waste Tank Emptied",
        icon="mdi:trash-can-remove",
    ),
    ButtonEntityDescription(
        key=BUTTON_CLEAR_MODEL,
        name="Clear Prediction Model",
        icon="mdi:restart-alert",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vacuum Water Level buttons from a config entry."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        VacuumWaterLevelButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelButton(VacuumWaterLevelEntity, ButtonEntity):
    """Button entity for Vacuum Water Level."""

    async def async_press(self) -> None:
        """Handle the button press."""
        key = self.entity_description.key

        if key == BUTTON_REFILLED:
            _LOGGER.debug("Vacuum Water Level: Manual refill button pressed")
            self.coordinator.manual_refill()

        elif key == BUTTON_WASTE_EMPTIED:
            _LOGGER.debug("Vacuum Water Level: Manual waste empty button pressed")
            self.coordinator.manual_waste_empty()

        elif key == BUTTON_CLEAR_MODEL:
            _LOGGER.debug("Vacuum Water Level: Clear prediction model button pressed")
            self.coordinator.clear_prediction_model()
