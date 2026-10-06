"""Tests for vendor-neutral behavior.

Tests that the integration works with any vacuum vendor without hardcoded logic.
Uses Roborock-shaped entity names as examples, not hardcoded branches.
"""

import pytest
from unittest.mock import MagicMock, patch
from custom_components.vacuum_water_level.discovery import (
    discover_companion_entities,
    EntityCandidate,
    _score_entity,
    _get_vacuum_slug,
)


class TestVendorNeutralDiscovery:
    """Tests that companion entity discovery works vendor-neutral."""

    def test_get_vacuum_slug_roborock(self):
        """Test slug extraction for Roborock entity."""
        slug = _get_vacuum_slug("vacuum.roborock_qrevo_maxv")
        assert slug == "roborock_qrevo_maxv"

    def test_get_vacuum_slug_dreame(self):
        """Test slug extraction for Dreame entity."""
        slug = _get_vacuum_slug("vacuum.dreame_l10s_ultra")
        assert slug == "dreame_l10s_ultra"

    def test_get_vacuum_slug_ecovacs(self):
        """Test slug extraction for Ecovacs entity."""
        slug = _get_vacuum_slug("vacuum.ecovacs_deebot_t9")
        assert slug == "ecovacs_deebot_t9"

    def test_get_vacuum_slug_narwal(self):
        """Test slug extraction for Narwal entity."""
        slug = _get_vacuum_slug("vacuum.narwal_freeario")
        assert slug == "narwal_freeario"

    def test_get_vacuum_slug_no_domain(self):
        """Test slug extraction for entity without domain prefix."""
        slug = _get_vacuum_slug("my_vacuum")
        assert slug == "my_vacuum"

    def test_score_entity_same_device_match(self):
        """Test scoring when entity belongs to same device."""
        score, reason = _score_entity(
            "binary_sensor.roborock_qrevo_maxv_cleaning",
            "Cleaning",
            ["cleaning"],
            "roborock_qrevo_maxv",
        )
        assert score > 0.5
        assert "same_device" in reason or "pattern_match" in reason

    def test_score_entity_different_device(self):
        """Test scoring when entity belongs to different device."""
        score, reason = _score_entity(
            "binary_sensor.other_vacuum_cleaning",
            "Cleaning",
            ["cleaning"],
            "roborock_qrevo_maxv",
        )
        # Should still match on pattern but with lower score
        assert score > 0

    def test_score_entity_no_match(self):
        """Test scoring when entity doesn't match any patterns."""
        score, reason = _score_entity(
            "sensor.temperature_living_room",
            "Living Room Temperature",
            ["cleaning"],
            "roborock_qrevo_maxv",
        )
        assert score == 0.0

    def test_score_entity_name_match(self):
        """Test scoring matches on entity friendly name."""
        score, reason = _score_entity(
            "sensor.some_entity",
            "Cleaned Area",
            ["cleaned_area", "area"],
            "roborock_qrevo_maxv",
        )
        assert score > 0
        assert "name_match" in reason


class TestDiscoveryWithMockEntities:
    """Tests for discovery with mock entity registry."""

    def test_discover_roborock_shaped_entities(self, mock_hass):
        """Test discovery with Roborock-shaped entity names (example only)."""
        mock_hass.states.async_all = MagicMock(return_value=[])

        mock_ent_reg = MagicMock()
        mock_entities = []

        # Create Roborock-shaped entities (as examples, not hardcoded)
        roborock_entities = [
            ("binary_sensor", "roborock_qrevo_maxv_cleaning", "Cleaning"),
            ("sensor", "roborock_qrevo_maxv_cleaned_area", "Cleaned Area"),
            ("sensor", "roborock_qrevo_maxv_status", "Status"),
            ("select", "roborock_qrevo_maxv_mop_mode", "Mop Mode"),
            ("select", "roborock_qrevo_maxv_mop_intensity", "Mop Intensity"),
            ("binary_sensor", "roborock_qrevo_maxv_dock_error", "Dock Error"),
            ("binary_sensor", "roborock_qrevo_maxv_dock_clean_water_box", "Clean Water Box"),
            ("binary_sensor", "roborock_qrevo_maxv_dock_dirty_water_box", "Dirty Water Box"),
        ]

        for domain, entity_id_suffix, name in roborock_entities:
            mock_entry = MagicMock()
            mock_entry.entity_id = f"{domain}.{entity_id_suffix}"
            mock_entry.name = name
            mock_entry.original_name = name
            mock_entities.append(mock_entry)

        mock_ent_reg.entities.values.return_value = mock_entities

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_ent_reg,
        ):
            result = discover_companion_entities(
                mock_hass, "vacuum.roborock_qrevo_maxv"
            )

        # Should discover all companion types
        assert result.get("cleaning") is not None
        assert result.get("area") is not None
        assert result.get("status") is not None
        assert result.get("mop_mode") is not None
        assert result.get("mop_intensity") is not None
        assert result.get("dock_error") is not None
        assert result.get("clean_water") is not None
        assert result.get("dirty_water") is not None

        # Check specific discoveries
        assert "cleaning" in result["cleaning"].entity_id
        assert "area" in result["area"].entity_id.lower()

    def test_discover_dreame_shaped_entities(self, mock_hass):
        """Test discovery with Dreame-shaped entity names."""
        mock_hass.states.async_all = MagicMock(return_value=[])

        mock_ent_reg = MagicMock()
        mock_entities = []

        dreame_entities = [
            ("binary_sensor", "dreame_l10s_cleaning", "Cleaning"),
            ("sensor", "dreame_l10s_cleaned_area", "Cleaned Area"),
            ("sensor", "dreame_l10s_status", "Status"),
            ("select", "dreame_l10s_mop_intensity", "Water Volume"),
        ]

        for domain, entity_id_suffix, name in dreame_entities:
            mock_entry = MagicMock()
            mock_entry.entity_id = f"{domain}.{entity_id_suffix}"
            mock_entry.name = name
            mock_entry.original_name = name
            mock_entities.append(mock_entry)

        mock_ent_reg.entities.values.return_value = mock_entities

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_ent_reg,
        ):
            result = discover_companion_entities(
                mock_hass, "vacuum.dreame_l10s"
            )

        # Should discover available companion types
        assert result.get("cleaning") is not None
        assert result.get("area") is not None
        assert result.get("mop_intensity") is not None

    def test_discover_ecovacs_shaped_entities(self, mock_hass):
        """Test discovery with Ecovacs-shaped entity names."""
        mock_hass.states.async_all = MagicMock(return_value=[])

        mock_ent_reg = MagicMock()
        mock_entities = []

        ecovacs_entities = [
            ("sensor", "ecovacs_deebot_cleaned_area", "Cleaned Area"),
            ("sensor", "ecovacs_deebot_status", "Work Mode"),
        ]

        for domain, entity_id_suffix, name in ecovacs_entities:
            mock_entry = MagicMock()
            mock_entry.entity_id = f"{domain}.{entity_id_suffix}"
            mock_entry.name = name
            mock_entry.original_name = name
            mock_entities.append(mock_entry)

        mock_ent_reg.entities.values.return_value = mock_entities

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_ent_reg,
        ):
            result = discover_companion_entities(
                mock_hass, "vacuum.ecovacs_deebot"
            )

        assert result.get("area") is not None
        assert result.get("status") is not None

    def test_discover_no_companions_returns_none(self, mock_hass):
        """Test that discovery returns None for all types when no companions exist."""
        mock_hass.states.async_all = MagicMock(return_value=[])

        mock_ent_reg = MagicMock()
        mock_ent_reg.entities.values.return_value = []

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_ent_reg,
        ):
            result = discover_companion_entities(
                mock_hass, "vacuum.unknown_brand"
            )

        for comp_type in [
            "cleaning", "area", "status", "mop_mode", "mop_intensity",
            "dock_error", "clean_water", "dirty_water"
        ]:
            assert result.get(comp_type) is None

    def test_discovery_is_vendor_neutral(self, mock_hass):
        """Test that discovery uses the same logic for all vendors."""
        mock_hass.states.async_all = MagicMock(return_value=[])

        mock_ent_reg = MagicMock()

        # Create entities with a completely unknown vendor name
        mock_entities = [
            self._make_entry("binary_sensor", "futurebot_x1_cleaning", "Cleaning"),
            self._make_entry("sensor", "futurebot_x1_cleaned_area", "Cleaned Area"),
        ]

        mock_ent_reg.entities.values.return_value = mock_entities

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_ent_reg,
        ):
            result = discover_companion_entities(
                mock_hass, "vacuum.futurebot_x1"
            )

        # Should still discover companions despite unknown vendor
        assert result.get("cleaning") is not None
        assert result.get("area") is not None

    @staticmethod
    def _make_entry(domain: str, entity_id_suffix: str, name: str):
        """Create a mock entity registry entry."""
        entry = MagicMock()
        entry.entity_id = f"{domain}.{entity_id_suffix}"
        entry.name = name
        entry.original_name = name
        return entry
