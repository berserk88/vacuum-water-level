"""Button platform for Vacuum Water Level integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BUTTON_REFILLED, BUTTON_WASTE_EMPTIED, BUTTON_CLEAR_MODEL
from .coordinator import VacuumWaterLevelCoordinator
from .entity import VacuumWaterLevelBaseEntity


@dataclass(frozen=True, kw_only=True)
class VacuumWaterButtonEntityDescription(ButtonEntityDescription):
    """Description for button entities."""

    action_type: str


BUTTON_DESCRIPTIONS: tuple[VacuumWaterButtonEntityDescription, ...] = (
    VacuumWaterButtonEntityDescription(
        key=BUTTON_REFILLED,
        action_type="refilled",
        translation_key="refilled",
        icon="mdi:water-check",
    ),
    VacuumWaterButtonEntityDescription(
        key=BUTTON_WASTE_EMPTIED,
        action_type="waste_emptied",
        translation_key="waste_tank_emptied",
        icon="mdi:delete-empty",
    ),
    VacuumWaterButtonEntityDescription(
        key=BUTTON_CLEAR_MODEL,
        action_type="clear_model",
        translation_key="clear_prediction_model",
        icon="mdi:restart",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: VacuumWaterLevelCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        VacuumWaterLevelButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class VacuumWaterLevelButton(VacuumWaterLevelBaseEntity, ButtonEntity):
    """Button entity to trigger manual maintenance actions."""

    entity_description: VacuumWaterButtonEntityDescription

    def __init__(
        self,
        coordinator: VacuumWaterLevelCoordinator,
        description: VacuumWaterButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle button press."""
        action = self.entity_description.action_type
        if action == "refilled":
            await self.coordinator.async_refilled()
        elif action == "waste_emptied":
            await self.coordinator.async_waste_emptied()
        elif action == "clear_model":
            await self.coordinator.async_clear_prediction_model()
