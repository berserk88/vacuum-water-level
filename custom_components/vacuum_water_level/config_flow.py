"""Config flow for Vacuum Water Level integration.

Two-step setup:
    1. Select vacuum entity and tank capacities
    2. Auto-discover companion entities (editable)

Supports an OptionsFlow for editing all discovered entities after setup.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    CONF_AREA_ENTITY,
    CONF_CLEANING_ENTITY,
    CONF_CLEAN_TANK_CAPACITY,
    CONF_CLEAN_WATER_SENSOR,
    CONF_DIRTY_TANK_CAPACITY,
    CONF_DIRTY_WATER_SENSOR,
    CONF_DOCK_ERROR_ENTITY,
    CONF_MOP_INTENSITY_ENTITY,
    CONF_MOP_MODE_ENTITY,
    CONF_STATUS_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_WATER_LOW_THRESHOLD,
    CONF_WASTE_FULL_THRESHOLD,
    DEFAULT_CLEAN_TANK_CAPACITY,
    DEFAULT_DIRTY_TANK_CAPACITY,
    DEFAULT_WATER_LOW_THRESHOLD,
    DEFAULT_WASTE_FULL_THRESHOLD,
    DOMAIN,
    SUPPORTED_VENDORS,
)
from .discovery import discover_companion_entities

_LOGGER = logging.getLogger(__name__)


def _get_vacuum_entities(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """Get all vacuum entities for the selector."""
    ent_reg = async_get_entity_registry(hass)
    options = []
    for entity in ent_reg.entities.values():
        if entity.domain == "vacuum":
            state = hass.states.get(entity.entity_id)
            name = entity.name or entity.original_name or (
                state.name if state else entity.entity_id
            )
            options.append(
                selector.SelectOptionDict(
                    value=entity.entity_id,
                    label=f"{name} ({entity.entity_id})",
                )
            )

    # Also check states for vacuum entities not in registry
    for state in hass.states.async_all():
        if state.entity_id.startswith("vacuum."):
            if not any(o["value"] == state.entity_id for o in options):
                options.append(
                    selector.SelectOptionDict(
                        value=state.entity_id,
                        label=f"{state.name} ({state.entity_id})",
                    )
                )

    return sorted(options, key=lambda x: x["label"])


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VACUUM_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="vacuum"),
        ),
        vol.Required(
            CONF_CLEAN_TANK_CAPACITY, default=DEFAULT_CLEAN_TANK_CAPACITY
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10, max=5000, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(
            CONF_DIRTY_TANK_CAPACITY, default=DEFAULT_DIRTY_TANK_CAPACITY
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10, max=5000, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_WATER_LOW_THRESHOLD, default=DEFAULT_WATER_LOW_THRESHOLD
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=50, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_WASTE_FULL_THRESHOLD, default=DEFAULT_WASTE_FULL_THRESHOLD
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=50, max=99, step=1, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)


def _companion_schema(
    discovered: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the companion entity selection schema.

    Pre-fills with discovered entities but allows manual override.
    """
    discovered = discovered or {}

    def _entity_selector(
        domain: list[str], discovered_id: str | None = None
    ) -> selector.EntitySelector:
        return selector.EntitySelector(
            selector.EntitySelectorConfig(domain=domain, multiple=False),
        )

    schema_dict: dict = {
        vol.Optional(
            CONF_CLEANING_ENTITY,
            default=discovered.get(CONF_CLEANING_ENTITY),
        ): _entity_selector(["binary_sensor", "sensor"]),
        vol.Optional(
            CONF_AREA_ENTITY,
            default=discovered.get(CONF_AREA_ENTITY),
        ): _entity_selector(["sensor"]),
        vol.Optional(
            CONF_STATUS_ENTITY,
            default=discovered.get(CONF_STATUS_ENTITY),
        ): _entity_selector(["sensor"]),
        vol.Optional(
            CONF_MOP_MODE_ENTITY,
            default=discovered.get(CONF_MOP_MODE_ENTITY),
        ): _entity_selector(["select", "sensor"]),
        vol.Optional(
            CONF_MOP_INTENSITY_ENTITY,
            default=discovered.get(CONF_MOP_INTENSITY_ENTITY),
        ): _entity_selector(["select", "sensor"]),
        vol.Optional(
            CONF_DOCK_ERROR_ENTITY,
            default=discovered.get(CONF_DOCK_ERROR_ENTITY),
        ): _entity_selector(["binary_sensor", "sensor"]),
        vol.Optional(
            CONF_CLEAN_WATER_SENSOR,
            default=discovered.get(CONF_CLEAN_WATER_SENSOR),
        ): _entity_selector(["binary_sensor", "sensor"]),
        vol.Optional(
            CONF_DIRTY_WATER_SENSOR,
            default=discovered.get(CONF_DIRTY_WATER_SENSOR),
        ): _entity_selector(["binary_sensor", "sensor"]),
    }

    return vol.Schema(schema_dict)


class VacuumWaterLevelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vacuum Water Level."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_entities: dict[str, Any] = {}
        self._vacuum_entity: str | None = None
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: select vacuum and capacities."""
        errors: dict[str, str] = {}

        if user_input is not None:
            vacuum_entity = user_input[CONF_VACUUM_ENTITY]

            # Check for duplicate
            existing_entries = self._async_current_entries()
            for entry in existing_entries:
                if entry.data.get(CONF_VACUUM_ENTITY) == vacuum_entity:
                    errors["base"] = "already_configured"
                    break

            if not errors:
                self._vacuum_entity = vacuum_entity
                self._user_input = user_input

                # Auto-discover companion entities
                try:
                    candidates = discover_companion_entities(
                        self.hass, vacuum_entity
                    )
                    self._discovered_entities = {}
                    comp_map = {
                        "cleaning": CONF_CLEANING_ENTITY,
                        "area": CONF_AREA_ENTITY,
                        "status": CONF_STATUS_ENTITY,
                        "mop_mode": CONF_MOP_MODE_ENTITY,
                        "mop_intensity": CONF_MOP_INTENSITY_ENTITY,
                        "dock_error": CONF_DOCK_ERROR_ENTITY,
                        "clean_water": CONF_CLEAN_WATER_SENSOR,
                        "dirty_water": CONF_DIRTY_WATER_SENSOR,
                    }
                    for comp_type, conf_key in comp_map.items():
                        candidate = candidates.get(comp_type)
                        if candidate:
                            self._discovered_entities[conf_key] = (
                                candidate.entity_id
                            )

                    _LOGGER.debug(
                        "Vacuum Water Level: Discovered entities: %s",
                        self._discovered_entities,
                    )
                except Exception as err:
                    _LOGGER.warning(
                        "Vacuum Water Level: Discovery failed: %s", err
                    )

                return await self.async_step_companion()

        # Check if there are any vacuum entities
        vacuum_options = _get_vacuum_entities(self.hass)
        if not vacuum_options:
            return self.async_abort(reason="no_vacuums")

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "vacuum_count": str(len(vacuum_options)),
            },
        )

    async def async_step_companion(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the companion entity selection step."""
        if user_input is not None:
            # Merge user data with initial data
            config_data = {
                CONF_VACUUM_ENTITY: self._vacuum_entity,
                CONF_CLEAN_TANK_CAPACITY: self._user_input.get(
                    CONF_CLEAN_TANK_CAPACITY, DEFAULT_CLEAN_TANK_CAPACITY
                ),
                CONF_DIRTY_TANK_CAPACITY: self._user_input.get(
                    CONF_DIRTY_TANK_CAPACITY, DEFAULT_DIRTY_TANK_CAPACITY
                ),
                CONF_WATER_LOW_THRESHOLD: self._user_input.get(
                    CONF_WATER_LOW_THRESHOLD, DEFAULT_WATER_LOW_THRESHOLD
                ),
                CONF_WASTE_FULL_THRESHOLD: self._user_input.get(
                    CONF_WASTE_FULL_THRESHOLD, DEFAULT_WASTE_FULL_THRESHOLD
                ),
            }

            # Determine unique ID
            await self.async_set_unique_id(
                f"{DOMAIN}_{self._vacuum_entity}"
            )
            self._abort_if_unique_id_configured()

            # Store companion entities in options
            options = {k: v for k, v in user_input.items() if v}

            return self.async_create_entry(
                title=f"Water Level - {self._vacuum_entity.split('.')[-1]}",
                data=config_data,
                options=options,
            )

        # Build schema with discovered defaults
        schema = _companion_schema(self._discovered_entities)

        # Build description placeholders for discovery info
        discovery_info = ""
        for key, value in self._discovered_entities.items():
            if value:
                discovery_info += f"- {key}: {value}\n"

        return self.async_show_form(
            step_id="companion",
            data_schema=schema,
            description_placeholders={
                "discovery_info": discovery_info or "No entities auto-discovered.",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "VacuumWaterLevelOptionsFlow":
        """Get the options flow."""
        return VacuumWaterLevelOptionsFlow(config_entry)


class VacuumWaterLevelOptionsFlow(config_entries.OptionsFlow):
    """Options flow for editing companion entities and thresholds."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build schema from current options/data
        current_options = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CLEAN_TANK_CAPACITY,
                    default=current_options.get(
                        CONF_CLEAN_TANK_CAPACITY, DEFAULT_CLEAN_TANK_CAPACITY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10, max=5000, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_DIRTY_TANK_CAPACITY,
                    default=current_options.get(
                        CONF_DIRTY_TANK_CAPACITY, DEFAULT_DIRTY_TANK_CAPACITY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10, max=5000, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_WATER_LOW_THRESHOLD,
                    default=current_options.get(
                        CONF_WATER_LOW_THRESHOLD, DEFAULT_WATER_LOW_THRESHOLD
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_WASTE_FULL_THRESHOLD,
                    default=current_options.get(
                        CONF_WASTE_FULL_THRESHOLD, DEFAULT_WASTE_FULL_THRESHOLD
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=50, max=99, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_CLEANING_ENTITY,
                    default=current_options.get(CONF_CLEANING_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_AREA_ENTITY,
                    default=current_options.get(CONF_AREA_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_STATUS_ENTITY,
                    default=current_options.get(CONF_STATUS_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_MOP_MODE_ENTITY,
                    default=current_options.get(CONF_MOP_MODE_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["select", "sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_MOP_INTENSITY_ENTITY,
                    default=current_options.get(CONF_MOP_INTENSITY_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["select", "sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_DOCK_ERROR_ENTITY,
                    default=current_options.get(CONF_DOCK_ERROR_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_CLEAN_WATER_SENSOR,
                    default=current_options.get(CONF_CLEAN_WATER_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "sensor"], multiple=False
                    )
                ),
                vol.Optional(
                    CONF_DIRTY_WATER_SENSOR,
                    default=current_options.get(CONF_DIRTY_WATER_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "sensor"], multiple=False
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
