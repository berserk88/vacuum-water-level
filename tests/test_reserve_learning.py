"""Tests for reserve learning (EWMA convergence).

These tests verify that the ReserveLearning class correctly learns reserve
volumes using EWMA and that the learning converges in the right direction.
"""

import pytest
from custom_components.vacuum_water_level.learning import (
    ReserveLearning,
    ewma,
    DEFAULT_CLEAN_RESERVE_ML,
    DEFAULT_DIRTY_RESERVE_ML,
    EWMA_ALPHA_RESERVE,
)


class TestEWMA:
    """Tests for the EWMA helper function."""

    def test_ewma_basic_update(self):
        """Test basic EWMA update."""
        result = ewma(10.0, 20.0, 0.3)
        expected = 10.0 * 0.7 + 20.0 * 0.3
        assert result == pytest.approx(expected)

    def test_ewma_with_nan_current(self):
        """Test EWMA when current value is NaN."""
        import math
        result = ewma(float("nan"), 50.0, 0.3)
        assert result == 50.0

    def test_ewma_with_none_current(self):
        """Test EWMA when current value is None."""
        result = ewma(None, 50.0, 0.3)
        assert result == 50.0

    def test_ewma_alpha_zero(self):
        """Test EWMA with alpha=0 (no update)."""
        result = ewma(10.0, 20.0, 0.0)
        assert result == pytest.approx(10.0)

    def test_ewma_alpha_one(self):
        """Test EWMA with alpha=1 (full replacement)."""
        result = ewma(10.0, 20.0, 1.0)
        assert result == pytest.approx(20.0)


class TestReserveLearningClean:
    """Tests for clean water reserve learning."""

    def test_initial_clean_reserve_is_zero(self):
        """Test that initial clean reserve is 0."""
        rl = ReserveLearning()
        assert rl.clean_reserve_ml == DEFAULT_CLEAN_RESERVE_ML

    def test_update_clean_reserve(self):
        """Test updating clean reserve when water low warning fires."""
        rl = ReserveLearning()
        capacity = 250.0
        used = 200.0  # 50 mL reserve
        rl.update_clean_reserve(capacity, used)
        # First observation with EWMA: result should move toward observation
        expected = ewma(0.0, 50.0, EWMA_ALPHA_RESERVE)
        assert rl.clean_reserve_ml == pytest.approx(expected, abs=0.01)

    def test_clean_reserve_warning_cycles_increment(self):
        """Test that warning_cycles increments on clean reserve update."""
        rl = ReserveLearning()
        rl.update_clean_reserve(250.0, 200.0)
        assert rl.warning_cycles == 1
        rl.update_clean_reserve(250.0, 195.0)
        assert rl.warning_cycles == 2

    def test_clean_reserve_negative_used_clamped(self):
        """Test that negative observed reserve is clamped to 0."""
        rl = ReserveLearning()
        rl.update_clean_reserve(250.0, 260.0)  # used > capacity
        assert rl.clean_reserve_ml >= 0.0

    def test_clean_reserve_converges_toward_true_value(self):
        """Test that clean reserve converges toward the true reserve over multiple cycles."""
        rl = ReserveLearning()
        true_reserve = 40.0  # Vacuum warns when 40 mL remain
        capacity = 250.0
        used = capacity - true_reserve

        for _ in range(50):
            rl.update_clean_reserve(capacity, used)

        # Should converge close to true_reserve
        assert rl.clean_reserve_ml == pytest.approx(true_reserve, abs=2.0)

    def test_clean_reserve_moves_in_correct_direction(self):
        """Test that reserve moves toward new observation."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 30.0

        # New observation: 50 mL reserve
        rl.update_clean_reserve(250.0, 200.0)

        # Should move toward 50 (up from 30)
        assert rl.clean_reserve_ml > 30.0

    def test_clean_reserve_bounded_between_zero_and_capacity(self):
        """Test that reserve stays bounded."""
        rl = ReserveLearning()
        for _ in range(100):
            rl.update_clean_reserve(250.0, 10.0)  # 240 mL reserve
        assert 0.0 <= rl.clean_reserve_ml <= 250.0


class TestReserveLearningDirty:
    """Tests for dirty water reserve learning."""

    def test_initial_dirty_reserve_is_zero(self):
        """Test that initial dirty reserve is 0."""
        rl = ReserveLearning()
        assert rl.dirty_reserve_ml == DEFAULT_DIRTY_RESERVE_ML

    def test_update_dirty_reserve(self):
        """Test updating dirty reserve when waste full warning fires."""
        rl = ReserveLearning()
        capacity = 250.0
        waste = 200.0  # 50 mL reserve
        rl.update_dirty_reserve(capacity, waste)
        expected = ewma(0.0, 50.0, EWMA_ALPHA_RESERVE)
        assert rl.dirty_reserve_ml == pytest.approx(expected, abs=0.01)

    def test_dirty_reserve_warning_cycles_increment(self):
        """Test that warning_cycles increments on dirty reserve update."""
        rl = ReserveLearning()
        rl.update_dirty_reserve(250.0, 200.0)
        assert rl.warning_cycles == 1

    def test_dirty_reserve_converges_toward_true_value(self):
        """Test that dirty reserve converges toward the true reserve."""
        rl = ReserveLearning()
        true_reserve = 30.0
        capacity = 250.0
        waste = capacity - true_reserve

        for _ in range(50):
            rl.update_dirty_reserve(capacity, waste)

        assert rl.dirty_reserve_ml == pytest.approx(true_reserve, abs=2.0)

    def test_dirty_reserve_moves_in_correct_direction(self):
        """Test that dirty reserve moves toward new observation."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 20.0
        rl.update_dirty_reserve(250.0, 200.0)  # 50 mL reserve
        assert rl.dirty_reserve_ml > 20.0


class TestEffectiveCapacity:
    """Tests for effective capacity calculation."""

    def test_effective_clean_capacity_default(self):
        """Test effective clean capacity with no reserve."""
        rl = ReserveLearning()
        assert rl.effective_clean_capacity(250.0) == 250.0

    def test_effective_clean_capacity_with_reserve(self):
        """Test effective clean capacity with learned reserve."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 40.0
        assert rl.effective_clean_capacity(250.0) == 210.0

    def test_effective_dirty_capacity_with_reserve(self):
        """Test effective dirty capacity with learned reserve."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 30.0
        assert rl.effective_dirty_capacity(250.0) == 220.0

    def test_effective_capacity_never_below_minimum(self):
        """Test that effective capacity never goes below 1."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 300.0  # More than capacity
        assert rl.effective_clean_capacity(250.0) >= 1.0

    def test_effective_dirty_capacity_never_below_minimum(self):
        """Test that effective dirty capacity never goes below 1."""
        rl = ReserveLearning()
        rl.dirty_reserve_ml = 300.0
        assert rl.effective_dirty_capacity(250.0) >= 1.0


class TestReserveSerialization:
    """Tests for serialization/deserialization of ReserveLearning."""

    def test_to_dict_and_from_dict_roundtrip(self):
        """Test that serialization roundtrips correctly."""
        rl = ReserveLearning()
        rl.clean_reserve_ml = 35.5
        rl.dirty_reserve_ml = 28.2
        rl.warning_cycles = 5

        data = rl.to_dict()
        rl2 = ReserveLearning.from_dict(data)

        assert rl2.clean_reserve_ml == 35.5
        assert rl2.dirty_reserve_ml == 28.2
        assert rl2.warning_cycles == 5

    def test_from_dict_none(self):
        """Test deserialization from None."""
        rl = ReserveLearning.from_dict(None)
        assert rl.clean_reserve_ml == 0.0
        assert rl.dirty_reserve_ml == 0.0
        assert rl.warning_cycles == 0

    def test_from_dict_missing_fields(self):
        """Test deserialization with missing fields uses defaults."""
        rl = ReserveLearning.from_dict({"clean_reserve_ml": 20.0})
        assert rl.clean_reserve_ml == 20.0
        assert rl.dirty_reserve_ml == 0.0
        assert rl.warning_cycles == 0
