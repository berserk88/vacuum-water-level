"""Config flow for Vacuum Water Level integration."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_VACUUM_ENTITY,
    CONF_CLEAN_TANK_CAPACITY,
    CONF_DIRTY_TANK_CAPACITY,
    CONF_WATER_LOW_THRESHOLD,
    CONF_WASTE_FULL_THRESHOLD,
    CONF_CLEANING_ENTITY,
    CONF_AREA_ENTITY,
    CONF_STATUS_ENTITY,
    CONF_MOP_MODE_ENTITY,
    CONF_MOP_INTENSITY_ENTITY,
    CONF_DOCK_ERROR_ENTITY,
    CONF_CLEAN_WATER_SENSOR,
    CONF_DIRTY_WATER_SENSOR,
    DEFAULT_CLEAN_TANK_CAPACITY,
    DEFAULT_DIRTY_TANK_CAPACITY,
    DEFAULT_WATER_LOW_THRESHOLD,
    DEFAULT_WASTE_FULL_THRESHOLD,
)


class VacuumWaterLevelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vacuum Water Level."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Select vacuum and tank parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_companion()

        schema = vol.Schema(
            {
                vol.Required(CONF_VACUUM_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="vacuum")
                ),
                vol.Required(
                    CONF_CLEAN_TANK_CAPACITY, default=DEFAULT_CLEAN_TANK_CAPACITY
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
                vol.Required(
                    CONF_DIRTY_TANK_CAPACITY, default=DEFAULT_DIRTY_TANK_CAPACITY
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
                vol.Required(
                    CONF_WATER_LOW_THRESHOLD, default=DEFAULT_WATER_LOW_THRESHOLD
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Required(
                    CONF_WASTE_FULL_THRESHOLD, default=DEFAULT_WASTE_FULL_THRESHOLD
                ): vol.All(vol.Coerce(int), vol.Range(min=50, max=99)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_companion(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Select companion sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            vacuum_id = self._data.get(CONF_VACUUM_ENTITY, "Vacuum")
            return self.async_create_entry(
                title=f"Water Level ({vacuum_id})",
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_CLEANING_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_AREA_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_STATUS_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_MOP_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig()
                ),
                vol.Optional(CONF_MOP_INTENSITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig()
                ),
                vol.Optional(CONF_DOCK_ERROR_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_CLEAN_WATER_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_DIRTY_WATER_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="companion",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow."""
        return VacuumWaterLevelOptionsFlow(config_entry)


class VacuumWaterLevelOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CLEAN_TANK_CAPACITY,
                    default=current.get(
                        CONF_CLEAN_TANK_CAPACITY, DEFAULT_CLEAN_TANK_CAPACITY
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
                vol.Required(
                    CONF_DIRTY_TANK_CAPACITY,
                    default=current.get(
                        CONF_DIRTY_TANK_CAPACITY, DEFAULT_DIRTY_TANK_CAPACITY
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
                vol.Required(
                    CONF_WATER_LOW_THRESHOLD,
                    default=current.get(
                        CONF_WATER_LOW_THRESHOLD, DEFAULT_WATER_LOW_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
                vol.Required(
                    CONF_WASTE_FULL_THRESHOLD,
                    default=current.get(
                        CONF_WASTE_FULL_THRESHOLD, DEFAULT_WASTE_FULL_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=50, max=99)),
                vol.Optional(
                    CONF_CLEANING_ENTITY,
                    description={"suggested_value": current.get(CONF_CLEANING_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    CONF_AREA_ENTITY,
                    description={"suggested_value": current.get(CONF_AREA_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_STATUS_ENTITY,
                    description={"suggested_value": current.get(CONF_STATUS_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_MOP_MODE_ENTITY,
                    description={"suggested_value": current.get(CONF_MOP_MODE_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Optional(
                    CONF_MOP_INTENSITY_ENTITY,
                    description={"suggested_value": current.get(CONF_MOP_INTENSITY_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Optional(
                    CONF_DOCK_ERROR_ENTITY,
                    description={"suggested_value": current.get(CONF_DOCK_ERROR_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_CLEAN_WATER_SENSOR,
                    description={"suggested_value": current.get(CONF_CLEAN_WATER_SENSOR)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    CONF_DIRTY_WATER_SENSOR,
                    description={"suggested_value": current.get(CONF_DIRTY_WATER_SENSOR)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
