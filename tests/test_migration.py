"""Tests for storage migration.

Tests that the storage layer correctly migrates data from older schema versions
and that data survives version upgrades.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.vacuum_water_level.storage import VacuumWaterStorage, DATA_VERSION
from custom_components.vacuum_water_level.learning import (
    WaterModel,
    WasteModel,
    ReserveLearning,
    VacuumWaterState,
)


class TestStorageMigration:
    """Tests for storage migration logic."""

    @pytest.mark.asyncio
    async def test_fresh_storage_creates_defaults(self, mock_hass):
        """Test that a fresh storage creates default data."""
        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=None)

        data = await storage.async_load()

        assert data["version"] == DATA_VERSION
        assert "water_model" in data
        assert "waste_model" in data
        assert "reserve_learning" in data
        assert "runtime_state" in data

    @pytest.mark.asyncio
    async def test_migration_from_v0(self, mock_hass):
        """Test migration from version 0 (pre-versioned) to current."""
        old_data = {
            "water_model": {
                "cycles_observed": 5,
                "correction_factors": {
                    "area_ml_per_m2": 2.5,
                    "wash_volume_ml": 45.0,
                },
                "pending_usage_ml": 100.0,
            },
            "waste_model": {
                "cycles_observed": 3,
                "correction_factors": {"waste_ratio": 0.85},
            },
            "reserve_learning": {
                "clean_reserve_ml": 30.0,
                "dirty_reserve_ml": 25.0,
                "warning_cycles": 4,
            },
            "runtime_state": {
                "water_used_since_refill_ml": 150.0,
                "waste_collected_ml": 130.0,
                "last_refill": "2024-01-01T00:00:00",
            },
        }

        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=old_data)

        data = await storage.async_load()

        # Should be migrated to current version
        assert data["version"] == DATA_VERSION

        # Water model should have correction factors filled in
        wm = data["water_model"]
        assert "mop_intensity_multiplier" in wm["correction_factors"]

        # Waste model should have waste_ratio
        wsm = data["waste_model"]
        assert "waste_ratio" in wsm["correction_factors"]

        # Reserve learning should have all fields
        rl = data["reserve_learning"]
        assert "clean_reserve_ml" in rl
        assert "dirty_reserve_ml" in rl
        assert "warning_cycles" in rl

        # Runtime state should have all fields
        rs = data["runtime_state"]
        assert "clean_warning_latched" in rs
        assert "dirty_warning_latched" in rs
        assert "cleaning_in_progress" in rs

    @pytest.mark.asyncio
    async def test_migration_preserves_existing_data(self, mock_hass):
        """Test that migration preserves existing learned data."""
        old_data = {
            "water_model": {
                "cycles_observed": 10,
                "correction_factors": {
                    "area_ml_per_m2": 3.0,
                    "mop_intensity_multiplier": {"low": 0.5, "high": 1.5},
                    "wash_volume_ml": 55.0,
                },
                "pending_usage_ml": 200.0,
                "pending_area_m2": 50.0,
                "pending_wash_count": 2,
            },
            "waste_model": {
                "cycles_observed": 8,
                "correction_factors": {"waste_ratio": 0.75},
            },
            "reserve_learning": {
                "clean_reserve_ml": 35.0,
                "dirty_reserve_ml": 28.0,
                "warning_cycles": 6,
            },
            "runtime_state": {
                "water_used_since_refill_ml": 180.0,
                "waste_collected_ml": 140.0,
                "last_refill": "2024-06-01T12:00:00",
                "last_waste_empty": "2024-06-02T08:00:00",
            },
        }

        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=old_data)

        data = await storage.async_load()

        # Check that existing data is preserved
        assert data["water_model"]["cycles_observed"] == 10
        assert data["water_model"]["correction_factors"]["area_ml_per_m2"] == 3.0
        assert data["waste_model"]["cycles_observed"] == 8
        assert data["waste_model"]["correction_factors"]["waste_ratio"] == 0.75
        assert data["reserve_learning"]["clean_reserve_ml"] == 35.0
        assert data["reserve_learning"]["warning_cycles"] == 6

    @pytest.mark.asyncio
    async def test_migration_from_completely_empty(self, mock_hass):
        """Test migration from completely empty data dict."""
        old_data = {}

        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=old_data)

        data = await storage.async_load()

        assert data["version"] == DATA_VERSION
        assert "water_model" in data
        assert "waste_model" in data
        assert "reserve_learning" in data
        assert "runtime_state" in data

    @pytest.mark.asyncio
    async def test_save_and_reload_roundtrip(self, mock_hass):
        """Test that data survives a save and reload cycle."""
        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=None)

        # Load defaults
        await storage.async_load()

        # Modify data
        wm = storage.get_water_model()
        wm.cycles_observed = 15
        wm.correction_factors["area_ml_per_m2"] = 3.5
        storage.update_water_model(wm)

        rl = storage.get_reserve_learning()
        rl.clean_reserve_ml = 42.0
        storage.update_reserve_learning(rl)

        # Save
        storage._store.async_save = AsyncMock()
        await storage.async_save()

        # Verify save was called with correct data
        saved_data = storage._store.async_save.call_args[0][0]
        assert saved_data["water_model"]["cycles_observed"] == 15
        assert saved_data["reserve_learning"]["clean_reserve_ml"] == 42.0

    @pytest.mark.asyncio
    async def test_get_methods_return_correct_objects(self, mock_hass):
        """Test that get methods return properly deserialized objects."""
        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=None)

        await storage.async_load()

        wm = storage.get_water_model()
        assert isinstance(wm, WaterModel)
        assert wm.cycles_observed == 0

        wsm = storage.get_waste_model()
        assert isinstance(wsm, WasteModel)
        assert wsm.cycles_observed == 0

        rl = storage.get_reserve_learning()
        assert isinstance(rl, ReserveLearning)
        assert rl.warning_cycles == 0

        rs = storage.get_runtime_state()
        assert isinstance(rs, VacuumWaterState)
        assert rs.water_used_since_refill_ml == 0.0

    @pytest.mark.asyncio
    async def test_diagnostics_returns_complete_data(self, mock_hass):
        """Test that diagnostics returns all expected fields."""
        storage = VacuumWaterStorage(mock_hass, "test_entry")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=None)

        await storage.async_load()

        diag = storage.get_diagnostics()

        assert "water_model" in diag
        assert "waste_model" in diag
        assert "reserve_learning" in diag
        assert "storage_version" in diag
