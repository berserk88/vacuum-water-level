"""Companion entity auto-discovery for vacuum water tracking.

This module discovers companion entities for a given vacuum entity using
heuristic scoring. It is vendor-neutral and does not hardcode any
vendor-specific entity IDs. It scores candidates by:
    - Same device (via entity registry)
    - Entity domain (binary_sensor, select, sensor)
    - Entity name/ID substring matching
    - Device class matching

Roborock entity names like 'binary_sensor.roborock_qrevo_maxv_cleaning' are
used as examples in documentation only, never hardcoded in logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityCandidate:
    """A discovered companion entity candidate."""

    entity_id: str
    confidence: float  # 0.0 to 1.0
    reason: str


# Substring patterns for entity discovery
# These are generic keywords, not vendor-specific entity IDs
CLEANING_PATTERNS = ["cleaning", "is_cleaning", "cleaning_state"]
AREA_PATTERNS = ["cleaned_area", "area_cleaned", "clean_area", "cleanedarea", "area"]
STATUS_PATTERNS = ["status", "state", "activity", "work_mode"]
MOP_MODE_PATTERNS = ["mop_mode", "mopmode", "mopping_mode"]
MOP_INTENSITY_PATTERNS = [
    "mop_intensity",
    "mopintensity",
    "water_volume",
    "water_flow",
    "mop_water",
]
DOCK_ERROR_PATTERNS = ["dock_error", "dock_status", "error", "fault", "warning"]
CLEAN_WATER_PATTERNS = [
    "clean_water",
    "cleanwater",
    "water_box",
    "waterbox",
    "clean_water_box",
    "water_level",
]
DIRTY_WATER_PATTERNS = [
    "dirty_water",
    "dirtywater",
    "waste_water",
    "wastewater",
    "dirty_box",
    "dirty_water_box",
    "waste_tank",
    "dirty_tank",
]


def _get_vacuum_slug(entity_id: str) -> str:
    """Extract the slug stem from a vacuum entity ID.

    Example: 'vacuum.roborock_qrevo_maxv' -> 'roborock_qrevo_maxv'

    Args:
        entity_id: The vacuum entity ID.

    Returns:
        The slug stem without the domain prefix.
    """
    if "." in entity_id:
        return entity_id.split(".", 1)[1]
    return entity_id


def _score_entity(
    entity_id: str,
    entity_name: str | None,
    patterns: list[str],
    vacuum_slug: str,
) -> tuple[float, str]:
    """Score an entity candidate by how well it matches.

    Args:
        entity_id: The candidate entity ID.
        entity_name: The friendly name of the entity, or None.
        patterns: Substring patterns to match against.
        vacuum_slug: The vacuum's slug stem for same-device scoring.

    Returns:
        Tuple of (score, reason).
    """
    score = 0.0
    reasons: list[str] = []

    # Check if entity belongs to the same device (slug match)
    candidate_slug = _get_vacuum_slug(entity_id)
    if vacuum_slug and vacuum_slug in candidate_slug:
        score += 0.3
        reasons.append("same_device")

    # Check pattern matching in entity ID
    entity_lower = entity_id.lower()
    for pattern in patterns:
        if pattern in entity_lower:
            score += 0.4
            reasons.append(f"pattern_match:{pattern}")
            break

    # Check pattern matching in entity name
    if entity_name:
        name_lower = entity_name.lower()
        for pattern in patterns:
            if pattern in name_lower:
                score += 0.3
                reasons.append(f"name_match:{pattern}")
                break

    # Bonus for both slug match and pattern match
    if score >= 0.7:
        score = min(score + 0.1, 1.0)

    reason = ",".join(reasons) if reasons else ""
    return (score, reason)


def discover_companion_entities(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, EntityCandidate | None]:
    """Discover companion entities for a vacuum.

    Args:
        hass: Home Assistant instance.
        vacuum_entity_id: The vacuum entity ID to discover companions for.

    Returns:
        Dictionary mapping companion type to the best EntityCandidate, or None.
        Keys: cleaning, area, status, mop_mode, mop_intensity, dock_error,
              clean_water, dirty_water
    """
    vacuum_slug = _get_vacuum_slug(vacuum_entity_id)

    # Gather all candidate entities
    try:
        from homeassistant.helpers import entity_registry as er
        ent_reg = er.async_get(hass)
    except Exception as err:
        _LOGGER.warning("Vacuum Water Level: Could not access entity registry: %s", err)
        ent_reg = None
    candidates_by_type: dict[str, list[EntityCandidate]] = {
        "cleaning": [],
        "area": [],
        "status": [],
        "mop_mode": [],
        "mop_intensity": [],
        "dock_error": [],
        "clean_water": [],
        "dirty_water": [],
    }

    pattern_map = {
        "cleaning": CLEANING_PATTERNS,
        "area": AREA_PATTERNS,
        "status": STATUS_PATTERNS,
        "mop_mode": MOP_MODE_PATTERNS,
        "mop_intensity": MOP_INTENSITY_PATTERNS,
        "dock_error": DOCK_ERROR_PATTERNS,
        "clean_water": CLEAN_WATER_PATTERNS,
        "dirty_water": DIRTY_WATER_PATTERNS,
    }

    domain_map = {
        "cleaning": {"binary_sensor", "sensor"},
        "area": {"sensor"},
        "status": {"sensor"},
        "mop_mode": {"select", "sensor"},
        "mop_intensity": {"select", "sensor"},
        "dock_error": {"binary_sensor", "sensor"},
        "clean_water": {"binary_sensor", "sensor"},
        "dirty_water": {"binary_sensor", "sensor"},
    }

    # Iterate through entity registry
    if ent_reg is not None:
        for entity_entry in ent_reg.entities.values():
            entity_id = entity_entry.entity_id
            domain = entity_id.split(".")[0] if "." in entity_id else ""

            for comp_type, patterns in pattern_map.items():
                if domain not in domain_map[comp_type]:
                    continue

                score, reason = _score_entity(
                    entity_id,
                    entity_entry.name or entity_entry.original_name,
                    patterns,
                    vacuum_slug,
                )

                if score > 0:
                    candidates_by_type[comp_type].append(
                        EntityCandidate(
                            entity_id=entity_id,
                            confidence=score,
                            reason=reason,
                        )
                    )

    # Also check states for entities not in registry
    all_states = hass.states.async_all()
    for state in all_states:
        entity_id = state.entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        friendly_name = state.name

        for comp_type, patterns in pattern_map.items():
            if domain not in domain_map[comp_type]:
                continue

            # Skip if already found via entity registry
            if any(c.entity_id == entity_id for c in candidates_by_type[comp_type]):
                continue

            score, reason = _score_entity(
                entity_id,
                friendly_name,
                patterns,
                vacuum_slug,
            )

            if score > 0:
                candidates_by_type[comp_type].append(
                    EntityCandidate(
                        entity_id=entity_id,
                        confidence=score,
                        reason=reason,
                    )
                )

    # Select best candidate for each type
    result: dict[str, EntityCandidate | None] = {}
    for comp_type, candidates in candidates_by_type.items():
        if candidates:
            best = max(candidates, key=lambda c: c.confidence)
            # Only accept if confidence is above threshold
            if best.confidence >= 0.3:
                result[comp_type] = best
            else:
                result[comp_type] = None
        else:
            result[comp_type] = None

    return result


def get_entity_state(hass: HomeAssistant, entity_id: str | None) -> State | None:
    """Get the state of an entity, or None if not configured.

    Args:
        hass: Home Assistant instance.
        entity_id: Entity ID, or None.

    Returns:
        State object, or None.
    """
    if entity_id is None:
        return None
    return hass.states.get(entity_id)


def get_bool_state(state: State | None) -> bool | None:
    """Get a boolean value from an entity state.

    Args:
        state: Entity state, or None.

    Returns:
        True/False for on/off states, None if state is None.
    """
    if state is None:
        return None
    value = state.state.lower()
    if value in ("on", "true", "1", "yes", "open", "active", "error", "problem"):
        return True
    if value in ("off", "false", "0", "no", "closed", "inactive", "ok", "normal"):
        return False
    return None


def get_float_state(state: State | None) -> float | None:
    """Get a float value from an entity state.

    Args:
        state: Entity state, or None.

    Returns:
        Float value, or None if not parseable.
    """
    if state is None:
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        # Check attributes for numeric value
        for attr_key in ("value", "measurement", "area", "cleaned_area"):
            if attr_key in state.attributes:
                try:
                    return float(state.attributes[attr_key])
                except (ValueError, TypeError):
                    continue
        return None


def get_str_state(state: State | None) -> str | None:
    """Get a string value from an entity state.

    Args:
        state: Entity state, or None.

    Returns:
        String state value, or None.
    """
    if state is None:
        return None
    return state.state
