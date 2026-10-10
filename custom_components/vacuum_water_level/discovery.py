"""Heuristic companion entity discovery for robot vacuums."""

from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant


def get_entity_state(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Get entity state safely."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    return state.state if state else None


def get_bool_state(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    """Get entity boolean state."""
    st = get_entity_state(hass, entity_id)
    if st is None:
        return None
    return st.lower() in ("on", "true", "1", "problem")


def get_float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Get entity float state."""
    st = get_entity_state(hass, entity_id)
    if st is None:
        return None
    try:
        return float(st)
    except (ValueError, TypeError):
        return None


def get_str_state(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Get entity string state."""
    return get_entity_state(hass, entity_id)
