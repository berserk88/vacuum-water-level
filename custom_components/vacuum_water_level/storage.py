"""Storage layer for Vacuum Water Level integration.

Uses Home Assistant's storage helper for persistence.
All data is stored per config entry, keyed by entry ID.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION, STORAGE_MINOR_VERSION
from .learning import (
    ReserveLearning,
    VacuumWaterState,
    WaterModel,
    WasteModel,
)

_LOGGER = logging.getLogger(__name__)

# Current data schema version
DATA_VERSION = 1


class VacuumWaterStorage:
    """Manages persistent storage for a single vacuum config entry.

    Stores:
        - water_model: Adaptive clean water consumption model
        - waste_model: Adaptive waste water model
        - reserve_learning: Learned reserve volumes
        - runtime_state: Runtime tracking state
        - version: Schema version for migrations
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage for a config entry.

        Args:
            hass: Home Assistant instance.
            entry_id: Config entry ID (stable across entity renames).
        """
        self._hass = hass
        self._entry_id = entry_id
        self._store: Store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage, applying migrations if needed.

        Returns:
            The loaded (and possibly migrated) data dictionary.
        """
        raw = await self._store.async_load()
        if raw is None:
            # First run - initialize defaults
            self._data = self._default_data()
        else:
            self._data = self._migrate(raw)

        return self._data

    def _default_data(self) -> dict[str, Any]:
        """Return default data structure for a new vacuum."""
        return {
            "version": DATA_VERSION,
            "water_model": WaterModel().to_dict(),
            "waste_model": WasteModel().to_dict(),
            "reserve_learning": ReserveLearning().to_dict(),
            "runtime_state": VacuumWaterState().to_dict(),
        }

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate data from older schema versions.

        Args:
            data: Raw loaded data.

        Returns:
            Migrated data matching current schema.
        """
        version = data.get("version", 0)

        if version < 1:
            # Migration from v0 (pre-versioned) to v1
            _LOGGER.info(
                "Vacuum Water Level: Migrating storage from v%d to v%d for entry %s",
                version,
                DATA_VERSION,
                self._entry_id,
            )
            # Ensure all required keys exist
            if "water_model" not in data:
                data["water_model"] = WaterModel().to_dict()
            if "waste_model" not in data:
                data["waste_model"] = WasteModel().to_dict()
            if "reserve_learning" not in data:
                data["reserve_learning"] = ReserveLearning().to_dict()
            if "runtime_state" not in data:
                data["runtime_state"] = VacuumWaterState().to_dict()

            # Ensure water_model has all correction factors
            wm = data["water_model"]
            if "correction_factors" not in wm:
                wm["correction_factors"] = {}
            if "area_ml_per_m2" not in wm["correction_factors"]:
                wm["correction_factors"]["area_ml_per_m2"] = 2.0
            if "mop_intensity_multiplier" not in wm["correction_factors"]:
                wm["correction_factors"]["mop_intensity_multiplier"] = {
                    "low": 0.7,
                    "medium": 1.0,
                    "high": 1.3,
                    "max": 1.5,
                }
            if "wash_volume_ml" not in wm["correction_factors"]:
                wm["correction_factors"]["wash_volume_ml"] = 50.0

            # Ensure waste_model has waste_ratio
            wsm = data["waste_model"]
            if "correction_factors" not in wsm:
                wsm["correction_factors"] = {}
            if "waste_ratio" not in wsm["correction_factors"]:
                wsm["correction_factors"]["waste_ratio"] = 0.9

            # Ensure reserve_learning has all fields
            rl = data["reserve_learning"]
            rl.setdefault("clean_reserve_ml", 0.0)
            rl.setdefault("dirty_reserve_ml", 0.0)
            rl.setdefault("warning_cycles", 0)

            # Ensure runtime_state has all fields
            rs = data["runtime_state"]
            rs.setdefault("water_used_since_refill_ml", 0.0)
            rs.setdefault("waste_collected_ml", 0.0)
            rs.setdefault("clean_water_used_since_waste_empty_ml", 0.0)
            rs.setdefault("last_refill", None)
            rs.setdefault("last_waste_empty", None)
            rs.setdefault("clean_warning_latched", False)
            rs.setdefault("dirty_warning_latched", False)
            rs.setdefault("last_cleaning_state", False)
            rs.setdefault("last_area", 0.0)
            rs.setdefault("last_mop_mode", None)
            rs.setdefault("last_mop_intensity", None)
            rs.setdefault("wash_count", 0)
            rs.setdefault("cleaning_in_progress", False)
            rs.setdefault("session_start_area", 0.0)
            rs.setdefault("session_checkpointed", False)

            data["version"] = DATA_VERSION

        # Future migrations would go here:
        # if version < 2: ...

        return data

    async def async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self._data)

    def async_delay_save(self, delay: int = 5) -> None:
        """Save data with a delay to batch multiple writes.

        This is synchronous - it delegates to the Store's async_delay_save
        which schedules the save on the event loop.

        Args:
            delay: Seconds to wait before writing.
        """
        self._store.async_delay_save(self._save_data, delay)

    def _save_data(self) -> dict[str, Any]:
        """Return data for delayed save."""
        return dict(self._data)

    @property
    def data(self) -> dict[str, Any]:
        """Return current data."""
        return self._data

    def get_water_model(self) -> WaterModel:
        """Get the water model."""
        return WaterModel.from_dict(self._data.get("water_model"))

    def get_waste_model(self) -> WasteModel:
        """Get the waste model."""
        return WasteModel.from_dict(self._data.get("waste_model"))

    def get_reserve_learning(self) -> ReserveLearning:
        """Get reserve learning."""
        return ReserveLearning.from_dict(self._data.get("reserve_learning"))

    def get_runtime_state(self) -> VacuumWaterState:
        """Get runtime state."""
        return VacuumWaterState.from_dict(self._data.get("runtime_state"))

    def update_water_model(self, model: WaterModel) -> None:
        """Update the water model in storage."""
        self._data["water_model"] = model.to_dict()

    def update_waste_model(self, model: WasteModel) -> None:
        """Update the waste model in storage."""
        self._data["waste_model"] = model.to_dict()

    def update_reserve_learning(self, reserve: ReserveLearning) -> None:
        """Update reserve learning in storage."""
        self._data["reserve_learning"] = reserve.to_dict()

    def update_runtime_state(self, state: VacuumWaterState) -> None:
        """Update runtime state in storage."""
        self._data["runtime_state"] = state.to_dict()

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic data for the diagnostics sensor."""
        water_model = self.get_water_model()
        waste_model = self.get_waste_model()
        reserve = self.get_reserve_learning()

        return {
            "water_model": water_model.to_dict(),
            "waste_model": waste_model.to_dict(),
            "reserve_learning": reserve.to_dict(),
            "storage_version": self._data.get("version", DATA_VERSION),
        }
