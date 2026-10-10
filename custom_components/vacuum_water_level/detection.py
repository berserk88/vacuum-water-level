"""Central detection logic for cleaning state, water low, and waste full."""

from __future__ import annotations

from typing import Any


def detect_cleaning(
    cleaning_entity_state: bool | None,
    status_entity_value: str | None,
    vacuum_state: str | None,
) -> bool:
    """Detect whether the vacuum is currently cleaning."""
    if cleaning_entity_state is not None:
        return cleaning_entity_state

    if status_entity_value is not None:
        return _is_status_cleaning(status_entity_value)

    if vacuum_state is not None:
        return _is_vacuum_cleaning(vacuum_state)

    return False


def _is_status_cleaning(status: str) -> bool:
    """Check if a status string indicates cleaning."""
    status_lower = str(status).lower().strip()
    active_cleaning = {
        "cleaning",
        "mopping",
        "sweeping",
        "working",
        "in_cleaning",
        "cleaning_up",
        "segment_cleaning",
        "spot_cleaning",
        "auto_cleaning",
        "quick_build_map",
        "mapping",
        "zoned_cleaning",
    }
    return status_lower in active_cleaning


def _is_vacuum_cleaning(state: str) -> bool:
    """Check if a vacuum state indicates cleaning."""
    state_lower = str(state).lower().strip()
    return state_lower == "cleaning"


def detect_water_low(
    sensor_state: bool | None,
    dock_error_clean: bool,
    water_remaining_pct: float,
    threshold_pct: float,
    latched: bool,
) -> bool:
    """Detect clean water low state."""
    if sensor_state is True:
        return True
    if dock_error_clean:
        return True
    if water_remaining_pct <= threshold_pct:
        return True
    return latched


def detect_waste_full(
    sensor_state: bool | None,
    dock_error_dirty: bool,
    waste_pct: float,
    threshold_pct: float,
    latched: bool,
) -> bool:
    """Detect dirty water tank full state."""
    if sensor_state is True:
        return True
    if dock_error_dirty:
        return True
    if waste_pct >= threshold_pct:
        return True
    return latched


def parse_dock_error_clean(dock_error: str | None) -> bool:
    """Parse dock error status for clean water empty."""
    if not dock_error:
        return False
    lower = str(dock_error).lower()
    keywords = [
        "water_box_empty",
        "clean_water_empty",
        "water_empty",
        "low_water",
        "no_water",
        "water_box_not_installed",
        "clean_tank_empty",
        "insufficient_water",
        "clean_water_tank_empty",
    ]
    return any(kw in lower for kw in keywords)


def parse_dock_error_dirty(dock_error: str | None) -> bool:
    """Parse dock error status for waste tank full."""
    if not dock_error:
        return False
    lower = str(dock_error).lower()
    keywords = [
        "dirty_box_full",
        "waste_tank_full",
        "waste_full",
        "dirty_water_full",
        "dirty_box_not_installed",
        "sewage_tank_full",
        "dirty_tank_full",
    ]
    return any(kw in lower for kw in keywords)
