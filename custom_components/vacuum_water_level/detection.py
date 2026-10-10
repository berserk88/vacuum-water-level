"""Central detection logic for cleaning state, water low, and waste full.

This module implements the priority-based detection described in the spec.
It is pure Python and unit-testable without Home Assistant.
"""

from __future__ import annotations

from typing import Any


def detect_cleaning(
    cleaning_entity_state: bool | None,
    status_entity_value: str | None,
    vacuum_state: str | None,
) -> bool:
    """Detect whether the vacuum is currently cleaning.

    Priority order:
        1. Dedicated cleaning binary sensor
        2. Status sensor (check for cleaning-related states)
        3. Vacuum state entity (check for cleaning states)
        4. Fallback (return False)

    Args:
        cleaning_entity_state: State of the cleaning binary sensor, or None.
        status_entity_value: Value of the status sensor, or None.
        vacuum_state: State string from the vacuum entity, or None.

    Returns:
        True if the vacuum appears to be cleaning.
    """
    # Priority 1: dedicated cleaning binary sensor
    if cleaning_entity_state is not None:
        return cleaning_entity_state

    # Priority 2: status sensor
    if status_entity_value is not None:
        return _is_status_cleaning(status_entity_value)

    # Priority 3: vacuum state
    if vacuum_state is not None:
        return _is_vacuum_cleaning(vacuum_state)

    # Priority 4: fallback
    return False


def _is_status_cleaning(status: str) -> bool:
    """Check if a status string indicates cleaning."""
    status_lower = str(status).lower().strip()
    cleaning_statuses = {
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
        "returning_to_dock",
        "charging",  # Some vacuums report charging while at dock between cleaning segments
    }
    # Only return True for active cleaning states
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
    """Check if a vacuum state indicates cleaning.

    Home Assistant vacuum states:
    - cleaning
    - docked
    - returning
    - error
    - paused
    - idle
    """
    state_lower = str(state).lower().strip()
    return state_lower == "cleaning"


def detect_water_low(
    clean_water_sensor_state: bool | None,
    dock_error_state: bool | None,
    predicted_remaining_pct: float,
    threshold_pct: float,
) -> tuple[bool, str]:
    """Detect water low condition.

    Priority order:
        1. Clean water box binary sensor
        2. Dock error sensor
        3. Prediction model (based on estimated remaining)

    Args:
        clean_water_sensor_state: State of clean water box sensor (True = water low/empty).
            None if not configured.
        dock_error_state: State of dock error sensor (True = error).
            None if not configured.
        predicted_remaining_pct: Predicted water remaining percentage.
        threshold_pct: Threshold percentage for water low warning.

    Returns:
        Tuple of (is_water_low, source) where source is the detection method used.
    """
    # Priority 1: clean water box sensor
    if clean_water_sensor_state is not None:
        return (clean_water_sensor_state, "clean_water_sensor")

    # Priority 2: dock error sensor
    if dock_error_state is not None:
        # Dock error may indicate water low
        return (dock_error_state, "dock_error_sensor")

    # Priority 3: prediction model
    is_low = predicted_remaining_pct <= threshold_pct
    return (is_low, "prediction_model")


def detect_waste_full(
    dirty_water_sensor_state: bool | None,
    dock_error_state: bool | None,
    predicted_waste_pct: float,
    threshold_pct: float,
) -> tuple[bool, str]:
    """Detect waste tank full condition.

    Priority order:
        1. Dirty water box binary sensor
        2. Dock error sensor
        3. Prediction model

    Args:
        dirty_water_sensor_state: State of dirty water box sensor (True = tank full).
            None if not configured.
        dock_error_state: State of dock error sensor (True = error).
            None if not configured.
        predicted_waste_pct: Predicted waste tank fill percentage.
        threshold_pct: Threshold percentage for waste full warning.

    Returns:
        Tuple of (is_waste_full, source) where source is the detection method used.
    """
    # Priority 1: dirty water box sensor
    if dirty_water_sensor_state is not None:
        return (dirty_water_sensor_state, "dirty_water_sensor")

    # Priority 2: dock error sensor
    if dock_error_state is not None:
        return (dock_error_state, "dock_error_sensor")

    # Priority 3: prediction model
    is_full = predicted_waste_pct >= threshold_pct
    return (is_full, "prediction_model")


def detect_refill(
    clean_water_sensor_state: bool | None,
    dock_error_state: bool | None,
    manual_refill: bool = False,
    warning_was_latched: bool = False,
) -> tuple[bool, str]:
    """Detect whether the clean water tank has been refilled.

    Priority order:
        1. Clean water binary sensor clears (was warning, now clear)
        2. Dock error clears (was error, now clear)
        3. Manual refill button

    A refill is only detected if there was a prior warning (latched) and the
    sensor/error has now cleared, or if the manual refill button was pressed.
    This prevents false refills when the sensor is normally clear.

    Args:
        clean_water_sensor_state: Current state of clean water sensor (True = low).
            None if not configured.
        dock_error_state: Current dock error state.
            None if not configured.
        manual_refill: Whether the manual refill button was pressed.
        warning_was_latched: Whether a water low warning was previously latched.

    Returns:
        Tuple of (refill_detected, source).
    """
    # Priority 1: clean water sensor clears after a warning
    if clean_water_sensor_state is not None:
        if warning_was_latched and not clean_water_sensor_state:
            return (True, "clean_water_sensor_cleared")
        return (False, "clean_water_sensor")

    # Priority 2: dock error clears after a warning
    if dock_error_state is not None:
        if warning_was_latched and not dock_error_state:
            return (True, "dock_error_cleared")
        return (False, "dock_error_sensor")

    # Priority 3: manual refill button
    if manual_refill:
        return (True, "manual_refill")

    return (False, "none")


def detect_waste_empty(
    dirty_water_sensor_state: bool | None,
    dock_error_state: bool | None,
    manual_empty: bool = False,
    warning_was_latched: bool = False,
) -> tuple[bool, str]:
    """Detect whether the waste tank has been emptied.

    Priority order:
        1. Dirty water binary sensor clears (was full, now clear)
        2. Dock full error clears (was error, now clear)
        3. Manual empty button

    An empty is only detected if there was a prior waste full warning (latched)
    and the sensor/error has now cleared, or if the manual empty button was pressed.

    Args:
        dirty_water_sensor_state: Current state of dirty water sensor (True = full).
            None if not configured.
        dock_error_state: Current dock error state.
            None if not configured.
        manual_empty: Whether the manual empty button was pressed.
        warning_was_latched: Whether a waste full warning was previously latched.

    Returns:
        Tuple of (empty_detected, source).
    """
    # Priority 1: dirty water sensor clears after a warning
    if dirty_water_sensor_state is not None:
        if warning_was_latched and not dirty_water_sensor_state:
            return (True, "dirty_water_sensor_cleared")
        return (False, "dirty_water_sensor")

    # Priority 2: dock error clears after a warning
    if dock_error_state is not None:
        if warning_was_latched and not dock_error_state:
            return (True, "dock_full_error_cleared")
        return (False, "dock_error_sensor")

    # Priority 3: manual empty button
    if manual_empty:
        return (True, "manual_empty")

    return (False, "none")


def detect_mop_washing(
    status_entity_value: str | None,
    vacuum_state: str | None,
) -> bool:
    """Detect if the vacuum is currently washing its mop.

    Checks status sensor and vacuum state for washing-related keywords.

    Args:
        status_entity_value: Value of the status sensor, or None.
        vacuum_state: State string from the vacuum entity, or None.

    Returns:
        True if mop washing is detected.
    """
    washing_keywords = {
        "washing",
        "mop_washing",
        "washing_mop",
        "dock_washing",
        "cleaning_mop",
        "mop_cleaning",
        "auto_washing",
        "washing_mops",
    }

    if status_entity_value is not None:
        status_lower = str(status_entity_value).lower().strip()
        if status_lower in washing_keywords:
            return True
        # Also check if "wash" is in the status
        if "wash" in status_lower and "mop" not in status_lower:
            return True

    if vacuum_state is not None:
        state_lower = str(vacuum_state).lower().strip()
        if state_lower in washing_keywords:
            return True

    return False


# Dock error parsing keywords
CLEAN_WATER_ERROR_KEYWORDS = [
    "clean water",
    "clean_water",
    "water box",
    "water_box",
    "water tank",
    "water_tank",
    "water low",
    "water_low",
    "water empty",
    "water_empty",
    "water missing",
    "water_missing",
    "no water",
    "water insufficient",
]

DIRTY_WATER_ERROR_KEYWORDS = [
    "dirty water",
    "dirty_water",
    "waste water",
    "waste_water",
    "waste tank",
    "waste_tank",
    "dirty tank",
    "dirty_tank",
    "dirty box",
    "dirty_box",
    "waste full",
    "waste_full",
    "dirty full",
    "dirty_full",
    "tank full",
    "tank_full",
]


def parse_dock_error_clean(dock_error_raw: str | None) -> bool | None:
    """Parse dock error state for clean water issues.

    Checks if the dock error text indicates a clean water problem
    (empty, low, missing). Returns True if clean water issue detected,
    False if the error text doesn't mention clean water, None if no input.

    Args:
        dock_error_raw: Raw dock error state string, or None.

    Returns:
        True if clean water issue, False if not, None if no input.
    """
    if dock_error_raw is None:
        return None
    text = str(dock_error_raw).lower().strip()
    if text in ("off", "false", "0", "no", "ok", "normal", "none", ""):
        return False
    # Check for clean water keywords
    for keyword in CLEAN_WATER_ERROR_KEYWORDS:
        if keyword in text:
            return True
    # Check if it's a generic error (on/true) without specific water mention
    if text in ("on", "true", "1", "yes", "error", "problem", "active"):
        # Generic dock error - could be water or waste, treat as both
        return True
    return False


def parse_dock_error_dirty(dock_error_raw: str | None) -> bool | None:
    """Parse dock error state for dirty/waste water issues.

    Checks if the dock error text indicates a dirty/waste water problem
    (tank full). Returns True if dirty water issue detected,
    False if the error text doesn't mention dirty water, None if no input.

    Args:
        dock_error_raw: Raw dock error state string, or None.

    Returns:
        True if dirty water issue, False if not, None if no input.
    """
    if dock_error_raw is None:
        return None
    text = str(dock_error_raw).lower().strip()
    if text in ("off", "false", "0", "no", "ok", "normal", "none", ""):
        return False
    # Check for dirty water keywords
    for keyword in DIRTY_WATER_ERROR_KEYWORDS:
        if keyword in text:
            return True
    # Check if it's a generic error (on/true) without specific mention
    if text in ("on", "true", "1", "yes", "error", "problem", "active"):
        # Generic dock error - could be water or waste, treat as both
        return True
    return False
