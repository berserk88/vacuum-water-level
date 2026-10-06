"""Data coordinator for Vacuum Water Level integration.

The coordinator is the runtime owner of all model mutation. It subscribes to
state changes for configured companion entities, updates the learning models,
and triggers reserve learning and calibration at the appropriate times.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant, State, callback
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
    detect_mop_washing,
    detect_refill,
    detect_waste_empty,
    detect_water_low,
    detect_waste_full,
    parse_dock_error_clean,
    parse_dock_error_dirty,
)
from .discovery import (
    get_bool_state,
    get_entity_state,
    get_float_state,
    get_str_state,
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


class VacuumWaterLevelCoordinator(DataUpdateCoordinator):
    """Coordinator for a single vacuum's water level tracking.

    Manages:
        - State change subscriptions for companion entities
        - Water consumption estimation
        - Waste water estimation
        - Reserve learning
        - Calibration on refill/empty events
        - Persistence via storage layer
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: Any,
        storage: VacuumWaterStorage,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            config_entry: Config entry with configuration.
            storage: Storage layer for persistence.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"Vacuum Water Level ({config_entry.entry_id})",
            update_interval=None,  # Event-driven, not polling
        )
        self.config_entry = config_entry
        self.storage = storage

        # Load models from storage
        data = storage.data
        self.water_model = WaterModel.from_dict(data.get("water_model"))
        self.waste_model = WasteModel.from_dict(data.get("waste_model"))
        self.reserve = ReserveLearning.from_dict(data.get("reserve_learning"))
        self.state = VacuumWaterState.from_dict(data.get("runtime_state"))

        # Track if a session is in progress
        self._session_area_start: float = 0.0
        self._session_wash_count: int = 0
        self._wash_was_active: bool = False

        # State change subscriptions
        self._unsub_trackers: list = []

        # Pending manual actions
        self._manual_refill_requested = False
        self._manual_empty_requested = False

        # Cached companion entity values
        self._cached_cleaning: bool | None = None
        self._cached_status: str | None = None
        self._cached_vacuum_state: str | None = None
        self._cached_area: float = 0.0
        self._cached_mop_mode: str | None = None
        self._cached_mop_intensity: str | None = None
        self._cached_dock_error_raw: str | None = None
        self._cached_clean_water_sensor: bool | None = None
        self._cached_dirty_water_sensor: bool | None = None

        self._last_update_time: datetime | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Return config entry data."""
        return self.config_entry.data

    @property
    def options(self) -> dict[str, Any]:
        """Return config entry options."""
        return self.config_entry.options

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value, checking options first then data."""
        if key in self.options:
            return self.options[key]
        if key in self.config:
            return self.config[key]
        return default

    @property
    def vacuum_entity_id(self) -> str:
        """Return the vacuum entity ID."""
        return self._get_config(CONF_VACUUM_ENTITY)

    @property
    def clean_tank_capacity(self) -> float:
        """Return clean tank capacity in mL."""
        return float(
            self._get_config(CONF_CLEAN_TANK_CAPACITY, DEFAULT_CLEAN_TANK_CAPACITY)
        )

    @property
    def dirty_tank_capacity(self) -> float:
        """Return dirty tank capacity in mL."""
        return float(
            self._get_config(CONF_DIRTY_TANK_CAPACITY, DEFAULT_DIRTY_TANK_CAPACITY)
        )

    @property
    def water_low_threshold(self) -> float:
        """Return water low threshold percentage."""
        return float(
            self._get_config(CONF_WATER_LOW_THRESHOLD, DEFAULT_WATER_LOW_THRESHOLD)
        )

    @property
    def waste_full_threshold(self) -> float:
        """Return waste full threshold percentage."""
        return float(
            self._get_config(CONF_WASTE_FULL_THRESHOLD, DEFAULT_WASTE_FULL_THRESHOLD)
        )

    @property
    def cleaning_entity(self) -> str | None:
        """Return cleaning entity ID."""
        return self._get_config(CONF_CLEANING_ENTITY)

    @property
    def area_entity(self) -> str | None:
        """Return area entity ID."""
        return self._get_config(CONF_AREA_ENTITY)

    @property
    def status_entity(self) -> str | None:
        """Return status entity ID."""
        return self._get_config(CONF_STATUS_ENTITY)

    @property
    def mop_mode_entity(self) -> str | None:
        """Return mop mode entity ID."""
        return self._get_config(CONF_MOP_MODE_ENTITY)

    @property
    def mop_intensity_entity(self) -> str | None:
        """Return mop intensity entity ID."""
        return self._get_config(CONF_MOP_INTENSITY_ENTITY)

    @property
    def dock_error_entity(self) -> str | None:
        """Return dock error entity ID."""
        return self._get_config(CONF_DOCK_ERROR_ENTITY)

    @property
    def clean_water_sensor(self) -> str | None:
        """Return clean water sensor entity ID."""
        return self._get_config(CONF_CLEAN_WATER_SENSOR)

    @property
    def dirty_water_sensor(self) -> str | None:
        """Return dirty water sensor entity ID."""
        return self._get_config(CONF_DIRTY_WATER_SENSOR)

    def get_effective_clean_capacity(self) -> float:
        """Return effective clean tank capacity (capacity - reserve)."""
        return self.reserve.effective_clean_capacity(self.clean_tank_capacity)

    def get_effective_dirty_capacity(self) -> float:
        """Return effective dirty tank capacity (capacity - reserve)."""
        return self.reserve.effective_dirty_capacity(self.dirty_tank_capacity)

    def get_water_remaining_pct(self) -> float:
        """Return predicted water remaining percentage."""
        return compute_water_remaining_pct(
            self.state.water_used_since_refill_ml,
            self.clean_tank_capacity,
            self.reserve.clean_reserve_ml,
        )

    def get_water_remaining_ml(self) -> float:
        """Return predicted water remaining in mL."""
        return compute_water_remaining_ml(
            self.state.water_used_since_refill_ml,
            self.clean_tank_capacity,
            self.reserve.clean_reserve_ml,
        )

    def get_waste_pct(self) -> float:
        """Return predicted waste tank fill percentage."""
        return compute_waste_pct(
            self.state.waste_collected_ml,
            self.dirty_tank_capacity,
            self.reserve.dirty_reserve_ml,
        )

    def get_waste_ml(self) -> float:
        """Return predicted waste tank fill in mL."""
        return compute_waste_ml(
            self.state.waste_collected_ml,
            self.dirty_tank_capacity,
            self.reserve.dirty_reserve_ml,
        )

    def get_water_low(self) -> tuple[bool, str]:
        """Return water low state and source.

        Uses parsed dock error to distinguish clean water issues from
        waste water issues.
        """
        dock_error_clean = parse_dock_error_clean(self._cached_dock_error_raw)
        return detect_water_low(
            self._cached_clean_water_sensor,
            dock_error_clean,
            self.get_water_remaining_pct(),
            self.water_low_threshold,
        )

    def get_waste_full(self) -> tuple[bool, str]:
        """Return waste full state and source.

        Uses parsed dock error to distinguish waste water issues from
        clean water issues.
        """
        dock_error_dirty = parse_dock_error_dirty(self._cached_dock_error_raw)
        return detect_waste_full(
            self._cached_dirty_water_sensor,
            dock_error_dirty,
            self.get_waste_pct(),
            self.waste_full_threshold,
        )

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic data."""
        return {
            "clean_reserve_ml": self.reserve.clean_reserve_ml,
            "dirty_reserve_ml": self.reserve.dirty_reserve_ml,
            "effective_capacity_ml": self.get_effective_clean_capacity(),
            "effective_dirty_capacity_ml": self.get_effective_dirty_capacity(),
            "water_model": self.water_model.to_dict(),
            "waste_model": self.waste_model.to_dict(),
            "reserve_learning": self.reserve.to_dict(),
            "configured_entities": {
                "vacuum_entity": self.vacuum_entity_id,
                "cleaning_entity": self.cleaning_entity,
                "area_entity": self.area_entity,
                "status_entity": self.status_entity,
                "mop_mode_entity": self.mop_mode_entity,
                "mop_intensity_entity": self.mop_intensity_entity,
                "dock_error_entity": self.dock_error_entity,
                "clean_water_sensor": self.clean_water_sensor,
                "dirty_water_sensor": self.dirty_water_sensor,
            },
            "runtime_state": self.state.to_dict(),
            "last_detection_sources": {
                "water_low_source": self.get_water_low()[1],
                "waste_full_source": self.get_waste_full()[1],
            },
        }

    def _refresh_cached_states(self) -> None:
        """Refresh all cached companion entity states."""
        # Vacuum state
        vacuum_state = get_entity_state(self.hass, self.vacuum_entity_id)
        self._cached_vacuum_state = get_str_state(vacuum_state) if vacuum_state else None

        # Cleaning binary sensor
        cleaning_state = get_entity_state(self.hass, self.cleaning_entity)
        self._cached_cleaning = get_bool_state(cleaning_state) if cleaning_state else None

        # Status sensor
        status_state = get_entity_state(self.hass, self.status_entity)
        self._cached_status = get_str_state(status_state) if status_state else None

        # Area sensor
        area_state = get_entity_state(self.hass, self.area_entity)
        new_area = get_float_state(area_state) if area_state else 0.0
        if new_area is not None:
            self._cached_area = new_area

        # Mop mode
        mop_mode_state = get_entity_state(self.hass, self.mop_mode_entity)
        self._cached_mop_mode = get_str_state(mop_mode_state) if mop_mode_state else None

        # Mop intensity
        mop_int_state = get_entity_state(self.hass, self.mop_intensity_entity)
        self._cached_mop_intensity = (
            get_str_state(mop_int_state) if mop_int_state else None
        )

        # Dock error - store raw text for parsing
        dock_err_state = get_entity_state(self.hass, self.dock_error_entity)
        if dock_err_state is not None:
            self._cached_dock_error_raw = dock_err_state.state
        else:
            self._cached_dock_error_raw = None

        # Clean water sensor
        clean_water_state = get_entity_state(self.hass, self.clean_water_sensor)
        self._cached_clean_water_sensor = (
            get_bool_state(clean_water_state) if clean_water_state else None
        )

        # Dirty water sensor
        dirty_water_state = get_entity_state(self.hass, self.dirty_water_sensor)
        self._cached_dirty_water_sensor = (
            get_bool_state(dirty_water_state) if dirty_water_state else None
        )

    def _is_cleaning(self) -> bool:
        """Determine if the vacuum is currently cleaning using priority detection."""
        return detect_cleaning(
            self._cached_cleaning,
            self._cached_status,
            self._cached_vacuum_state,
        )

    def _is_washing(self) -> bool:
        """Determine if the vacuum is washing its mop."""
        return detect_mop_washing(self._cached_status, self._cached_vacuum_state)

    def _get_provisional_session_usage(self) -> tuple[float, float, int]:
        """Compute provisional usage for the current cleaning session.

        Returns (area_delta, provisional_water_ml, wash_count) for the
        current in-progress session. Used when warnings fire during cleaning.
        """
        area_delta = self._cached_area - self._session_area_start
        if area_delta < 0:
            area_delta = self._cached_area
        wash_count = self._session_wash_count
        provisional = self.water_model.estimate_usage(
            area_delta,
            self._cached_mop_mode,
            self._cached_mop_intensity,
            wash_count,
        )
        return (area_delta, provisional, wash_count)

    def _checkpoint_session(self) -> None:
        """Checkpoint in-progress session usage for calibration.

        If a cleaning session is in progress and hasn't been checkpointed yet,
        finalize the provisional usage into the runtime state. This allows
        refill/empty calibration to have accurate data even when the cleaning
        session hasn't ended yet.

        The session is marked as checkpointed so that when it later ends,
        the usage isn't double-counted.
        """
        if not self.state.cleaning_in_progress or self.state.session_checkpointed:
            return

        area_delta, provisional, wash_count = self._get_provisional_session_usage()

        if provisional > 0:
            waste_provisional = self.waste_model.estimate_waste(provisional)
            self.state.water_used_since_refill_ml += provisional
            self.state.clean_water_used_since_waste_empty_ml += provisional
            self.state.waste_collected_ml += waste_provisional

        self.state.session_checkpointed = True

        _LOGGER.debug(
            "Vacuum Water Level: Session checkpointed. "
            "Provisional water: %.1f mL, waste: %.1f mL",
            provisional,
            self.waste_model.estimate_waste(provisional) if provisional > 0 else 0.0,
        )

    def _process_cleaning_cycle(self) -> None:
        """Process the current cleaning state and update water usage estimates."""
        is_cleaning = self._is_cleaning()
        is_washing = self._is_washing()

        # Track washing transitions (start of wash = one wash event)
        if is_washing and not self._wash_was_active:
            self._session_wash_count += 1
            self._wash_was_active = True
        elif not is_washing and self._wash_was_active:
            self._wash_was_active = False

        if not self.state.cleaning_in_progress and is_cleaning:
            # Cleaning session started
            self.state.cleaning_in_progress = True
            self._session_area_start = self._cached_area
            self._session_wash_count = 0
            _LOGGER.debug(
                "Vacuum Water Level: Cleaning session started for %s",
                self.vacuum_entity_id,
            )

        if self.state.cleaning_in_progress:
            if not is_cleaning:
                # Cleaning session ended - calculate usage
                # If session was already checkpointed (e.g., refill during cleaning),
                # skip adding usage again to avoid double-counting
                if not self.state.session_checkpointed:
                    area_delta = self._cached_area - self._session_area_start
                    if area_delta < 0:
                        area_delta = self._cached_area  # Area counter may have reset

                    wash_count = self._session_wash_count

                    # Estimate water usage
                    water_used = self.water_model.record_usage(
                        area_delta,
                        self._cached_mop_mode,
                        self._cached_mop_intensity,
                        wash_count,
                    )

                    # Estimate waste water
                    waste_generated = self.waste_model.record_usage(water_used)

                    # Update runtime state
                    self.state.water_used_since_refill_ml += water_used
                    self.state.clean_water_used_since_waste_empty_ml += water_used
                    self.state.waste_collected_ml += waste_generated
                    self.state.last_area = self._cached_area
                    self.state.last_mop_mode = self._cached_mop_mode
                    self.state.last_mop_intensity = self._cached_mop_intensity
                    self.state.wash_count = self.state.wash_count + wash_count

                    _LOGGER.debug(
                        "Vacuum Water Level: Cleaning session ended. "
                        "Area: %.1f m², Water: %.1f mL, Waste: %.1f mL, Washes: %d",
                        area_delta,
                        water_used,
                        waste_generated,
                        wash_count,
                    )
                else:
                    _LOGGER.debug(
                        "Vacuum Water Level: Cleaning session ended (already checkpointed)."
                    )

                self.state.cleaning_in_progress = False
                self.state.last_cleaning_state = False
                self.state.session_checkpointed = False

                self._persist()

        # Update last cleaning state
        self.state.last_cleaning_state = is_cleaning

        # Check for water low warning -> reserve learning
        self._check_water_low_warning()

        # Check for waste full warning -> reserve learning
        self._check_waste_full_warning()

        # Check for refill detection
        self._check_refill()

        # Check for waste empty detection
        self._check_waste_empty()

    def _check_water_low_warning(self) -> None:
        """Check for water low warning and learn reserve volume.

        If the warning fires during active cleaning, compute provisional usage
        so the reserve learning uses accurate data.

        Reserve learning only happens when the source is a real companion sensor
        (clean water sensor or dock error), NOT when the source is the prediction
        model. The prediction model can drive the binary sensor, but reserve
        volumes represent physical vacuum behaviour and must be learned from
        actual vacuum warnings.
        """
        is_low, source = self.get_water_low()

        if is_low and not self.state.clean_warning_latched:
            # Water low warning just triggered
            self.state.clean_warning_latched = True

            # Only learn reserve from real sensor sources, not prediction
            if source != "prediction_model":
                # Compute usage including any in-progress session
                total_used = self.state.water_used_since_refill_ml
                if self.state.cleaning_in_progress:
                    _, provisional, _ = self._get_provisional_session_usage()
                    total_used += provisional

                # Learn reserve volume (reserve learning before calibration)
                self.reserve.update_clean_reserve(
                    self.clean_tank_capacity,
                    total_used,
                )

                _LOGGER.debug(
                    "Vacuum Water Level: Water low warning detected. "
                    "Reserve: %.1f mL (source: %s, total_used: %.1f mL)",
                    self.reserve.clean_reserve_ml,
                    source,
                    total_used,
                )
            else:
                _LOGGER.debug(
                    "Vacuum Water Level: Water low predicted (source: %s). "
                    "Reserve not updated (prediction source).",
                    source,
                )

            self._persist()

        elif not is_low and self.state.clean_warning_latched:
            # Water low warning cleared - will be picked up by refill detection
            pass

    def _check_waste_full_warning(self) -> None:
        """Check for waste tank full warning and learn reserve volume.

        If the warning fires during active cleaning, compute provisional waste
        so the reserve learning uses accurate data.

        Reserve learning only happens when the source is a real companion sensor
        (dirty water sensor or dock error), NOT when the source is the prediction
        model.
        """
        is_full, source = self.get_waste_full()

        if is_full and not self.state.dirty_warning_latched:
            # Waste full warning just triggered
            self.state.dirty_warning_latched = True

            # Only learn reserve from real sensor sources, not prediction
            if source != "prediction_model":
                # Compute waste including any in-progress session
                total_waste = self.state.waste_collected_ml
                if self.state.cleaning_in_progress:
                    _, provisional, _ = self._get_provisional_session_usage()
                    total_waste += self.waste_model.estimate_waste(provisional)

                # Learn reserve volume
                self.reserve.update_dirty_reserve(
                    self.dirty_tank_capacity,
                    total_waste,
                )

                _LOGGER.debug(
                    "Vacuum Water Level: Waste tank full warning detected. "
                    "Reserve: %.1f mL (source: %s, total_waste: %.1f mL)",
                    self.reserve.dirty_reserve_ml,
                    source,
                    total_waste,
                )
            else:
                _LOGGER.debug(
                    "Vacuum Water Level: Waste full predicted (source: %s). "
                    "Reserve not updated (prediction source).",
                    source,
                )

            self._persist()

        elif not is_full and self.state.dirty_warning_latched:
            # Waste full warning cleared - will be picked up by empty detection
            pass

    def _check_refill(self) -> None:
        """Check for water refill and calibrate if detected.

        Refill is only detected when a prior water low warning was latched
        and the sensor/error has now cleared, or when the manual button is pressed.
        Calibration uses effective capacity (capacity - reserve) when a warning
        was latched, giving us the actual water consumed.
        """
        refill_detected, source = detect_refill(
            self._cached_clean_water_sensor,
            parse_dock_error_clean(self._cached_dock_error_raw),
            self._manual_refill_requested,
            warning_was_latched=self.state.clean_warning_latched,
        )

        if refill_detected:
            # Checkpoint in-progress session so calibration has accurate data
            self._checkpoint_session()

        if refill_detected and self.state.water_used_since_refill_ml > 0:
            # Refill detected - calibrate water model
            # When a warning was latched, actual usage = effective capacity
            # (what the vacuum considers empty after reserve)
            if self.state.clean_warning_latched:
                actual_usage = self.get_effective_clean_capacity()
            else:
                actual_usage = self.state.water_used_since_refill_ml

            self.water_model.calibrate(actual_usage)

            # Reset water tracking
            self.state.water_used_since_refill_ml = 0.0
            self.state.last_refill = datetime.now(timezone.utc).isoformat()
            self.state.clean_warning_latched = False
            self._manual_refill_requested = False

            _LOGGER.debug(
                "Vacuum Water Level: Refill detected (source: %s). "
                "Calibrated water model against %.1f mL. Cycles: %d",
                source,
                actual_usage,
                self.water_model.cycles_observed,
            )

            self._persist()

        elif refill_detected and self._manual_refill_requested:
            # Manual refill with no usage - just reset
            self.state.water_used_since_refill_ml = 0.0
            self.state.last_refill = datetime.now(timezone.utc).isoformat()
            self.state.clean_warning_latched = False
            self._manual_refill_requested = False
            self._persist()

    def _check_waste_empty(self) -> None:
        """Check for waste tank empty and calibrate if detected.

        Empty is only detected when a prior waste full warning was latched
        and the sensor/error has now cleared, or when the manual button is pressed.
        Calibration uses effective dirty capacity when a warning was latched.
        """
        empty_detected, source = detect_waste_empty(
            self._cached_dirty_water_sensor,
            parse_dock_error_dirty(self._cached_dock_error_raw),
            self._manual_empty_requested,
            warning_was_latched=self.state.dirty_warning_latched,
        )

        if empty_detected:
            # Checkpoint in-progress session so calibration has accurate data
            self._checkpoint_session()

        if empty_detected and self.state.waste_collected_ml > 0:
            # Waste tank emptied - calibrate waste model
            # When a warning was latched, actual waste = effective dirty capacity
            if self.state.dirty_warning_latched:
                actual_waste = self.get_effective_dirty_capacity()
            else:
                actual_waste = self.state.waste_collected_ml

            # Use clean water used since waste empty as reference
            clean_water_reference = self.state.clean_water_used_since_waste_empty_ml

            self.waste_model.calibrate(actual_waste, clean_water_reference)

            # Reset waste tracking
            self.state.waste_collected_ml = 0.0
            self.state.clean_water_used_since_waste_empty_ml = 0.0
            self.state.last_waste_empty = datetime.now(timezone.utc).isoformat()
            self.state.dirty_warning_latched = False
            self._manual_empty_requested = False

            _LOGGER.debug(
                "Vacuum Water Level: Waste empty detected (source: %s). "
                "Calibrated waste model against %.1f mL. Cycles: %d",
                source,
                actual_waste,
                self.waste_model.cycles_observed,
            )

            self._persist()

        elif empty_detected and self._manual_empty_requested:
            # Manual empty with no waste - just reset
            self.state.waste_collected_ml = 0.0
            self.state.clean_water_used_since_waste_empty_ml = 0.0
            self.state.last_waste_empty = datetime.now(timezone.utc).isoformat()
            self.state.dirty_warning_latched = False
            self._manual_empty_requested = False
            self._persist()

    def _persist(self) -> None:
        """Persist all models and state to storage."""
        self.storage.update_water_model(self.water_model)
        self.storage.update_waste_model(self.waste_model)
        self.storage.update_reserve_learning(self.reserve)
        self.storage.update_runtime_state(self.state)
        self.storage.async_delay_save()

    def manual_refill(self) -> None:
        """Handle manual refill button press."""
        self._manual_refill_requested = True
        self._process_cleaning_cycle()
        # If refill wasn't detected via sensors, force it
        if self._manual_refill_requested:
            if self.state.clean_warning_latched:
                actual_usage = self.get_effective_clean_capacity()
            else:
                actual_usage = self.state.water_used_since_refill_ml
            if actual_usage > 0:
                self.water_model.calibrate(actual_usage)
            self.state.water_used_since_refill_ml = 0.0
            self.state.last_refill = datetime.now(timezone.utc).isoformat()
            self.state.clean_warning_latched = False
            self._manual_refill_requested = False
            self._persist()
        self.async_set_updated_data(self.get_diagnostics())

    def manual_waste_empty(self) -> None:
        """Handle manual waste empty button press."""
        self._manual_empty_requested = True
        self._process_cleaning_cycle()
        if self._manual_empty_requested:
            if self.state.dirty_warning_latched:
                actual_waste = self.get_effective_dirty_capacity()
            else:
                actual_waste = self.state.waste_collected_ml
            clean_water_reference = self.state.clean_water_used_since_waste_empty_ml
            if actual_waste > 0 and clean_water_reference > 0:
                self.waste_model.calibrate(actual_waste, clean_water_reference)
            self.state.waste_collected_ml = 0.0
            self.state.clean_water_used_since_waste_empty_ml = 0.0
            self.state.last_waste_empty = datetime.now(timezone.utc).isoformat()
            self.state.dirty_warning_latched = False
            self._manual_empty_requested = False
            self._persist()
        self.async_set_updated_data(self.get_diagnostics())

    def clear_prediction_model(self) -> None:
        """Handle clear prediction model button press.

        Resets water_model and waste_model but preserves:
            - clean_reserve_ml
            - dirty_reserve_ml
            - warning_cycles
        """
        self.water_model.reset_model()
        self.waste_model.reset_model()
        # Do NOT reset reserve learning - it represents physical vacuum behavior
        self._persist()
        _LOGGER.debug("Vacuum Water Level: Prediction models cleared")
        self.async_set_updated_data(self.get_diagnostics())

    @callback
    def _on_state_change(self, event: Any) -> None:
        """Handle state change events for companion entities.

        This is called whenever any tracked entity changes state.
        """
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            return

        entity_id = new_state.entity_id

        _LOGGER.debug(
            "Vacuum Water Level: State change for %s: %s -> %s",
            entity_id,
            old_state.state if old_state else "None",
            new_state.state,
        )

        # Refresh cached states
        self._refresh_cached_states()

        # Process the cleaning cycle
        self._process_cleaning_cycle()

        # Update coordinator data to trigger entity updates
        self.async_set_updated_data(self.get_diagnostics())

    async def async_setup(self) -> None:
        """Set up the coordinator.

        Subscribes to state changes for all configured companion entities.
        """
        # Initial refresh of cached states
        self._refresh_cached_states()

        # Collect all entity IDs to track
        tracked_entities = [self.vacuum_entity_id]

        for entity_attr in [
            "cleaning_entity",
            "area_entity",
            "status_entity",
            "mop_mode_entity",
            "mop_intensity_entity",
            "dock_error_entity",
            "clean_water_sensor",
            "dirty_water_sensor",
        ]:
            entity_id = getattr(self, entity_attr)
            if entity_id and entity_id not in tracked_entities:
                tracked_entities.append(entity_id)

        # Subscribe to state changes
        unsub = async_track_state_change_event(
            self.hass,
            tracked_entities,
            self._on_state_change,
        )
        self._unsub_trackers.append(unsub)

        _LOGGER.debug(
            "Vacuum Water Level: Tracking %d entities for %s",
            len(tracked_entities),
            self.vacuum_entity_id,
        )

        # Initial processing
        self._process_cleaning_cycle()

    async def async_shutdown(self) -> None:
        """Shut down the coordinator.

        Unsubscribes from state changes and persists final state.
        """
        for unsub in self._unsub_trackers:
            unsub()
        self._unsub_trackers.clear()

        # Final persist
        self._persist()
        await self.storage.async_save()
