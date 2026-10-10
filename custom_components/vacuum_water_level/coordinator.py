"""Data coordinator for Vacuum Water Level integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event

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
)
from .detection import (
    detect_cleaning,
    detect_water_low,
    detect_waste_full,
    parse_dock_error_clean,
    parse_dock_error_dirty,
)
from .learning import (
    ReserveLearning,
    VacuumWaterState,
    WaterModel,
    WasteModel,
    compute_water_remaining_ml,
    compute_water_remaining_pct,
    compute_waste_ml,
    compute_waste_pct,
)
from .storage import VacuumWaterStorage

_LOGGER = logging.getLogger(__name__)


class VacuumWaterLevelCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single vacuum's water level tracking."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: Any,
        storage: VacuumWaterStorage,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Vacuum Water Level ({config_entry.entry_id})",
            update_interval=None,
        )
        self.config_entry = config_entry
        self.storage = storage

        data = storage.data
        self.water_model = WaterModel.from_dict(data.get("water_model"))
        self.waste_model = WasteModel.from_dict(data.get("waste_model"))
        self.reserve = ReserveLearning.from_dict(data.get("reserve_learning"))
        self.state = VacuumWaterState.from_dict(data.get("runtime_state"))

        self._unsub_trackers: list = []

    @property
    def clean_capacity(self) -> float:
        """Clean tank capacity."""
        return float(
            self.config_entry.options.get(
                CONF_CLEAN_TANK_CAPACITY,
                self.config_entry.data.get(
                    CONF_CLEAN_TANK_CAPACITY, DEFAULT_CLEAN_TANK_CAPACITY
                ),
            )
        )

    @property
    def dirty_capacity(self) -> float:
        """Dirty tank capacity."""
        return float(
            self.config_entry.options.get(
                CONF_DIRTY_TANK_CAPACITY,
                self.config_entry.data.get(
                    CONF_DIRTY_TANK_CAPACITY, DEFAULT_DIRTY_TANK_CAPACITY
                ),
            )
        )

    @property
    def water_low_threshold(self) -> float:
        """Water low warning threshold."""
        return float(
            self.config_entry.options.get(
                CONF_WATER_LOW_THRESHOLD,
                self.config_entry.data.get(
                    CONF_WATER_LOW_THRESHOLD, DEFAULT_WATER_LOW_THRESHOLD
                ),
            )
        )

    @property
    def waste_full_threshold(self) -> float:
        """Waste tank full warning threshold."""
        return float(
            self.config_entry.options.get(
                CONF_WASTE_FULL_THRESHOLD,
                self.config_entry.data.get(
                    CONF_WASTE_FULL_THRESHOLD, DEFAULT_WASTE_FULL_THRESHOLD
                ),
            )
        )

    @property
    def water_remaining_pct(self) -> float:
        """Clean water remaining percentage."""
        return compute_water_remaining_pct(
            self.state.water_used_since_refill_ml,
            self.clean_capacity,
            self.reserve.clean_reserve_ml,
        )

    @property
    def water_remaining_ml(self) -> float:
        """Clean water remaining in mL."""
        return compute_water_remaining_ml(
            self.state.water_used_since_refill_ml,
            self.clean_capacity,
            self.reserve.clean_reserve_ml,
        )

    @property
    def waste_tank_pct(self) -> float:
        """Waste tank fill percentage."""
        return compute_waste_pct(
            self.state.waste_collected_ml,
            self.dirty_capacity,
            self.reserve.dirty_reserve_ml,
        )

    @property
    def waste_tank_ml(self) -> float:
        """Waste tank fill in mL."""
        return compute_waste_ml(
            self.state.waste_collected_ml,
            self.dirty_capacity,
            self.reserve.dirty_reserve_ml,
        )

    @property
    def water_consumption_rate(self) -> float:
        """Current effective clean water consumption rate in mL/m²."""
        return self.water_model.get_effective_consumption_rate(
            self.state.last_mop_mode,
            self.state.last_mop_intensity,
        )

    @property
    def dirty_water_fill_rate(self) -> float:
        """Current effective dirty water fill rate in mL/m²."""
        effective_clean = self.water_consumption_rate
        return self.waste_model.get_dirty_fill_rate(effective_clean)

    @property
    def is_water_low(self) -> bool:
        """Check if clean water is low."""
        clean_sensor = self._get_entity_bool(CONF_CLEAN_WATER_SENSOR)
        dock_err = parse_dock_error_clean(self._get_entity_str(CONF_DOCK_ERROR_ENTITY))
        return detect_water_low(
            clean_sensor,
            dock_err,
            self.water_remaining_pct,
            self.water_low_threshold,
            self.state.clean_warning_latched,
        )

    @property
    def is_waste_full(self) -> bool:
        """Check if dirty water tank is full."""
        dirty_sensor = self._get_entity_bool(CONF_DIRTY_WATER_SENSOR)
        dock_err = parse_dock_error_dirty(self._get_entity_str(CONF_DOCK_ERROR_ENTITY))
        return detect_waste_full(
            dirty_sensor,
            dock_err,
            self.waste_tank_pct,
            self.waste_full_threshold,
            self.state.dirty_warning_latched,
        )

    def _get_entity_str(self, conf_key: str) -> str | None:
        entity_id = self.config_entry.options.get(
            conf_key, self.config_entry.data.get(conf_key)
        )
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _get_entity_bool(self, conf_key: str) -> bool | None:
        st = self._get_entity_str(conf_key)
        if st is None:
            return None
        return st.lower() in ("on", "true", "1", "problem")

    def _get_entity_float(self, conf_key: str) -> float | None:
        st = self._get_entity_str(conf_key)
        if st is None:
            return None
        try:
            return float(st)
        except (ValueError, TypeError):
            return None

    async def async_setup(self) -> None:
        """Setup listeners for companion entities."""
        entities_to_track: list[str] = []
        for key in (
            CONF_VACUUM_ENTITY,
            CONF_CLEANING_ENTITY,
            CONF_AREA_ENTITY,
            CONF_STATUS_ENTITY,
            CONF_MOP_MODE_ENTITY,
            CONF_MOP_INTENSITY_ENTITY,
            CONF_DOCK_ERROR_ENTITY,
            CONF_CLEAN_WATER_SENSOR,
            CONF_DIRTY_WATER_SENSOR,
        ):
            ent = self.config_entry.options.get(
                key, self.config_entry.data.get(key)
            )
            if ent:
                entities_to_track.append(ent)

        if entities_to_track:
            self._unsub_trackers.append(
                async_track_state_change_event(
                    self.hass, entities_to_track, self._handle_companion_state_change
                )
            )

        self.async_set_updated_data(self._build_data())

    @callback
    def _handle_companion_state_change(self, event: Any) -> None:
        """Handle state change in companion entities."""
        cleaning = detect_cleaning(
            self._get_entity_bool(CONF_CLEANING_ENTITY),
            self._get_entity_str(CONF_STATUS_ENTITY),
            self._get_entity_str(CONF_VACUUM_ENTITY),
        )

        current_area = self._get_entity_float(CONF_AREA_ENTITY) or 0.0
        mop_mode = self._get_entity_str(CONF_MOP_MODE_ENTITY)
        mop_intensity = self._get_entity_str(CONF_MOP_INTENSITY_ENTITY)

        self.state.last_mop_mode = mop_mode
        self.state.last_mop_intensity = mop_intensity

        if cleaning:
            if not self.state.cleaning_in_progress:
                self.state.cleaning_in_progress = True
                self.state.session_start_area = current_area
            else:
                delta_area = max(0.0, current_area - self.state.last_area)
                if delta_area > 0:
                    water_used = self.water_model.record_usage(
                        delta_area, mop_mode, mop_intensity, 0
                    )
                    waste_collected = self.waste_model.record_usage(water_used)
                    self.state.water_used_since_refill_ml += water_used
                    self.state.clean_water_used_since_waste_empty_ml += water_used
                    self.state.waste_collected_ml += waste_collected
        else:
            if self.state.cleaning_in_progress:
                self.state.cleaning_in_progress = False

        self.state.last_area = current_area
        self.state.last_cleaning_state = cleaning

        # Check water low / waste full alerts
        if self.water_remaining_pct <= self.water_low_threshold and not self.state.clean_warning_latched:
            self.state.clean_warning_latched = True
            self.reserve.update_clean_reserve(self.clean_capacity, self.state.water_used_since_refill_ml)

        if self.waste_tank_pct >= self.waste_full_threshold and not self.state.dirty_warning_latched:
            self.state.dirty_warning_latched = True
            self.reserve.update_dirty_reserve(self.dirty_capacity, self.state.waste_collected_ml)

        self.async_set_updated_data(self._build_data())
        self.hass.async_create_task(self._async_save())

    def _build_data(self) -> dict[str, Any]:
        """Build dictionary of all sensor states."""
        return {
            "water_remaining_pct": round(self.water_remaining_pct, 1),
            "water_remaining_ml": self.water_remaining_ml,
            "water_used_since_refill": round(self.state.water_used_since_refill_ml, 1),
            "waste_tank_pct": round(self.waste_tank_pct, 1),
            "waste_tank_ml": self.waste_tank_ml,
            "water_consumption_rate": self.water_consumption_rate,
            "dirty_water_fill_rate": self.dirty_water_fill_rate,
            "last_refill": self.state.last_refill,
            "last_waste_empty": self.state.last_waste_empty,
            "water_low": self.is_water_low,
            "waste_tank_full": self.is_waste_full,
            "diagnostics": {
                "learned_area_rate_ml_per_m2": self.water_model.base_consumption_rate,
                "learned_wash_volume_ml": self.water_model.learned_wash_volume_ml,
                "learned_waste_ratio": self.waste_model.waste_ratio,
                "clean_reserve_ml": self.reserve.clean_reserve_ml,
                "dirty_reserve_ml": self.reserve.dirty_reserve_ml,
                "effective_clean_capacity": self.reserve.effective_clean_capacity(self.clean_capacity),
                "effective_dirty_capacity": self.reserve.effective_dirty_capacity(self.dirty_capacity),
            },
        }

    async def async_refilled(self, actual_poured_ml: float | None = None) -> None:
        """Record clean water refill and calibrate model."""
        actual = (
            actual_poured_ml
            if actual_poured_ml is not None
            else self.state.water_used_since_refill_ml
        )
        self.water_model.calibrate(actual)
        self.state.water_used_since_refill_ml = 0.0
        self.state.clean_warning_latched = False
        self.state.last_refill = datetime.now(timezone.utc).isoformat()
        self.async_set_updated_data(self._build_data())
        await self._async_save()

    async def async_waste_emptied(self, actual_drained_ml: float | None = None) -> None:
        """Record dirty tank empty and calibrate waste ratio."""
        actual = (
            actual_drained_ml
            if actual_drained_ml is not None
            else self.state.waste_collected_ml
        )
        self.waste_model.calibrate(
            actual, self.state.clean_water_used_since_waste_empty_ml
        )
        self.state.waste_collected_ml = 0.0
        self.state.clean_water_used_since_waste_empty_ml = 0.0
        self.state.dirty_warning_latched = False
        self.state.last_waste_empty = datetime.now(timezone.utc).isoformat()
        self.async_set_updated_data(self._build_data())
        await self._async_save()

    async def async_clear_prediction_model(self) -> None:
        """Reset learned models to default."""
        self.water_model.reset_model()
        self.waste_model.reset_model()
        self.async_set_updated_data(self._build_data())
        await self._async_save()

    async def _async_save(self) -> None:
        """Persist current state."""
        await self.storage.async_save({
            "water_model": self.water_model.to_dict(),
            "waste_model": self.waste_model.to_dict(),
            "reserve_learning": self.reserve.to_dict(),
            "runtime_state": self.state.to_dict(),
        })

    async def async_unload(self) -> None:
        """Unload coordinator."""
        for unsub in self._unsub_trackers:
            unsub()
        self._unsub_trackers.clear()
