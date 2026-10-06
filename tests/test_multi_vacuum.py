"""Tests for multi-vacuum isolation.

Tests that multiple vacuums tracked by the integration do not interfere
with each other - each has its own storage, models, and state.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from custom_components.vacuum_water_level.storage import VacuumWaterStorage
from custom_components.vacuum_water_level.learning import (
    WaterModel,
    WasteModel,
    ReserveLearning,
    VacuumWaterState,
)


class TestMultiVacuumIsolation:
    """Tests for multi-vacuum storage isolation."""

    @pytest.mark.asyncio
    async def test_separate_storage_per_entry(self, mock_hass):
        """Test that each config entry gets separate storage."""
        storage1 = VacuumWaterStorage(mock_hass, "entry_1")
        storage2 = VacuumWaterStorage(mock_hass, "entry_2")

        storage1._store = MagicMock()
        storage1._store.async_load = AsyncMock(return_value=None)
        storage2._store = MagicMock()
        storage2._store.async_load = AsyncMock(return_value=None)

        await storage1.async_load()
        await storage2.async_load()

        # Modify storage1
        wm1 = storage1.get_water_model()
        wm1.cycles_observed = 10
        storage1.update_water_model(wm1)

        # Storage2 should be unaffected
        wm2 = storage2.get_water_model()
        assert wm2.cycles_observed == 0

    @pytest.mark.asyncio
    async def test_separate_reserve_learning(self, mock_hass):
        """Test that reserve learning is separate per vacuum."""
        storage1 = VacuumWaterStorage(mock_hass, "entry_1")
        storage2 = VacuumWaterStorage(mock_hass, "entry_2")

        storage1._store = MagicMock()
        storage1._store.async_load = AsyncMock(return_value=None)
        storage2._store = MagicMock()
        storage2._store.async_load = AsyncMock(return_value=None)

        await storage1.async_load()
        await storage2.async_load()

        # Learn reserve for vacuum 1
        rl1 = storage1.get_reserve_learning()
        rl1.update_clean_reserve(250.0, 210.0)
        storage1.update_reserve_learning(rl1)

        # Vacuum 2 should have no reserve
        rl2 = storage2.get_reserve_learning()
        assert rl2.clean_reserve_ml == 0.0
        assert rl2.warning_cycles == 0

    @pytest.mark.asyncio
    async def test_separate_runtime_state(self, mock_hass):
        """Test that runtime state is separate per vacuum."""
        storage1 = VacuumWaterStorage(mock_hass, "entry_1")
        storage2 = VacuumWaterStorage(mock_hass, "entry_2")

        storage1._store = MagicMock()
        storage1._store.async_load = AsyncMock(return_value=None)
        storage2._store = MagicMock()
        storage2._store.async_load = AsyncMock(return_value=None)

        await storage1.async_load()
        await storage2.async_load()

        # Set state for vacuum 1
        rs1 = storage1.get_runtime_state()
        rs1.water_used_since_refill_ml = 150.0
        rs1.waste_collected_ml = 120.0
        rs1.last_refill = "2024-01-01T00:00:00"
        storage1.update_runtime_state(rs1)

        # Vacuum 2 should have default state
        rs2 = storage2.get_runtime_state()
        assert rs2.water_used_since_refill_ml == 0.0
        assert rs2.waste_collected_ml == 0.0
        assert rs2.last_refill is None

    @pytest.mark.asyncio
    async def test_separate_waste_models(self, mock_hass):
        """Test that waste models are separate per vacuum."""
        storage1 = VacuumWaterStorage(mock_hass, "entry_1")
        storage2 = VacuumWaterStorage(mock_hass, "entry_2")

        storage1._store = MagicMock()
        storage1._store.async_load = AsyncMock(return_value=None)
        storage2._store = MagicMock()
        storage2._store.async_load = AsyncMock(return_value=None)

        await storage1.async_load()
        await storage2.async_load()

        # Calibrate waste model for vacuum 1
        wsm1 = storage1.get_waste_model()
        wsm1.record_usage(100.0)
        wsm1.calibrate(85.0, 100.0)
        storage1.update_waste_model(wsm1)

        # Vacuum 2 should have default waste model
        wsm2 = storage2.get_waste_model()
        assert wsm2.cycles_observed == 0
        assert wsm2.waste_ratio == 0.9  # default

    @pytest.mark.asyncio
    async def test_different_capacities_per_vacuum(self, mock_hass):
        """Test that different vacuums can have different tank capacities."""
        # This is tested at the coordinator level, but we verify storage
        # doesn't impose any capacity constraints
        storage = VacuumWaterStorage(mock_hass, "entry_1")
        storage._store = MagicMock()
        storage._store.async_load = AsyncMock(return_value=None)

        await storage.async_load()

        # Storage should not contain capacity - that's in config
        assert "clean_tank_capacity" not in storage.data
        assert "dirty_tank_capacity" not in storage.data

    @pytest.mark.asyncio
    async def test_clear_model_does_not_affect_other_vacuum(self, mock_hass):
        """Test that clearing one vacuum's model doesn't affect another."""
        storage1 = VacuumWaterStorage(mock_hass, "entry_1")
        storage2 = VacuumWaterStorage(mock_hass, "entry_2")

        storage1._store = MagicMock()
        storage1._store.async_load = AsyncMock(return_value=None)
        storage2._store = MagicMock()
        storage2._store.async_load = AsyncMock(return_value=None)

        await storage1.async_load()
        await storage2.async_load()

        # Set up vacuum 1 with learned data
        wm1 = storage1.get_water_model()
        wm1.cycles_observed = 20
        wm1.correction_factors["area_ml_per_m2"] = 3.5
        storage1.update_water_model(wm1)

        # Set up vacuum 2 with learned data
        wm2 = storage2.get_water_model()
        wm2.cycles_observed = 5
        wm2.correction_factors["area_ml_per_m2"] = 2.0
        storage2.update_water_model(wm2)

        # Clear vacuum 1's model
        wm1.reset_model()
        storage1.update_water_model(wm1)

        # Vacuum 2 should be unaffected
        wm2_check = storage2.get_water_model()
        assert wm2_check.cycles_observed == 5
        assert wm2_check.correction_factors["area_ml_per_m2"] == 2.0
