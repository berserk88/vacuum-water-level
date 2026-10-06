"""Tests for convergence behavior of the learning models.

These tests verify that the adaptive learning models converge in the correct
direction and remain bounded, rather than testing exact floating-point equality.
"""

import pytest
from custom_components.vacuum_water_level.learning import (
    WaterModel,
    WasteModel,
    ReserveLearning,
    ewma,
    DEFAULT_BASE_ML_PER_M2,
    DEFAULT_WASH_VOLUME_ML,
    DEFAULT_WASTE_RATIO,
)


class TestWaterModelConvergence:
    """Tests for water model convergence behavior."""

    def test_area_rate_converges_toward_true_value(self):
        """Test that area consumption rate converges toward the true rate."""
        wm = WaterModel()
        true_rate = 4.0  # True consumption is 4 mL/m²

        # Simulate multiple cleaning cycles
        for _ in range(30):
            area = 50.0  # 50 m² per session
            # Record usage with current model
            estimated = wm.record_usage(area, "on", "medium", 0)
            # Actual usage based on true rate
            actual = area * true_rate
            wm.calibrate(actual)

        # The correction factor should converge toward true_rate
        learned_rate = wm.correction_factors.get("area_ml_per_m2", DEFAULT_BASE_ML_PER_M2)
        assert learned_rate == pytest.approx(true_rate, abs=0.5)

    def test_wash_volume_converges_toward_true_value(self):
        """Test that wash volume converges toward the true wash volume."""
        wm = WaterModel()
        true_wash_volume = 80.0  # True wash volume is 80 mL

        # Simulate multiple cycles with wash events
        for _ in range(30):
            area = 30.0
            estimated = wm.record_usage(area, "on", "medium", 1)
            # Actual usage = area * base_rate + true_wash_volume
            actual = area * wm.correction_factors.get(
                "area_ml_per_m2", DEFAULT_BASE_ML_PER_M2
            ) + true_wash_volume
            wm.calibrate(actual)

        learned_wash = wm.learned_wash_volume_ml
        assert learned_wash == pytest.approx(true_wash_volume, abs=15.0)

    def test_estimates_increase_monotonically_during_session(self):
        """Test that estimates only increase during a cleaning session."""
        wm = WaterModel()
        # Multiple recording calls should accumulate
        e1 = wm.record_usage(10.0, "on", "medium", 0)
        e2 = wm.record_usage(10.0, "on", "medium", 0)
        assert e2 >= e1  # At least equal (should be equal for same params)
        assert wm.pending_usage_ml > e1  # Pending should accumulate

    def test_correction_factor_bounded(self):
        """Test that correction factors stay within reasonable bounds."""
        wm = WaterModel()

        # Simulate extreme observations
        for _ in range(10):
            wm.record_usage(100.0, "on", "high", 5)
            # Actual is way more than estimated
            wm.calibrate(5000.0)

        rate = wm.correction_factors.get("area_ml_per_m2", DEFAULT_BASE_ML_PER_M2)
        # Should be bounded (not infinite)
        assert rate < 100.0
        assert rate > 0.0

    def test_correction_factor_doesnt_crash_on_zero_estimate(self):
        """Test that calibration doesn't crash when estimate is zero."""
        wm = WaterModel()
        # Record zero area usage
        wm.record_usage(0.0, "off", "medium", 0)
        wm.calibrate(100.0)
        # Should not crash, cycles may or may not increment
        assert wm.cycles_observed >= 0

    def test_model_reset_clears_wash_volume(self):
        """Test that reset clears wash_volume_ml (it's part of water_model)."""
        wm = WaterModel()
        wm.correction_factors["wash_volume_ml"] = 75.0
        wm.cycles_observed = 10

        wm.reset_model()

        # Wash volume should be reset to default
        assert wm.correction_factors.get("wash_volume_ml") == DEFAULT_WASH_VOLUME_ML
        # Cycles should be reset
        assert wm.cycles_observed == 0


class TestWasteModelConvergence:
    """Tests for waste model convergence behavior."""

    def test_waste_ratio_converges_toward_true_value(self):
        """Test that waste ratio converges toward the true ratio."""
        wsm = WasteModel()
        true_ratio = 0.75  # True waste is 75% of clean consumed

        # Simulate multiple cycles
        for _ in range(30):
            clean_used = 100.0
            wsm.record_usage(clean_used)
            actual_waste = clean_used * true_ratio
            wsm.calibrate(actual_waste, clean_used)

        learned_ratio = wsm.waste_ratio
        assert learned_ratio == pytest.approx(true_ratio, abs=0.1)

    def test_waste_ratio_starts_at_default(self):
        """Test that waste ratio starts at the default value."""
        wsm = WasteModel()
        assert wsm.waste_ratio == DEFAULT_WASTE_RATIO

    def test_waste_ratio_bounded(self):
        """Test that waste ratio stays within reasonable bounds."""
        wsm = WasteModel()

        # Simulate extreme observations
        for _ in range(10):
            wsm.record_usage(100.0)
            # Actual waste is way more than clean consumed
            wsm.calibrate(500.0, 100.0)

        ratio = wsm.waste_ratio
        assert ratio <= 3.0  # Bounded by calibration logic
        assert ratio >= 0.0

    def test_waste_ratio_converges_from_above(self):
        """Test convergence when true ratio is below default."""
        wsm = WasteModel()
        true_ratio = 0.5  # Lower than default 0.9

        for _ in range(30):
            clean_used = 100.0
            wsm.record_usage(clean_used)
            wsm.calibrate(clean_used * true_ratio, clean_used)

        assert wsm.waste_ratio == pytest.approx(true_ratio, abs=0.1)
        assert wsm.waste_ratio < DEFAULT_WASTE_RATIO

    def test_waste_ratio_converges_from_below(self):
        """Test convergence when true ratio is above default."""
        wsm = WasteModel()
        true_ratio = 1.5  # Higher than default 0.9

        for _ in range(30):
            clean_used = 100.0
            wsm.record_usage(clean_used)
            wsm.calibrate(clean_used * true_ratio, clean_used)

        assert wsm.waste_ratio == pytest.approx(true_ratio, abs=0.15)
        assert wsm.waste_ratio > DEFAULT_WASTE_RATIO

    def test_waste_ratio_moves_in_correct_direction(self):
        """Test that waste ratio moves toward new observation."""
        wsm = WasteModel()
        initial_ratio = wsm.waste_ratio

        # Record and calibrate with a higher ratio
        wsm.record_usage(100.0)
        wsm.calibrate(150.0, 100.0)  # ratio = 1.5

        assert wsm.waste_ratio > initial_ratio


class TestReserveConvergence:
    """Tests for reserve learning convergence."""

    def test_clean_reserve_converges_from_multiple_observations(self):
        """Test that clean reserve converges with varying observations."""
        rl = ReserveLearning()
        true_reserve = 35.0

        # Add some noise to observations
        import random
        random.seed(42)
        for _ in range(50):
            noise = random.uniform(-5.0, 5.0)
            rl.update_clean_reserve(250.0, 250.0 - true_reserve + noise)

        # Should converge close to true_reserve despite noise
        assert rl.clean_reserve_ml == pytest.approx(true_reserve, abs=5.0)

    def test_dirty_reserve_converges_from_multiple_observations(self):
        """Test that dirty reserve converges with varying observations."""
        rl = ReserveLearning()
        true_reserve = 28.0

        import random
        random.seed(123)
        for _ in range(50):
            noise = random.uniform(-3.0, 3.0)
            rl.update_dirty_reserve(250.0, 250.0 - true_reserve + noise)

        assert rl.dirty_reserve_ml == pytest.approx(true_reserve, abs=5.0)

    def test_reserve_learning_rate_is_reasonable(self):
        """Test that reserve learning converges at a reasonable rate."""
        rl = ReserveLearning()
        true_reserve = 40.0

        # After 5 observations, should be within 50% of true value
        for _ in range(5):
            rl.update_clean_reserve(250.0, 250.0 - true_reserve)

        assert abs(rl.clean_reserve_ml - true_reserve) < true_reserve * 0.5

    def test_reserve_does_not_oscillate_wildly(self):
        """Test that reserve doesn't oscillate wildly between updates."""
        rl = ReserveLearning()

        # Warm up with a few observations to get close to steady state
        for _ in range(20):
            rl.update_clean_reserve(250.0, 250.0 - 32.5)

        # Now alternate between two close reserve values
        values = []
        for i in range(20):
            # Alternate between two reserve values
            reserve = 30.0 if i % 2 == 0 else 35.0
            rl.update_clean_reserve(250.0, 250.0 - reserve)
            values.append(rl.clean_reserve_ml)

        # Check that the range of values is bounded after warm-up
        value_range = max(values) - min(values)
        assert value_range < 10.0  # Should not oscillate wildly

    def test_ewma_converges_exponentially(self):
        """Test that EWMA converges exponentially (faster initially, slower later)."""
        current = 0.0
        target = 100.0
        alpha = 0.3

        values = []
        for _ in range(20):
            current = ewma(current, target, alpha)
            values.append(current)

        # Early convergence should be faster
        early_delta = abs(values[4] - values[0])
        late_delta = abs(values[19] - values[15])
        assert early_delta > late_delta
