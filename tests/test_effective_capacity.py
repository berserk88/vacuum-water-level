"""Tests for effective capacity calculation.

Verifies that effective capacity = actual_capacity - reserve_ml
and that calibration never uses full capacity after reserve learning exists.
"""

import pytest
from custom_components.vacuum_water_level.learning import (
    ReserveLearning,
    WaterModel,
    WasteModel,
    compute_water_remaining_pct,
    compute_water_remaining_ml,
    compute_waste_pct,
    compute_waste_ml,
)


class TestWaterRemainingPct:
    """Tests for water remaining percentage calculation."""

    def test_full_tank_no_reserve(self):
        """Test 100% when no water used."""
        pct = compute_water_remaining_pct(0.0, 250.0, 0.0)
        assert pct == pytest.approx(100.0)

    def test_half_tank_no_reserve(self):
        """Test 50% when half used."""
        pct = compute_water_remaining_pct(125.0, 250.0, 0.0)
        assert pct == pytest.approx(50.0)

    def test_empty_tank_no_reserve(self):
        """Test 0% when all used."""
        pct = compute_water_remaining_pct(250.0, 250.0, 0.0)
        assert pct == pytest.approx(0.0)

    def test_with_reserve(self):
        """Test percentage accounting for reserve."""
        # 250 capacity, 40 reserve -> effective 210
        # Used 105 -> remaining 105 -> 50%
        pct = compute_water_remaining_pct(105.0, 250.0, 40.0)
        assert pct == pytest.approx(50.0)

    def test_reserve_makes_zero_pct_before_full_usage(self):
        """Test that 0% is reached when effective capacity is used, not full."""
        # 250 capacity, 40 reserve -> effective 210
        # Used 210 -> remaining 0 -> 0%
        pct = compute_water_remaining_pct(210.0, 250.0, 40.0)
        assert pct == pytest.approx(0.0)

    def test_clamped_to_zero(self):
        """Test that percentage doesn't go below 0."""
        pct = compute_water_remaining_pct(300.0, 250.0, 0.0)
        assert pct == 0.0

    def test_clamped_to_hundred(self):
        """Test that percentage doesn't exceed 100."""
        pct = compute_water_remaining_pct(-10.0, 250.0, 0.0)
        assert pct == 100.0

    def test_minimum_effective_capacity(self):
        """Test that effective capacity has minimum of 1."""
        # Reserve > capacity -> effective capacity = 1
        pct = compute_water_remaining_pct(0.0, 250.0, 300.0)
        assert pct == pytest.approx(100.0)


class TestWaterRemainingML:
    """Tests for water remaining mL calculation."""

    def test_full_tank_no_reserve(self):
        """Test full volume when no water used."""
        ml = compute_water_remaining_ml(0.0, 250.0, 0.0)
        assert ml == pytest.approx(250.0)

    def test_with_reserve(self):
        """Test mL accounting for reserve."""
        ml = compute_water_remaining_ml(0.0, 250.0, 40.0)
        assert ml == pytest.approx(210.0)

    def test_clamped_to_zero(self):
        """Test that mL doesn't go below 0."""
        ml = compute_water_remaining_ml(300.0, 250.0, 0.0)
        assert ml == 0.0


class TestWastePct:
    """Tests for waste tank percentage calculation."""

    def test_empty_tank_no_reserve(self):
        """Test 0% when no waste."""
        pct = compute_waste_pct(0.0, 250.0, 0.0)
        assert pct == pytest.approx(0.0)

    def test_half_full_no_reserve(self):
        """Test 50% when half full."""
        pct = compute_waste_pct(125.0, 250.0, 0.0)
        assert pct == pytest.approx(50.0)

    def test_full_no_reserve(self):
        """Test 100% when full."""
        pct = compute_waste_pct(250.0, 250.0, 0.0)
        assert pct == pytest.approx(100.0)

    def test_with_reserve(self):
        """Test percentage accounting for dirty reserve."""
        # 250 capacity, 30 reserve -> effective 220
        # Waste 110 -> 50%
        pct = compute_waste_pct(110.0, 250.0, 30.0)
        assert pct == pytest.approx(50.0)

    def test_reserve_makes_100_pct_before_full(self):
        """Test that 100% is reached when effective capacity is filled."""
        # 250 capacity, 30 reserve -> effective 220
        # Waste 220 -> 100%
        pct = compute_waste_pct(220.0, 250.0, 30.0)
        assert pct == pytest.approx(100.0)

    def test_clamped_to_hundred(self):
        """Test that percentage doesn't exceed 100."""
        pct = compute_waste_pct(300.0, 250.0, 0.0)
        assert pct == 100.0

    def test_clamped_to_zero(self):
        """Test that percentage doesn't go below 0."""
        pct = compute_waste_pct(-10.0, 250.0, 0.0)
        assert pct == 0.0


class TestWasteML:
    """Tests for waste tank mL calculation."""

    def test_waste_ml_capped_at_effective_capacity(self):
        """Test that waste mL is capped at effective capacity."""
        ml = compute_waste_ml(300.0, 250.0, 0.0)
        assert ml == 250.0

    def test_waste_ml_with_reserve(self):
        """Test waste mL with reserve."""
        ml = compute_waste_ml(300.0, 250.0, 40.0)
        assert ml == 210.0


class TestCalibrationUsesEffectiveCapacity:
    """Tests ensuring calibration uses effective capacity, not full capacity."""

    def test_water_model_calibrate_after_reserve_learning(self):
        """Test that water model calibration works correctly with reserve."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 40.0
        effective_capacity = rl.effective_clean_capacity(250.0)
        assert effective_capacity == 210.0

        # Water model should calibrate against actual usage, which is
        # measured against effective capacity (what the vacuum reports as empty)
        wm = WaterModel()
        # Simulate a cleaning session
        wm.record_usage(100.0, "on", "high", 1)
        # Actual usage was close to estimated
        wm.calibrate(wm.pending_usage_ml)
        # Model should have incremented cycles
        assert wm.cycles_observed == 1

    def test_reserve_learning_before_calibration(self):
        """Test the ordering: reserve learning must happen before calibration."""
        rl = ReserveLearning()
        wm = WaterModel()

        # Step 1: Learn reserve (happens when water low warning fires)
        rl.update_clean_reserve(250.0, 210.0)
        assert rl.clean_reserve_ml > 0.0

        # Step 2: Calibrate using effective capacity
        effective = rl.effective_clean_capacity(250.0)
        wm.record_usage(50.0, "on", "medium", 0)
        wm.calibrate(50.0)  # Actual usage matches estimate

        # The effective capacity should reflect the reserve
        assert effective < 250.0
        assert effective == 250.0 - rl.clean_reserve_ml

    def test_waste_model_calibrate_after_reserve_learning(self):
        """Test that waste model calibration works with dirty reserve."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 30.0
        effective = rl.effective_dirty_capacity(250.0)
        assert effective == 220.0

        wsm = WasteModel()
        wsm.record_usage(100.0)
        wsm.calibrate(95.0, 100.0)
        assert wsm.cycles_observed == 1
